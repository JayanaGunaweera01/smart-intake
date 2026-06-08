"""
Train XGBoost lead-scoring classifier.
Logs parameters, metrics, and model to MLflow.
Registers best model in Model Registry.

Usage:
    python -m ml.train --data ml/data/leads.parquet --experiment lead-scoring
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import mlflow
import mlflow.xgboost

MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
import numpy as np
import pandas as pd
import xgboost as xgb
from imblearn.over_sampling import SMOTE
from mlflow.models.signature import infer_signature
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

FEATURE_COLS = [
    "is_free_email", "has_website", "source_score",
    "time_on_site_s", "pages_visited", "submission_hour",
    "submission_dow", "company_size_bucket", "domain_age_days",
    "linkedin_employees", "funding_stage", "industry_code",
]
LABEL_COL = "label"
MODEL_NAME = "lead-scorer"


def load_data(path: str):
    df = pd.read_parquet(path)
    X = df[FEATURE_COLS].fillna(-1)
    y = df[LABEL_COL]
    print(f"Dataset: {len(df)} rows | {y.mean():.1%} positive")
    return X, y


def train(data_path: str, experiment: str, register: bool = True):
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(experiment)

    X, y = load_data(data_path)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=42
    )

    # Handle class imbalance
    sm = SMOTE(random_state=42)
    X_res, y_res = sm.fit_resample(X_train, y_train)

    params = {
        "n_estimators": 400,
        "max_depth": 5,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 3,
        "scale_pos_weight": (y == 0).sum() / (y == 1).sum(),
        # BUG FIX: use_label_encoder was deprecated in XGBoost 1.6 and removed
        # in 2.0 — passing it raises TypeError with xgboost==2.0.3
        "eval_metric": "logloss",
        "random_state": 42,
        "n_jobs": -1,
    }

    with mlflow.start_run() as run:
        mlflow.log_params(params)
        mlflow.log_param("features", FEATURE_COLS)
        mlflow.log_param("n_train", len(X_res))
        mlflow.log_param("n_test", len(X_test))
        mlflow.log_param("smote_applied", True)

        model = xgb.XGBClassifier(**params)

        # Cross-validation
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_aucs = cross_val_score(model, X_res, y_res, cv=cv, scoring="roc_auc", n_jobs=-1)
        mlflow.log_metric("cv_auc_mean", cv_aucs.mean())
        mlflow.log_metric("cv_auc_std", cv_aucs.std())

        # Final fit
        model.fit(
            X_res, y_res,
            eval_set=[(X_test, y_test)],
            verbose=50,
        )

        # Eval
        y_prob = model.predict_proba(X_test)[:, 1]
        y_pred = (y_prob >= 0.5).astype(int)

        auc = roc_auc_score(y_test, y_prob)
        pr_auc = average_precision_score(y_test, y_prob)
        f1 = f1_score(y_test, y_pred)

        mlflow.log_metric("test_roc_auc", auc)
        mlflow.log_metric("test_pr_auc", pr_auc)
        mlflow.log_metric("test_f1", f1)

        report = classification_report(y_test, y_pred, output_dict=True)
        for cls, metrics in report.items():
            if isinstance(metrics, dict):
                for metric, val in metrics.items():
                    mlflow.log_metric(f"cls_{cls}_{metric}", val)

        # Feature importance
        importance = dict(zip(FEATURE_COLS, model.feature_importances_))
        mlflow.log_dict(importance, "feature_importance.json")

        # Log model
        signature = infer_signature(X_test, model.predict_proba(X_test))
        mlflow.xgboost.log_model(
            model,
            artifact_path="model",
            signature=signature,
            registered_model_name=MODEL_NAME if register else None,
            input_example=X_test.iloc[:3],
        )

        # Save reference data for drift detection
        X_train.assign(label=y_train).to_parquet("ml/data/reference.parquet", index=False)
        mlflow.log_artifact("ml/data/reference.parquet", "reference_data")

        print(f"\n{'─'*50}")
        print(f"Run ID : {run.info.run_id}")
        print(f"AUC    : {auc:.4f}")
        print(f"PR-AUC : {pr_auc:.4f}")
        print(f"F1     : {f1:.4f}")
        print(f"CV-AUC : {cv_aucs.mean():.4f} ± {cv_aucs.std():.4f}")
        print(f"{'─'*50}")

        if register:
            _promote_to_production(run.info.run_id)

        return run.info.run_id


def _promote_to_production(run_id: str):
    """Transition the model from None → Staging → Production."""
    client = mlflow.MlflowClient(tracking_uri=MLFLOW_URI)
    versions = client.search_model_versions(f"run_id='{run_id}'")
    if not versions:
        print("No registered model version found — skipping promotion")
        return
    version = versions[0].version
    client.transition_model_version_stage(
        name=MODEL_NAME, version=version, stage="Production", archive_existing_versions=True
    )
    print(f"Model v{version} promoted to Production")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="ml/data/leads.parquet")
    parser.add_argument("--experiment", default="lead-scoring")
    parser.add_argument("--no-register", action="store_true")
    args = parser.parse_args()

    Path("ml/data").mkdir(parents=True, exist_ok=True)
    train(args.data, args.experiment, register=not args.no_register)


if __name__ == "__main__":
    main()
