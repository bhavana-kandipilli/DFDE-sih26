import datetime
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str
    badge_number: Optional[str] = None
    department: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class UserCreateRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str = "FIELD_OFFICER"
    badge_number: Optional[str] = None
    department: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    badge_number: Optional[str] = None
    department: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True

class CaseCreateRequest(BaseModel):
    case_number: str = Field(..., min_length=3, max_length=100)
    incident_location: str = Field(..., min_length=2, max_length=255)
    notes: Optional[str] = None

class CaseResponse(BaseModel):
    id: str
    case_number: str
    incident_location: str
    notes: Optional[str] = None
    status: str
    created_by_id: Optional[str] = None
    created_at: datetime.datetime
    result_summary: Optional[str] = None
    integrity_score: Optional[int] = None
    test_count: Optional[int] = None

    class Config:
        from_attributes = True

class TestCreateRequest(BaseModel):
    case_id: str
    reagent_name: str = Field(..., min_length=2, max_length=100)

class TestResponse(BaseModel):
    id: str
    case_id: str
    reagent_name: str
    status: str
    created_by_id: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class EvidenceResponse(BaseModel):
    id: str
    test_id: str
    payload_hash: str
    canonical_hash: Optional[str] = None
    metadata_hash: str
    hmac_signature: str
    device_id: Optional[str] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    blur_score: float
    brightness_mean: float
    contrast_std: float
    card_detected: bool
    integrity_score: Optional[int] = None
    integrity_status: Optional[str] = None
    verification_status: str
    raw_storage_path: str
    calibrated_storage_path: str
    is_finalized: bool = False
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class AIResultResponse(BaseModel):
    id: str
    test_id: str
    evidence_id: str
    classification: str
    confidence_score: float
    ood_score: float
    model_version: str
    decision_reason: Optional[str] = None
    processing_time_ms: float
    lab_confirmation_required: bool
    disclaimer: str
    integrity_score: Optional[int] = None
    integrity_status: Optional[str] = None
    canonical_hash: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class TestIntegrityResponse(BaseModel):
    test_id: str
    evidence_id: Optional[str] = None
    payload_hash: Optional[str] = None
    canonical_hash: Optional[str] = None
    hmac_signature: Optional[str] = None
    integrity_score: Optional[int] = None
    integrity_status: Optional[str] = None
    verification_status: str
    is_tampered: bool
    audit_chain_verified: bool
    chain_block_hash: Optional[str] = None

class EvidenceVerifyResponse(BaseModel):
    status: str # VERIFIED or TAMPER_DETECTED
    is_tampered: bool
    image_intact: bool
    canonical_hash_verified: bool
    stored_payload_hash: str
    recomputed_payload_hash: str
    stored_canonical_hash: Optional[str] = None
    recomputed_canonical_hash: Optional[str] = None
    hash_matched: bool = True
    hmac_valid: bool = True
    tamper_status: str = "VALID"
    calculated_payload_hash: Optional[str] = None
    verification_timestamp: str

class SyncItem(BaseModel):
    client_record_id: str
    type: str # case, test, evidence
    data: Dict[str, Any]

class SyncRequest(BaseModel):
    device_id: str
    client_sync_timestamp: str
    items: List[SyncItem] = []

class SyncResponse(BaseModel):
    device_id: str
    server_sync_timestamp: str
    records_processed: int
    status: str = "COMPLETED" # COMPLETED, SYNCED, SYNC_REJECTED
    detail: Optional[str] = None
    error: Optional[str] = None
    details: Optional[List[Dict[str, Any]]] = []

class AuditLogResponse(BaseModel):
    id: str
    case_id: Optional[str] = None
    user_id: Optional[str] = None
    action: str
    resource_id: Optional[str] = None
    previous_hash: Optional[str] = None
    current_hash: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class ModelVersionResponse(BaseModel):
    version_tag: str
    model_type: str
    accuracy: float
    f1_score: float
    is_active: bool
    thresholds: Dict[str, Any]
    classes: List[str]

class TimelineEvent(BaseModel):
    step_index: int = 1
    stage_number: int = 1
    stage_name: str
    status: str = "COMPLETED"
    actor: Optional[str] = None
    actor_badge: str = "N/A"
    timestamp: Optional[str] = None
    details: str
    block_hash: str = "GENESIS_FORENSIC_AUDIT_BLOCK"
    hash_link: Optional[str] = None
    verified: bool = True

class DashboardSummaryResponse(BaseModel):
    total_cases: int
    total_tests: int
    pending_sync: int
    presumptive_positive: int
    presumptive_negative: int
    inconclusive: int
    unsupported_ood: int
    integrity_warnings_count: int
    recent_activity: List[Dict[str, Any]] = []
    disclaimer: str = "Application record metrics only. Not representative of epidemiological or chemical prevalence statistics."

class CaseDetailResponse(BaseModel):
    case: CaseResponse
    officer_name: Optional[str] = None
    officer_badge: Optional[str] = None
    tests: List[Dict[str, Any]] = []
    timeline: List[TimelineEvent] = []
    audit_logs: List[AuditLogResponse] = []
