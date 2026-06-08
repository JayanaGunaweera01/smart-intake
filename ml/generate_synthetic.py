"""
Generate synthetic B2B lead data for model training.

Usage:
    python -m ml.generate_synthetic --n 5000 --out ml/data/leads.parquet
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

fake = Faker()
rng = np.random.default_rng(42)


FREE_DOMAINS = [
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "icloud.com", "protonmail.com",
]

COMPANY_DOMAINS = [
    "acme.io", "techcorp.com", "finx.co", "saasly.com",
    "growthco.ai", "pivotdata.com",
]

SOURCES = ["organic", "referral", "email", "paid", "social", "direct", "web"]
SOURCE_WEIGHTS = [0.30, 0.20, 0.15, 0.15, 0.10, 0.05, 0.05]


def _label(row: pd.Series) -> int:
    """
    Deterministic labelling function (ground truth proxy).
    A lead is 'converted' (1) when it hits ≥3 positive signals.
    """
    score = 0.0
    score += 0.30 if not row["is_free_email"] else 0.0
    score += 0.20 if row["has_website"] else 0.0
    score += 0.15 * row["source_score"]
    score += 0.10 if row["pages_visited"] >= 3 else 0.0
    score += 0.10 if row["time_on_site_s"] >= 120 else 0.0
    score += 0.10 if row["company_size_bucket"] >= 2 else 0.0
    score += 0.05 if row["funding_stage"] >= 1 else 0.0

    # Add noise
    noise = rng.normal(0, 0.08)
    return int((score + noise) >= 0.55)


def generate(n: int = 5000) -> pd.DataFrame:
    rows = []
    for _ in range(n):
        is_free = rng.random() < 0.40
        domain = fake.random_element(FREE_DOMAINS if is_free else COMPANY_DOMAINS)
        source = rng.choice(SOURCES, p=SOURCE_WEIGHTS)
        source_scores = {
            "organic": 1.0, "referral": 0.95, "email": 0.85,
            "paid": 0.80, "social": 0.70, "direct": 0.75, "web": 0.70,
        }

        row = {
            "email_domain": domain,
            "is_free_email": int(is_free),
            "has_website": int(rng.random() < (0.2 if is_free else 0.85)),
            "source_score": source_scores[source],
            "time_on_site_s": int(rng.exponential(180)),
            "pages_visited": int(rng.integers(1, 12)),
            "submission_hour": int(rng.integers(0, 24)),
            "submission_dow": int(rng.integers(0, 7)),
            "company_size_bucket": int(rng.integers(0, 5)),
            "domain_age_days": int(rng.integers(0, 5000)) if not is_free else 0,
            "linkedin_employees": int(rng.integers(0, 500)) if not is_free else 0,
            "funding_stage": int(rng.integers(0, 5)) if not is_free else 0,
            "industry_code": int(rng.integers(0, 20)),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    df["label"] = df.apply(_label, axis=1)
    print(f"Generated {len(df)} rows | conversion rate: {df['label'].mean():.1%}")
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5000)
    parser.add_argument("--out", type=str, default="ml/data/leads.parquet")
    args = parser.parse_args()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df = generate(args.n)
    df.to_parquet(args.out, index=False)
    print(f"Saved to {args.out}")


if __name__ == "__main__":
    main()
