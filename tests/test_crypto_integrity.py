from backend.app.core.security import (
    calculate_sha256,
    generate_hmac_signature,
    verify_evidence_integrity,
    generate_chain_log_hash
)

def test_sha256_payload_hashing():
    payload = b"FORENSIC_DRUG_IMAGE_RAW_BYTES_SAMPLE_123"
    hash1 = calculate_sha256(payload)
    hash2 = calculate_sha256(payload)
    
    assert len(hash1) == 64
    assert hash1 == hash2

def test_hmac_signature_and_tamper_detection():
    payload = b"RAW_FIELD_TEST_SPECTRUM_BYTES"
    meta = {
        "case_id": "CASE-2026-001",
        "officer_id": "OFF-99",
        "reagent": "MARQUIS"
    }
    
    payload_hash = calculate_sha256(payload)
    hmac_sig = generate_hmac_signature(payload_hash, meta)
    
    # 1. Untampered check -> MUST PASS
    is_valid = verify_evidence_integrity(payload, meta, hmac_sig)
    assert is_valid is True
    
    # 2. Tampered payload (1 byte altered) -> MUST FAIL
    tampered_payload = b"RAW_FIELD_TEST_SPECTRUM_BYTEX"
    is_tampered_valid = verify_evidence_integrity(tampered_payload, meta, hmac_sig)
    assert is_tampered_valid is False
    
    # 3. Tampered metadata (officer ID modified) -> MUST FAIL
    tampered_meta = {
        "case_id": "CASE-2026-001",
        "officer_id": "OFF-100",
        "reagent": "MARQUIS"
    }
    is_meta_tampered_valid = verify_evidence_integrity(payload, tampered_meta, hmac_sig)
    assert is_meta_tampered_valid is False

def test_append_only_audit_log_hash_chain():
    gen_hash = generate_chain_log_hash("GENESIS", "Log Entry 1: Case Created")
    next_hash = generate_chain_log_hash(gen_hash, "Log Entry 2: Evidence Uploaded")
    
    assert len(gen_hash) == 64
    assert len(next_hash) == 64
    assert gen_hash != next_hash
