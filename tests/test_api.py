from backend.app.schemas.evidence import (
    AllowedResultTerminology,
    PresumptiveInterpretationSchema,
    MANDATORY_FORENSIC_DISCLAIMER
)

def test_presumptive_allowed_terminology():
    # Valid allowed terminologies
    valid_terms = [
        AllowedResultTerminology.PRESUMPTIVE_POSITIVE,
        AllowedResultTerminology.PRESUMPTIVE_NEGATIVE,
        AllowedResultTerminology.INCONCLUSIVE,
        AllowedResultTerminology.UNSUPPORTED_OOD
    ]
    
    for term in valid_terms:
        schema = PresumptiveInterpretationSchema(
            classification=term,
            primary_substance_indicated="Ketamine Matrix",
            calibrated_confidence=0.88,
            ood_metric=0.05
        )
        assert schema.classification == term
        assert "presumptive field-test interpretation" in schema.disclaimer.lower()

def test_invalid_conclusive_terminology_rejected():
    try:
        # Attempting to assign forbidden conclusive terminology MUST fail validation
        PresumptiveInterpretationSchema(
            classification="CONCLUSIVE_IDENTIFICATION", # Forbidden
            calibrated_confidence=0.99,
            ood_metric=0.01
        )
        assert False, "Should have raised ValueError"
    except ValueError:
        assert True
