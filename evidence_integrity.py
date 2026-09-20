#!/usr/bin/env python3
"""
Evidence Integrity Engine Entrypoint.

Exposes EvidenceIntegrityEngine directly from the project root.
"""

from backend.app.services.evidence_integrity import EvidenceIntegrityEngine

__all__ = ["EvidenceIntegrityEngine"]

if __name__ == "__main__":
    import datetime

    # Quick CLI self-test
    sample_quality = {
        "blur_score": 142.5,
        "brightness_mean": 128.0,
        "contrast_std": 45.0,
        "reference_card_detected": True,
        "calibration_applied": True
    }
    sample_provenance = {
        "authenticated_operator": True,
        "badge_number": "BADGE-4092",
        "device_id": "DEVICE-TAB-X99",
        "gps_latitude": 37.7749,
        "gps_longitude": -122.4194
    }
    sample_metadata = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "case_id": "CASE-2026-001",
        "test_id": "TEST-2026-001",
        "reagent_name": "idPAD 12-Lane",
        "model_version": "v1.0.0-presumptive-idpad"
    }
    sample_crypto = {
        "payload_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "hmac_valid": True,
        "tamper_detected": False
    }

    result = EvidenceIntegrityEngine.evaluate(
        sample_quality,
        sample_provenance,
        sample_metadata,
        sample_crypto
    )
    import pprint
    print("Self-test Evaluation:")
    pprint.pprint(result)
