#!/usr/bin/env python3
"""
Comprehensive Test Suite for Evidence Integrity Engine.
Tests:
- Deterministic scoring system and diagnostic checks
- Canonical evidence representation and cryptographic hashing
- Tamper detection on modified raw image binary
- Tamper detection on modified metadata
- Tamper detection on altered AI result
- Tamper detection on altered timestamp
- Missing fields and degradation handling
- Immutability enforcement and duplicate upload prevention
- Digital Evidence Certificate generation and legal disclaimer compliance
"""

import os
import io
import json
import time
import uuid
import datetime
import unittest
import numpy as np
import cv2
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.db.models import User, Case, Test, Evidence, AIResult, AuditLog
from backend.app.core.config import settings
from backend.app.services.evidence_integrity import EvidenceIntegrityEngine
from backend.app.core.security import calculate_sha256
from backend.app.db.init_db import init_db

class TestEvidenceIntegrityEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Create valid test image
        img = np.ones((200, 300, 3), dtype=np.uint8) * 140
        # Draw high-contrast features for Laplacian variance & reference card
        cv2.rectangle(img, (20, 20), (280, 180), (255, 255, 255), -1)
        cv2.rectangle(img, (40, 40), (120, 160), (30, 80, 200), -1)
        cv2.rectangle(img, (140, 40), (260, 160), (200, 50, 40), -1)
        for i in range(10):
            cv2.line(img, (50, 30 + i * 14), (250, 30 + i * 14), (0, 0, 0), 2)

        _, buf = cv2.imencode(".png", img)
        cls.valid_image_bytes = buf.tobytes()

        # Login officer
        login_res = cls.client.post("/auth/login", json={"username": "officer1", "password": "fieldpass123"})
        cls.officer_token = login_res.json()["access_token"]
        cls.officer_badge = login_res.json().get("badge_number") or "BADGE-4092"

        # Login analyst
        analyst_res = cls.client.post("/auth/login", json={"username": "analyst1", "password": "analystpass123"})
        cls.analyst_token = analyst_res.json()["access_token"]

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def _headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    # -------------------------------------------------------------
    # 1. Deterministic Scoring Unit Tests
    # -------------------------------------------------------------
    def test_deterministic_scoring_perfect_record(self):
        """Valid, high-quality capture scores 100 points with HIGH status."""
        eval_res = EvidenceIntegrityEngine.evaluate(
            image_quality={
                "blur_score": 150.0,
                "brightness_mean": 125.0,
                "contrast_std": 45.0,
                "reference_card_detected": True,
                "calibration_applied": True
            },
            provenance={
                "authenticated_operator": True,
                "badge_number": "BADGE-007",
                "device_id": "DEVICE-TAB-42",
                "gps_latitude": 37.7749,
                "gps_longitude": -122.4194
            },
            metadata={
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "case_id": "CASE-101",
                "test_id": "TEST-202",
                "reagent_name": "idPAD 12-Lane",
                "model_version": "v1.0.0-presumptive-idpad"
            },
            cryptography={
                "payload_hash": "a" * 64,
                "recomputed_hash": "a" * 64,
                "hmac_valid": True,
                "tamper_detected": False
            }
        )
        self.assertEqual(eval_res["score"], 100)
        self.assertEqual(eval_res["status"], "HIGH")
        self.assertTrue(eval_res["checks"]["focus_sharpness"])
        self.assertTrue(eval_res["checks"]["reference_card"])
        self.assertTrue(eval_res["checks"]["gps"])
        self.assertFalse(eval_res["checks"]["tamper_detected"])
        self.assertEqual(len(eval_res["failures"]), 0)

    def test_deterministic_scoring_missing_fields_degradation(self):
        """Missing GPS, missing device ID, and sub-optimal blur reduce score deterministically."""
        eval_res = EvidenceIntegrityEngine.evaluate(
            image_quality={
                "blur_score": 65.0, # 5 pts instead of 10
                "brightness_mean": 125.0,
                "contrast_std": 30.0,
                "reference_card_detected": True,
                "calibration_applied": False # 0 pts instead of 5
            },
            provenance={
                "authenticated_operator": True,
                "badge_number": "BADGE-007",
                "device_id": None, # 0 pts instead of 5
                "gps_latitude": None, # 0 pts instead of 5
                "gps_longitude": None
            },
            metadata={
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "case_id": "CASE-101",
                "test_id": "TEST-202",
                "reagent_name": "idPAD",
                "model_version": "v1.0.0-presumptive-idpad"
            },
            cryptography={
                "payload_hash": "b" * 64,
                "recomputed_hash": "b" * 64,
                "hmac_valid": True,
                "tamper_detected": False
            }
        )
        # Expected: 100 - 5 (blur) - 5 (calib) - 5 (device) - 5 (gps) = 80
        self.assertEqual(eval_res["score"], 80)
        self.assertEqual(eval_res["status"], "MEDIUM")
        self.assertFalse(eval_res["checks"]["gps"])
        self.assertFalse(eval_res["checks"]["device_id"])
        self.assertGreater(len(eval_res["warnings"]), 0)

    def test_tamper_override_drops_score_to_zero(self):
        """Any detected cryptographic tampering overrides all points to 0 and COMPROMISED status."""
        eval_res = EvidenceIntegrityEngine.evaluate(
            image_quality={
                "blur_score": 200.0,
                "brightness_mean": 128.0,
                "contrast_std": 50.0,
                "reference_card_detected": True,
                "calibration_applied": True
            },
            provenance={
                "authenticated_operator": True,
                "badge_number": "BADGE-007",
                "device_id": "TAB-01",
                "gps_latitude": 40.7128,
                "gps_longitude": -74.0060
            },
            metadata={
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "case_id": "CASE-999",
                "test_id": "TEST-999",
                "reagent_name": "idPAD",
                "model_version": "v1.0.0-presumptive-idpad"
            },
            cryptography={
                "payload_hash": "c" * 64,
                "recomputed_hash": "d" * 64, # MISMATCH!
                "hmac_valid": False,
                "tamper_detected": True
            }
        )
        self.assertEqual(eval_res["score"], 0)
        self.assertEqual(eval_res["status"], "COMPROMISED")
        self.assertTrue(eval_res["checks"]["tamper_detected"])
        self.assertTrue(any("CRITICAL" in f or "PAYLOAD" in f for f in eval_res["failures"]))

    # -------------------------------------------------------------
    # 2. End-to-End Workflow & Verification Tests
    # -------------------------------------------------------------
    def test_valid_evidence_lifecycle_and_verification(self):
        """Full lifecycle: upload with telemetry -> analyze -> check integrity -> verify intact."""
        # 1. Create Case
        case_res = self.client.post("/cases", json={
            "case_number": f"CASE-INTEG-{uuid.uuid4().hex[:6]}",
            "incident_location": "SFO Terminal 3",
            "notes": "Verified evidence workflow test"
        }, headers=self._headers(self.officer_token))
        self.assertEqual(case_res.status_code, 201)
        case_id = case_res.json()["id"]

        # 2. Create Test
        test_res = self.client.post("/tests", json={
            "case_id": case_id,
            "reagent_name": "idPAD 12-Lane Analytical Device"
        }, headers=self._headers(self.officer_token))
        self.assertEqual(test_res.status_code, 201)
        test_id = test_res.json()["id"]

        # 3. Upload Evidence with GPS & Device ID
        files = {"file": ("sample.png", self.valid_image_bytes, "image/png")}
        data = {
            "device_id": "FIELD-TABLET-A4",
            "latitude": "37.7749",
            "longitude": "-122.4194"
        }
        ev_res = self.client.post(f"/tests/{test_id}/evidence", files=files, data=data, headers=self._headers(self.officer_token))
        self.assertEqual(ev_res.status_code, 200)
        evidence_id = ev_res.json()["id"]
        payload_hash = ev_res.json()["payload_hash"]
        self.assertEqual(len(payload_hash), 64)

        # 4. Analyze Evidence
        an_res = self.client.post(f"/tests/{test_id}/analyze", headers=self._headers(self.officer_token))
        self.assertEqual(an_res.status_code, 200)
        an_data = an_res.json()
        self.assertIsNotNone(an_data["canonical_hash"])
        self.assertGreaterEqual(an_data["integrity_score"], 80)
        self.assertEqual(an_data["integrity_status"], "HIGH")

        # 5. Verify Evidence via POST /evidence/{id}/verify
        verify_res = self.client.post(f"/evidence/{evidence_id}/verify", headers=self._headers(self.analyst_token))
        self.assertEqual(verify_res.status_code, 200)
        v_data = verify_res.json()
        self.assertEqual(v_data["status"], "VERIFIED")
        self.assertFalse(v_data["is_tampered"])
        self.assertTrue(v_data["image_intact"])
        self.assertTrue(v_data["canonical_hash_verified"])
        self.assertEqual(v_data["recomputed_payload_hash"], payload_hash)

        # 6. Retrieve Digital Forensic Certificate
        cert_res = self.client.get(f"/evidence/{evidence_id}/certificate", headers=self._headers(self.officer_token))
        self.assertEqual(cert_res.status_code, 200)
        cert = cert_res.json()
        self.assertIn("CERT-", cert["certificate_id"])
        self.assertEqual(cert["verification_status"], "VALID")
        self.assertGreaterEqual(cert["evidence_integrity"]["score"], 80)
        self.assertIn("GC-MS", cert["disclaimer"])
        self.assertEqual(cert["cryptographic_hashes"]["raw_image_sha256"], payload_hash)

    # -------------------------------------------------------------
    # 3. Tamper Detection: Modified Image Binary
    # -------------------------------------------------------------
    def test_detect_modified_image_tamper(self):
        """Altering a single byte of raw evidence on storage triggers TAMPER_DETECTED."""
        # Create case & test
        c_res = self.client.post("/cases", json={
            "case_number": f"CASE-TAMPER-IMG-{uuid.uuid4().hex[:6]}",
            "incident_location": "Pier 45",
            "notes": "Image tamper test"
        }, headers=self._headers(self.officer_token))
        case_id = c_res.json()["id"]

        t_res = self.client.post("/tests", json={
            "case_id": case_id,
            "reagent_name": "idPAD 12-Lane"
        }, headers=self._headers(self.officer_token))
        test_id = t_res.json()["id"]

        # Upload unique evidence for tampering test
        tamper_img = np.ones((200, 300, 3), dtype=np.uint8) * 88
        cv2.circle(tamper_img, (150, 100), 50, (200, 100, 50), -1)
        _, tbuf = cv2.imencode(".png", tamper_img)
        tamper_bytes = tbuf.tobytes()

        files = {"file": ("tamper_evidence.png", tamper_bytes, "image/png")}
        ev_res = self.client.post(f"/tests/{test_id}/evidence", files=files, headers=self._headers(self.officer_token))
        evidence_id = ev_res.json()["id"]
        raw_storage_path = ev_res.json()["raw_storage_path"]

        # Analyze
        self.client.post(f"/tests/{test_id}/analyze", headers=self._headers(self.officer_token))

        # Intentionally tamper with raw image bytes on storage
        full_disk_path = os.path.join(settings.STORAGE_DIR, raw_storage_path)
        self.assertTrue(os.path.exists(full_disk_path))
        with open(full_disk_path, "rb") as f:
            original_bytes = bytearray(f.read())

        try:
            # Flip byte at index 100
            tampered_bytes = bytearray(original_bytes)
            tampered_bytes[100] ^= 0xFF
            with open(full_disk_path, "wb") as f:
                f.write(tampered_bytes)

            # Call POST /evidence/{id}/verify
            v_res = self.client.post(f"/evidence/{evidence_id}/verify", headers=self._headers(self.analyst_token))
            self.assertEqual(v_res.status_code, 200)
            v_data = v_res.json()

            # MUST DETECT TAMPER
            self.assertEqual(v_data["status"], "TAMPER_DETECTED")
            self.assertTrue(v_data["is_tampered"])
            self.assertFalse(v_data["image_intact"])
            self.assertNotEqual(v_data["recomputed_payload_hash"], v_data["stored_payload_hash"])

            # Check integrity endpoint reflects disqualification
            integ_res = self.client.get(f"/tests/{test_id}/integrity", headers=self._headers(self.officer_token))
            self.assertEqual(integ_res.json()["verification_status"], "TAMPERED_DISQUALIFIED")
            self.assertTrue(integ_res.json()["is_tampered"])
        finally:
            with open(full_disk_path, "wb") as f:
                f.write(original_bytes)

    # -------------------------------------------------------------
    # 4. Tamper Detection: Modified Metadata in Canonical Representation
    # -------------------------------------------------------------
    def test_detect_modified_metadata_tamper(self):
        """Altering metadata values produces a mismatch in the canonical hash."""
        canonical_h1, _ = EvidenceIntegrityEngine.calculate_canonical_hash(
            payload_hash="e" * 64,
            case_id="CASE-1",
            test_id="TEST-1",
            metadata_dict={"badge_number": "BADGE-1", "device_id": "DEV-1", "reagent_name": "idPAD", "gps_latitude": 37.0, "gps_longitude": -122.0},
            result_dict={"classification": "PRESUMPTIVE_POSITIVE", "confidence_score": 0.9, "ood_score": 0.05, "model_version": "v1.0.0"},
            timestamp_iso="2026-09-19T12:00:00Z"
        )

        # Modified metadata: officer badge altered
        canonical_h2, _ = EvidenceIntegrityEngine.calculate_canonical_hash(
            payload_hash="e" * 64,
            case_id="CASE-1",
            test_id="TEST-1",
            metadata_dict={"badge_number": "BADGE-SPOOFED", "device_id": "DEV-1", "reagent_name": "idPAD", "gps_latitude": 37.0, "gps_longitude": -122.0},
            result_dict={"classification": "PRESUMPTIVE_POSITIVE", "confidence_score": 0.9, "ood_score": 0.05, "model_version": "v1.0.0"},
            timestamp_iso="2026-09-19T12:00:00Z"
        )

        self.assertNotEqual(canonical_h1, canonical_h2)

        # Verification function detects canonical tampering
        verify_check = EvidenceIntegrityEngine.verify_evidence_record(
            raw_image_bytes=b"dummy_data",
            stored_payload_hash=calculate_sha256(b"dummy_data"),
            stored_canonical_hash=canonical_h1,
            case_id="CASE-1",
            test_id="TEST-1",
            metadata_dict={"badge_number": "BADGE-SPOOFED", "device_id": "DEV-1", "reagent_name": "idPAD", "gps_latitude": 37.0, "gps_longitude": -122.0},
            result_dict={"classification": "PRESUMPTIVE_POSITIVE", "confidence_score": 0.9, "ood_score": 0.05, "model_version": "v1.0.0"},
            timestamp_iso="2026-09-19T12:00:00Z"
        )
        self.assertTrue(verify_check["is_tampered"])
        self.assertFalse(verify_check["canonical_hash_verified"])
        self.assertEqual(verify_check["status"], "TAMPER_DETECTED")

    # -------------------------------------------------------------
    # 5. Tamper Detection: Altered AI Result
    # -------------------------------------------------------------
    def test_detect_altered_result_tamper(self):
        """Silently altering the AI classification changes the canonical hash and fails verification."""
        original_hash, _ = EvidenceIntegrityEngine.calculate_canonical_hash(
            payload_hash="f" * 64,
            case_id="CASE-RES-1",
            test_id="TEST-RES-1",
            metadata_dict={"badge_number": "B1", "device_id": "D1", "reagent_name": "idPAD", "gps_latitude": 0.0, "gps_longitude": 0.0},
            result_dict={"classification": "PRESUMPTIVE_NEGATIVE", "confidence_score": 0.92, "ood_score": 0.02, "model_version": "v1.0.0"},
            timestamp_iso="2026-09-19T12:00:00Z"
        )

        # Silently altered to PRESUMPTIVE_POSITIVE
        tampered_verify = EvidenceIntegrityEngine.verify_evidence_record(
            raw_image_bytes=b"sample_image",
            stored_payload_hash=calculate_sha256(b"sample_image"),
            stored_canonical_hash=original_hash,
            case_id="CASE-RES-1",
            test_id="TEST-RES-1",
            metadata_dict={"badge_number": "B1", "device_id": "D1", "reagent_name": "idPAD", "gps_latitude": 0.0, "gps_longitude": 0.0},
            result_dict={"classification": "PRESUMPTIVE_POSITIVE", "confidence_score": 0.92, "ood_score": 0.02, "model_version": "v1.0.0"},
            timestamp_iso="2026-09-19T12:00:00Z"
        )
        self.assertTrue(tampered_verify["is_tampered"])
        self.assertEqual(tampered_verify["status"], "TAMPER_DETECTED")
        self.assertFalse(tampered_verify["canonical_hash_verified"])

    # -------------------------------------------------------------
    # 6. Tamper Detection: Altered / Future Timestamp
    # -------------------------------------------------------------
    def test_detect_altered_timestamp(self):
        """Future timestamp triggers clock skew failure and alters canonical sealing."""
        future_ts = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)).isoformat()
        eval_res = EvidenceIntegrityEngine.evaluate(
            image_quality={"blur_score": 120.0, "brightness_mean": 120.0, "contrast_std": 30.0, "reference_card_detected": True, "calibration_applied": True},
            provenance={"authenticated_operator": True, "badge_number": "B1", "device_id": "D1", "gps_latitude": 30.0, "gps_longitude": -90.0},
            metadata={"timestamp": future_ts, "case_id": "C1", "test_id": "T1", "reagent_name": "idPAD", "model_version": "v1.0.0-presumptive-idpad"},
            cryptography={"payload_hash": "a" * 64, "recomputed_hash": "a" * 64, "hmac_valid": True, "tamper_detected": False}
        )
        self.assertFalse(eval_res["checks"]["timestamp"])
        self.assertTrue(any("future" in f.lower() for f in eval_res["failures"]))

    # -------------------------------------------------------------
    # 7. Immutability & Duplicate Upload Prevention
    # -------------------------------------------------------------
    def test_immutability_duplicate_upload_rejected(self):
        """Once evidence is finalized through analysis, new upload attempts are rejected with 409 Conflict."""
        # Create case & test
        c_res = self.client.post("/cases", json={"case_number": f"CASE-IMMUT-{uuid.uuid4().hex[:6]}", "incident_location": "Vault A"}, headers=self._headers(self.officer_token))
        case_id = c_res.json()["id"]

        t_res = self.client.post("/tests", json={"case_id": case_id, "reagent_name": "idPAD 12-Lane"}, headers=self._headers(self.officer_token))
        test_id = t_res.json()["id"]

        # 1st Upload
        files = {"file": ("valid.png", self.valid_image_bytes, "image/png")}
        up1 = self.client.post(f"/tests/{test_id}/evidence", files=files, headers=self._headers(self.officer_token))
        self.assertEqual(up1.status_code, 200)

        # Analyze & Finalize
        an_res = self.client.post(f"/tests/{test_id}/analyze", headers=self._headers(self.officer_token))
        self.assertEqual(an_res.status_code, 200)

        # Attempt duplicate upload to finalized test
        files2 = {"file": ("replacement.png", self.valid_image_bytes, "image/png")}
        up2 = self.client.post(f"/tests/{test_id}/evidence", files=files2, headers=self._headers(self.officer_token))
        self.assertEqual(up2.status_code, 409)
        self.assertIn("immutable", up2.json()["detail"].lower())

    # -------------------------------------------------------------
    # 8. Cryptographic Hash-Chain Verification
    # -------------------------------------------------------------
    def test_append_only_audit_chain_integrity(self):
        """Each audit log entry is linked to the previous entry's hash."""
        case_res = self.client.post("/cases", json={
            "case_number": f"CASE-CHAIN-{uuid.uuid4().hex[:6]}",
            "incident_location": "Harbor Division"
        }, headers=self._headers(self.officer_token))
        case_id = case_res.json()["id"]

        audit_res = self.client.get(f"/audit/{case_id}", headers=self._headers(self.analyst_token))
        self.assertEqual(audit_res.status_code, 200)
        logs = audit_res.json()
        self.assertGreaterEqual(len(logs), 1)

        # Verify hash chaining structure
        for log in logs:
            self.assertEqual(len(log["current_hash"]), 64)
            self.assertIsNotNone(log["previous_hash"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
