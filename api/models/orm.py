"""SQLAlchemy ORM models matching db/schema.sql."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float, ForeignKey,
    Integer, SmallInteger, String, Text, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID
from sqlalchemy.orm import relationship

from api.database import Base


def _uuid():
    return str(uuid.uuid4())


class Rep(Base):
    __tablename__ = "reps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    phone = Column(Text, nullable=False)
    email = Column(Text, nullable=False, unique=True)
    tier_focus = Column(ARRAY(Text), default=["hot", "warm"])
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    assignments = relationship("RepAssignment", back_populates="rep")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(Text, unique=True, nullable=True)
    email = Column(Text, nullable=False)
    name = Column(Text)
    company = Column(Text)
    phone = Column(Text)
    website = Column(Text)
    source = Column(Text, default="web")
    raw_payload = Column(JSONB, nullable=False)
    ip_address = Column(INET)
    user_agent = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    features = relationship("LeadFeature", back_populates="lead", uselist=False)
    prediction = relationship("Prediction", back_populates="lead", uselist=False)
    assignments = relationship("RepAssignment", back_populates="lead")
    events = relationship("AuditEvent", back_populates="lead")


class LeadFeature(Base):
    __tablename__ = "lead_features"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), unique=True)
    company_size_bucket = Column(SmallInteger)
    has_website = Column(Boolean)
    domain_age_days = Column(Integer)
    is_free_email = Column(Boolean)
    source_score = Column(Float)
    time_on_site_s = Column(Integer)
    pages_visited = Column(SmallInteger)
    linkedin_employees = Column(Integer)
    funding_stage = Column(SmallInteger)
    industry_code = Column(SmallInteger)
    email_domain = Column(Text)
    submission_hour = Column(SmallInteger)
    submission_dow = Column(SmallInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lead = relationship("Lead", back_populates="features")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), unique=True)
    model_name = Column(Text, nullable=False)
    model_version = Column(Text, nullable=False)
    score = Column(Float, nullable=False)
    tier = Column(Text, nullable=False)
    shap_values = Column(JSONB)
    top_factors = Column(JSONB)
    latency_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lead = relationship("Lead", back_populates="prediction")


class RepAssignment(Base):
    __tablename__ = "rep_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"))
    rep_id = Column(UUID(as_uuid=True), ForeignKey("reps.id"))
    status = Column(Text, default="pending")
    sms_sid = Column(Text)
    notes = Column(Text)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    ack_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))

    lead = relationship("Lead", back_populates="assignments")
    rep = relationship("Rep", back_populates="assignments")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"))
    event = Column(Text, nullable=False)
    payload = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lead = relationship("Lead", back_populates="events")


class DriftSnapshot(Base):
    __tablename__ = "drift_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    psi_score = Column(Float, nullable=False)
    ks_statistic = Column(Float)
    n_samples = Column(Integer, nullable=False)
    feature_drift = Column(JSONB)
    drift_detected = Column(Boolean, default=False)
    retrain_trigger = Column(Boolean, default=False)
    report_path = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
