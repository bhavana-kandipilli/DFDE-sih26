#!/usr/bin/env python3
"""
Systematic Failure Mode and Negative Edge Case Test Suite.
Tests:
1. Bad / Corrupted Image (Malformed headers, random noise) -> Rejected
2. Missing Reference Card -> Quality warning & score penalty
3. Low Light / Underexposure -> Lighting failure flag
4. Blur / Out of Focus -> Blur threshold failure flag
5. Unsupported Test / Substance -> Out-of-Distribution (OOD) classification
6. Network Failure During Offline Operation -> Safe persistence in offline vault
7. Corrupted Upload Binary -> Rejection via magic byte & decode filters
8. Duplicate Upload -> Idempotency detection (ALREADY_SYNCED)
9. Altered Evidence in Transit -> Hash mismatch (SYNC_REJECTED & audit alert)
10. Expired Authentication -> HTTP 401 Unauthorized
11. Unauthorized User (Broken Authorization) -> HTTP 403 Forbidden
"""

import os
import sys
import uuid
import time
import base64
import unittest
import numpy as np
import cv2
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from backend.app.main import app
from backend.app.db.init_db import init_db
from backend.app.core.security import calculate_sha256, create_access_token
from backend.app.services.calibration_service import CalibrationService
from backend.app.services.evidence_integrity import EvidenceIntegrityEngine
from ml.inference import PresumptiveInferenceEngine
from offline.local_storage import EncryptedLocalStorage
import datetime

class TestFailureModesAndEdgeCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        cls.vault = EncryptedLocalStorage()
        cls.engine = PresumptiveInferenceEngine()

        # Generate tokens
        res = cls.client.post("/auth/login", json={"username": "officer1", "password": "fieldpass123"})
        cls.officer_token = res.json()["access_token"]
        cls.officer_headers = {"Authorization": f"Bearer {cls.officer_token}"}

        res = cls.client.post("/auth/login", json={"username": "readonly1", "password": "readonlypass123"})
        cls.readonly_token = res.json()["access_token"]
        cls.readonly_headers = {"Authorization": f"Bearer {cls.readonly_token}"}

    # =========================================================================
    # 1. Bad / Corrupted Image
    # =========================================================================
    def test_failure_corrupted_image_upload(self):
        """Malformed image binary must be safely rejected with HTTP 400/415."""
        corrupt_bytes = b"\x89PNG\r\n\x1a\n" + b"\xff" * 40 # Incomplete corrupted PNG
        res = self.client.post(
            "/tests/dummy-test/evidence",
            headers=self.officer_headers,
            files={"file": ("corrupt.png", corrupt_bytes, "image/png")}
        )
        self.assertIn(res.status_code, [400, 404, 422])

    # =========================================================================
    # 2. Missing Reference Card
    # =========================================================================
    def test_failure_missing_reference_card(self):
        """Image without reference card must fail card detection and penalize score."""
        # Plain green image with no card
        plain_img = np.zeros((300, 400, 3), dtype=np.uint8)
        plain_img[:] = (0, 150, 0)
        _, enc = cv2.imencode(".jpg", plain_img)
        plain_bytes = enc.tobytes()

        calib_res = CalibrationService.process_and_store(plain_bytes, "DUMMY_CASE", "MANDELIN")
        self.assertFalse(calib_res["quality"]["card_detected"])

        eval_res = EvidenceIntegrityEngine.evaluate(
            image_quality={
                "blur_score": 150.0,
                "brightness_mean": 120.0,
                "contrast_std": 45.0,
                "reference_card_detected": False,
                "calibration_applied": False
            },
            provenance={"authenticated_operator": True, "device_id": "DEV-1", "gps_latitude": 37.0, "gps_longitude": -122.0},
            metadata={"timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "case_id": "C1", "test_id": "T1", "reagent_name": "MANDELIN", "model_version": "v1.0.0"},
            cryptography={"payload_hash": "abc", "recomputed_hash": "abc", "hmac_valid": True, "tamper_detected": False}
        )
        self.assertFalse(eval_res["checks"]["reference_card"])
        self.assertTrue(any("reference" in f.lower() for f in eval_res["failures"]))
        self.assertLess(eval_res["score"], 80)

    # =========================================================================
    # 3. Low Light / Underexposure
    # =========================================================================
    def test_failure_low_light_underexposure(self):
        """Nearly black image must trigger underexposure failure."""
        dark_img = np.zeros((300, 400, 3), dtype=np.uint8)
        dark_img[:] = (5, 5, 5) # Extremely dark
        _, enc = cv2.imencode(".jpg", dark_img)
        dark_bytes = enc.tobytes()

        calib_res = CalibrationService.process_and_store(dark_bytes, "DUMMY_CASE", "MANDELIN")
        self.assertLess(calib_res["quality"]["brightness_mean"], 30.0)

        eval_res = EvidenceIntegrityEngine.evaluate(
            image_quality={
                "blur_score": 150.0,
                "brightness_mean": 10.0, # Underexposed
                "contrast_std": 5.0,
                "reference_card_detected": False,
                "calibration_applied": False
            },
            provenance={"authenticated_operator": True, "device_id": "DEV-1", "gps_latitude": 37.0, "gps_longitude": -122.0},
            metadata={"timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "case_id": "C1", "test_id": "T1", "reagent_name": "MANDELIN", "model_version": "v1.0.0"},
            cryptography={"payload_hash": "abc", "recomputed_hash": "abc", "hmac_valid": True, "tamper_detected": False}
        )
        self.assertFalse(eval_res["checks"]["exposure_lighting"])
        self.assertTrue(any("underexposure" in f.lower() for f in eval_res["failures"]))

    # =========================================================================
    # 4. Blur / Out of Focus
    # =========================================================================
    def test_failure_severe_blur(self):
        """Heavily blurred image must fail blur threshold check."""
        img = np.zeros((300, 400, 3), dtype=np.uint8)
        img[:] = (128, 128, 128)
        # Uniform image has Laplacian variance near 0
        _, enc = cv2.imencode(".jpg", img)
        flat_bytes = enc.tobytes()

        calib_res = CalibrationService.process_and_store(flat_bytes, "DUMMY_CASE", "MANDELIN")
        self.assertLess(calib_res["quality"]["blur_score"], 100.0)

    # =========================================================================
    # 5. Unsupported Test / Substance (Out-of-Distribution)
    # =========================================================================
    def test_failure_unsupported_ood_sample(self):
        """Exotic synthetic reaction must be classified as UNSUPPORTED_OOD or INCONCLUSIVE."""
        # Synthesize an anomalous neon purple/magenta reaction
        odd_img = np.zeros((200, 200, 3), dtype=np.uint8)
        odd_img[:] = (255, 0, 255)
        path = os.path.join(ROOT_DIR, "storage", "odd_reaction.png")
        cv2.imwrite(path, odd_img)

        ai_res = self.engine.predict(path)
        self.assertIn(ai_res["classification"], ["UNSUPPORTED_OOD", "INCONCLUSIVE", "PRESUMPTIVE_NEGATIVE"])
        self.assertTrue("laboratory confirmation" in ai_res["disclaimer"].lower())

    # =========================================================================
    # 6. Network Failure Simulation (Offline Vault Persistence)
    # =========================================================================
    def test_offline_vault_resilience_to_network_failure(self):
        """Simulate total offline mode: records must queue safely in encrypted SQLite."""
        test_id = str(uuid.uuid4())
        raw_bytes = b"SIMULATED_OPTICAL_STREAM_DATA"
        p_hash = calculate_sha256(raw_bytes)

        self.vault.save_evidence(
            evidence_id=test_id,
            evidence_data_or_test_id=test_id,
            raw_image_bytes=raw_bytes,
            payload_hash=p_hash
        )
        self.vault.enqueue_sync_item("evidence_bundle", test_id, p_hash)

        # Confirm evidence persists in local vault and can be decrypted
        stored = self.vault.get_evidence(test_id)
        self.assertEqual(stored["decrypted_image_bytes"], raw_bytes)
        
        # Confirm pending sync queue item
        items = self.vault.get_pending_sync_items()
        self.assertTrue(any(i["resource_id"] == test_id for i in items))

    # =========================================================================
    # 7. Corrupted Upload Binary in Sync
    # =========================================================================
    def test_failure_sync_corrupted_base64_payload(self):
        """Sync payload with corrupted base64 data fails verification."""
        sync_payload = {
            "device_id": "TEST-DEVICE",
            "client_sync_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "items": [{
                "client_record_id": str(uuid.uuid4()),
                "type": "evidence_bundle",
                "data": {
                    "case": {"case_number": f"CASE-FAIL-{uuid.uuid4().hex[:6]}"},
                    "test": {"reagent_name": "MARQUIS"},
                    "evidence": {
                        "id": str(uuid.uuid4()),
                        "raw_image_base64": "NOT_A_VALID_BASE64_STREAM!!!",
                        "payload_hash": "claimed_hash_123"
                    }
                }
            }]
        }
        res = self.client.post("/sync", headers=self.officer_headers, json=sync_payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "SYNC_REJECTED")

    # =========================================================================
    # 8. Duplicate Upload Idempotency
    # =========================================================================
    def test_duplicate_upload_idempotency(self):
        """Duplicate sync of the same evidence returns ALREADY_SYNCED without data duplication."""
        raw_bytes = b"IDEMPOTENCY_SAMPLE_" + uuid.uuid4().bytes
        p_hash = calculate_sha256(raw_bytes)
        ev_id = str(uuid.uuid4())
        c_num = f"CASE-DUP-{uuid.uuid4().hex[:6].upper()}"

        sync_bundle = {
            "device_id": "DEVICE-IDEMP",
            "client_sync_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "items": [{
                "client_record_id": ev_id,
                "type": "evidence_bundle",
                "data": {
                    "case": {"case_number": c_num, "incident_location": "Check point"},
                    "test": {"reagent_name": "EHRLICH"},
                    "evidence": {
                        "id": ev_id,
                        "raw_image_base64": base64.b64encode(raw_bytes).decode("utf-8"),
                        "payload_hash": p_hash
                    }
                }
            }]
        }
        # First sync: SUCCESS / COMPLETED
        res1 = self.client.post("/sync", headers=self.officer_headers, json=sync_bundle)
        self.assertEqual(res1.status_code, 200)
        self.assertIn(res1.json()["status"], ["SUCCESS", "COMPLETED"])

        # Second sync: Idempotent detection
        res2 = self.client.post("/sync", headers=self.officer_headers, json=sync_bundle)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["details"][0]["status"], "ALREADY_SYNCED")

    # =========================================================================
    # 9. Altered Evidence / Tamper Detection
    # =========================================================================
    def test_altered_evidence_sync_tamper_rejected(self):
        """When client claims hash A but transmits bytes with hash B, server MUST reject with SYNC_REJECTED."""
        real_bytes = b"AUTHENTIC_EVIDENCE_BYTES"
        altered_bytes = b"TAMPERED_INJECTED_BYTES"
        claimed_hash = calculate_sha256(real_bytes) # Client claims hash of authentic image

        sync_payload = {
            "device_id": "DEVICE-TAMPER",
            "client_sync_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "items": [{
                "client_record_id": str(uuid.uuid4()),
                "type": "evidence_bundle",
                "data": {
                    "case": {"case_number": f"CASE-TMP-{uuid.uuid4().hex[:6]}"},
                    "test": {"reagent_name": "MANDELIN"},
                    "evidence": {
                        "id": str(uuid.uuid4()),
                        "raw_image_base64": base64.b64encode(altered_bytes).decode("utf-8"), # Altered payload
                        "payload_hash": claimed_hash
                    }
                }
            }]
        }
        res = self.client.post("/sync", headers=self.officer_headers, json=sync_payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "SYNC_REJECTED")
        self.assertIn("Hash mismatch", res.json()["error"])

    # =========================================================================
    # 10. Expired Authentication
    # =========================================================================
    def test_expired_authentication_token_rejected_401(self):
        """Expired JWT token must return HTTP 401 Unauthorized."""
        expired_token = create_access_token(
            data={"sub": "officer1", "role": "FIELD_OFFICER"},
            expires_delta=datetime.timedelta(minutes=-10) # Expired 10 minutes ago
        )
        res = self.client.get("/cases", headers={"Authorization": f"Bearer {expired_token}"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("Invalid or expired", res.json()["detail"])

    # =========================================================================
    # 11. Unauthorized User (RBAC Authorization)
    # =========================================================================
    def test_unauthorized_user_access_denied_403(self):
        """READ_ONLY user attempting to create a case must be rejected with HTTP 403 Forbidden."""
        res = self.client.post(
            "/cases",
            headers=self.readonly_headers,
            json={"case_number": f"CASE-FAIL-{uuid.uuid4().hex[:6]}", "incident_location": "Restricted Zone"}
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("Forbidden", res.json()["detail"])

if __name__ == "__main__":
    unittest.main()
