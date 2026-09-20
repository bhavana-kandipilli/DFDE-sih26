-- Production PostgreSQL Database Schema for Digital Field Drug Evidence System
-- Version: 1.0.0

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'FIELD_OFFICER', -- FIELD_OFFICER, FORENSIC_ANALYST, ADMIN, AUDITOR, READ_ONLY
    badge_number VARCHAR(100),
    department VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cases (
    id VARCHAR(36) PRIMARY KEY,
    case_number VARCHAR(100) UNIQUE NOT NULL,
    incident_location VARCHAR(255) NOT NULL,
    notes TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'OPEN', -- OPEN, UNDER_REVIEW, CLOSED, ARCHIVED
    created_by_id VARCHAR(36) REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tests (
    id VARCHAR(36) PRIMARY KEY,
    case_id VARCHAR(36) NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    reagent_name VARCHAR(100) NOT NULL, -- idPAD, Marquis, Scott, etc.
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING', -- PENDING, EVIDENCE_UPLOADED, ANALYZED, REJECTED
    is_finalized BOOLEAN NOT NULL DEFAULT FALSE,
    created_by_id VARCHAR(36) REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evidence (
    id VARCHAR(36) PRIMARY KEY,
    test_id VARCHAR(36) UNIQUE NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    raw_storage_path VARCHAR(512) NOT NULL,
    calibrated_storage_path VARCHAR(512) NOT NULL,
    patch_storage_path VARCHAR(512) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL, -- SHA-256 of raw image
    canonical_hash VARCHAR(64), -- SHA-256 of canonical evidence record
    metadata_hash VARCHAR(64) NOT NULL,
    hmac_signature VARCHAR(64) NOT NULL,
    device_id VARCHAR(100),
    gps_latitude FLOAT,
    gps_longitude FLOAT,
    blur_score FLOAT NOT NULL,
    brightness_mean FLOAT NOT NULL,
    contrast_std FLOAT NOT NULL,
    card_detected BOOLEAN NOT NULL DEFAULT TRUE,
    integrity_score INTEGER,
    integrity_status VARCHAR(50), -- HIGH, MEDIUM, LOW, COMPROMISED
    verification_status VARCHAR(50) NOT NULL DEFAULT 'VALID', -- VALID, TAMPERED_DISQUALIFIED
    is_finalized BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_results (
    id VARCHAR(36) PRIMARY KEY,
    test_id VARCHAR(36) UNIQUE NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    evidence_id VARCHAR(36) UNIQUE NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
    classification VARCHAR(50) NOT NULL, -- PRESUMPTIVE_POSITIVE, PRESUMPTIVE_NEGATIVE, INCONCLUSIVE, UNSUPPORTED / OUT_OF_DISTRIBUTION
    confidence_score FLOAT NOT NULL,
    ood_score FLOAT NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    decision_reason TEXT,
    processing_time_ms FLOAT NOT NULL,
    lab_confirmation_required BOOLEAN NOT NULL DEFAULT TRUE,
    disclaimer TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    case_id VARCHAR(36) REFERENCES cases(id) ON DELETE SET NULL,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_id VARCHAR(36),
    payload_snapshot TEXT,
    previous_hash VARCHAR(64),
    current_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_versions (
    id VARCHAR(36) PRIMARY KEY,
    version_tag VARCHAR(50) UNIQUE NOT NULL,
    model_type VARCHAR(100) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    accuracy FLOAT NOT NULL,
    f1_score FLOAT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sync_records (
    id VARCHAR(36) PRIMARY KEY,
    device_id VARCHAR(100) NOT NULL,
    client_sync_timestamp VARCHAR(50) NOT NULL,
    records_synced INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'COMPLETED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indices for rapid querying and integrity verification
CREATE INDEX IF NOT EXISTS idx_cases_case_number ON cases(case_number);
CREATE INDEX IF NOT EXISTS idx_tests_case_id ON tests(case_id);
CREATE INDEX IF NOT EXISTS idx_evidence_payload_hash ON evidence(payload_hash);
CREATE INDEX IF NOT EXISTS idx_audit_logs_case_id ON audit_logs(case_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_current_hash ON audit_logs(current_hash);
