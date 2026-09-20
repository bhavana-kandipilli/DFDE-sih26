from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class AllowedResultTerminology(str, Enum):
    PRESUMPTIVE_POSITIVE = "PRESUMPTIVE_POSITIVE"
    PRESUMPTIVE_NEGATIVE = "PRESUMPTIVE_NEGATIVE"
    INCONCLUSIVE = "INCONCLUSIVE"
    UNSUPPORTED_OOD = "UNSUPPORTED / OUT_OF_DISTRIBUTION"

MANDATORY_FORENSIC_DISCLAIMER = (
    "NOTICE: This output is a presumptive field-test interpretation. "
    "The system DOES NOT conclusively identify drugs. "
    "Laboratory confirmation (GC-MS / LC-MS) is required for forensic/legal proof."
)

class QualityAssessmentSchema(BaseModel):
    passed: bool
    failure_reasons: List[str] = []
    blur_score: float
    brightness_mean: float
    color_card_detected: bool
    extracted_patches_count: int

class PresumptiveInterpretationSchema(BaseModel):
    classification: AllowedResultTerminology
    primary_substance_indicated: Optional[str] = None
    calibrated_confidence: float = Field(..., ge=0.0, le=1.0)
    ood_metric: float
    model_version: str = "v1.0-presumptive-ensemble"
    lab_confirmation_required: bool = True
    disclaimer: str = MANDATORY_FORENSIC_DISCLAIMER

class EvidenceIntegritySchema(BaseModel):
    payload_hash: str
    metadata_hash: str
    hmac_signature: str
    verification_status: str

class EvidenceUploadResponse(BaseModel):
    evidence_id: str
    case_id: str
    reagent_name: str
    quality_assessment: QualityAssessmentSchema
    presumptive_result: PresumptiveInterpretationSchema
    evidence_integrity: EvidenceIntegritySchema
