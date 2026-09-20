import uuid
import datetime
from sqlalchemy import Column, String, Float, Boolean, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from backend.app.db.session import Base

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="FIELD_OFFICER") # FIELD_OFFICER, FORENSIC_ANALYST, ADMIN, AUDITOR, READ_ONLY
    badge_number = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    cases = relationship("Case", back_populates="created_by")
    tests = relationship("Test", back_populates="created_by")
    audit_logs = relationship("AuditLog", back_populates="user")

class Case(Base):
    __tablename__ = "cases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_number = Column(String(100), unique=True, nullable=False, index=True)
    incident_location = Column(String(255), nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String(50), default="OPEN", nullable=False) # OPEN, UNDER_REVIEW, CLOSED, ARCHIVED
    created_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    created_by = relationship("User", back_populates="cases")
    tests = relationship("Test", back_populates="case", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="case")

class Test(Base):
    __tablename__ = "tests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    reagent_name = Column(String(100), nullable=False) # idPAD, Marquis, Scott, etc.
    status = Column(String(50), default="PENDING", nullable=False) # PENDING, EVIDENCE_UPLOADED, ANALYZED, REJECTED
    is_finalized = Column(Boolean, default=False, nullable=False)
    created_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    case = relationship("Case", back_populates="tests")
    created_by = relationship("User", back_populates="tests")
    evidence = relationship("Evidence", back_populates="test", uselist=False, cascade="all, delete-orphan")
    ai_result = relationship("AIResult", back_populates="test", uselist=False, cascade="all, delete-orphan")

class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    test_id = Column(String(36), ForeignKey("tests.id"), unique=True, nullable=False, index=True)
    raw_storage_path = Column(String(512), nullable=False)
    calibrated_storage_path = Column(String(512), nullable=False)
    patch_storage_path = Column(String(512), nullable=False)
    payload_hash = Column(String(64), nullable=False, index=True) # SHA-256 of raw image
    canonical_hash = Column(String(64), nullable=True, index=True) # SHA-256 of canonical evidence record
    metadata_hash = Column(String(64), nullable=False)
    hmac_signature = Column(String(64), nullable=False)
    device_id = Column(String(100), nullable=True)
    gps_latitude = Column(Float, nullable=True)
    gps_longitude = Column(Float, nullable=True)
    blur_score = Column(Float, nullable=False)
    brightness_mean = Column(Float, nullable=False)
    contrast_std = Column(Float, nullable=False)
    card_detected = Column(Boolean, default=True, nullable=False)
    integrity_score = Column(Integer, nullable=True)
    integrity_status = Column(String(50), nullable=True) # HIGH, MEDIUM, LOW, COMPROMISED
    verification_status = Column(String(50), default="VALID", nullable=False) # VALID, TAMPERED_DISQUALIFIED
    is_finalized = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    test = relationship("Test", back_populates="evidence")
    ai_result = relationship("AIResult", back_populates="evidence", uselist=False)

class AIResult(Base):
    __tablename__ = "ai_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    test_id = Column(String(36), ForeignKey("tests.id"), unique=True, nullable=False, index=True)
    evidence_id = Column(String(36), ForeignKey("evidence.id"), unique=True, nullable=False, index=True)
    classification = Column(String(50), nullable=False) # PRESUMPTIVE_POSITIVE, PRESUMPTIVE_NEGATIVE, INCONCLUSIVE, UNSUPPORTED / OUT_OF_DISTRIBUTION
    confidence_score = Column(Float, nullable=False) # Calibrated probability
    ood_score = Column(Float, nullable=False)
    model_version = Column(String(50), nullable=False)
    decision_reason = Column(Text, nullable=True)
    processing_time_ms = Column(Float, nullable=False)
    lab_confirmation_required = Column(Boolean, default=True, nullable=False)
    disclaimer = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    test = relationship("Test", back_populates="ai_result")
    evidence = relationship("Evidence", back_populates="ai_result")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False) # CASE_CREATED, EVIDENCE_UPLOADED, AI_ANALYSIS_EXECUTED, EVIDENCE_VERIFIED
    resource_id = Column(String(36), nullable=True)
    payload_snapshot = Column(Text, nullable=True)
    previous_hash = Column(String(64), nullable=True)
    current_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    case = relationship("Case", back_populates="audit_logs")
    user = relationship("User", back_populates="audit_logs")

class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    version_tag = Column(String(50), unique=True, nullable=False)
    model_type = Column(String(100), nullable=False) # Logistic_Regression_Platt_Calibrated
    file_path = Column(String(512), nullable=False)
    accuracy = Column(Float, nullable=False)
    f1_score = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class SyncRecord(Base):
    __tablename__ = "sync_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    device_id = Column(String(100), nullable=False, index=True)
    client_sync_timestamp = Column(String(50), nullable=False)
    records_synced = Column(Integer, default=0, nullable=False)
    status = Column(String(50), default="COMPLETED", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
