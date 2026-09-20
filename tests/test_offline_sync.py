"""
Automated Offline-First & Resilient Sync Test Suite
Digital Field Drug Evidence System

Simulates:
1. Start offline
2. Create case
3. Capture image
4. Run model locally
5. Generate evidence record
6. Close application
7. Restart application
8. Verify local data exists
9. Restore internet
10. Synchronize
11. Verify server record exists
12. Verify hash match

Tamper test:
Alter local image -> Verify SYNC_REJECTED and Audit event logged.

Plus Idempotency, Retry Resilience, and Vault Encryption Integrity tests.
"""

import os
import sys
import time
import uuid
import shutil
import base64
import unittest
import numpy as np
import cv2
from starlette.testclient import TestClient

# Ensure root directory in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.db.init_db import init_db
from backend.app.db.models import User, Case, Test, Evidence, AIResult, AuditLog, SyncRecord
from backend.app.core.security import calculate_sha256, create_access_token
from backend.app.services.evidence_integrity import EvidenceIntegrityEngine
from ml.inference import PresumptiveInferenceEngine
from offline.local_storage import EncryptedLocalStorage
from offline.sync_manager import SyncManager, SyncStatus


class TestOfflineSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        cls.test_vault_path = os.path.join(BASE_DIR, "storage", "test_offline_vault.db")
        cls.test_vault_key = EncryptedLocalStorage.generate_device_key()

        # Get Auth token for officer1
        login_resp = cls.client.post("/auth/login", json={"username": "officer1", "password": "fieldpass123"})
        if login_resp.status_code != 200:
            raise RuntimeError(f"Login failed: {login_resp.text}")
        cls.token = login_resp.json()["access_token"]
        cls.auth_headers = {"Authorization": f"Bearer {cls.token}"}

    def setUp(self):
        if os.path.exists(self.test_vault_path):
            os.remove(self.test_vault_path)

    def tearDown(self):
        if os.path.exists(self.test_vault_path):
            try:
                os.remove(self.test_vault_path)
            except OSError:
                pass

    def _create_synthetic_test_image(self) -> bytes:
        """Create a synthetic 150x150 PNG image buffer representing a field reaction."""
        img = np.zeros((150, 150, 3), dtype=np.uint8)
        img[:, :] = [40, 40, 180] # Dark reddish-orange Mandelin reaction tone
        # Draw simulated reaction circle
        cv2.circle(img, (75, 75), 45, (25, 20, 140), -1)
        cv2.putText(img, str(uuid.uuid4())[:8], (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        _, buf = cv2.imencode(".png", img)
        return buf.tobytes()

    def test_complete_12_step_offline_to_online_lifecycle(self):
        """
        Executes the explicit 12-step field offline capture, local vault persistence,
        app restart, cloud synchronization, and forensic hash verification.
        """
        # Step 1: Start offline - Initialize encrypted local vault
        store = EncryptedLocalStorage(
            db_path=self.test_vault_path,
            encryption_key=self.test_vault_key
        )
        self.assertTrue(os.path.exists(self.test_vault_path))

        # Step 2: Create case offline
        case_id = str(uuid.uuid4())
        case_num = f"CASE-OFFLINE-{int(time.time())}"
        case_data = {
            "case_number": case_num,
            "title": "Offline Narcotics Seizure Patrol",
            "description": "Vehicle stop at border checkpoint; cellular reception unavailable.",
            "created_at": "2026-09-19T10:00:00Z"
        }
        store.save_case(case_id, case_data)

        # Step 3: Create test session & Capture image offline
        test_id = str(uuid.uuid4())
        test_data = {
            "case_id": case_id,
            "test_number": "TEST-OFF-01",
            "reagent_name": "MANDELIN",
            "created_at": "2026-09-19T10:05:00Z"
        }
        store.save_test(test_id, test_data)

        raw_image_bytes = self._create_synthetic_test_image()
        payload_hash = calculate_sha256(raw_image_bytes)

        # Step 4: Run model locally
        engine = PresumptiveInferenceEngine()
        ai_res = engine.predict(raw_image_bytes)
        self.assertIn(ai_res["classification"], [
            "PRESUMPTIVE_POSITIVE", "PRESUMPTIVE_NEGATIVE",
            "INCONCLUSIVE", "UNSUPPORTED / OUT_OF_DISTRIBUTION"
        ])

        # Step 5: Generate evidence record & Evaluate Evidence Integrity Score
        device_id = "OFFLINE-TABLET-007"
        gps_lat, gps_lon = 37.7749, -122.4194
        meta_dict = {
            "badge_number": "BADGE-OFFLINE-88",
            "device_id": device_id,
            "reagent_name": "MANDELIN",
            "gps_latitude": gps_lat,
            "gps_longitude": gps_lon
        }
        now_ts = "2026-09-19T10:06:00Z"
        confidence_val = float(ai_res.get("confidence_score", ai_res.get("calibrated_confidence", ai_res.get("confidence", 0.0))))
        canonical_hash, canonical_str = EvidenceIntegrityEngine.calculate_canonical_hash(
            payload_hash=payload_hash,
            case_id=case_num,
            test_id=test_id,
            metadata_dict=meta_dict,
            result_dict={
                "classification": ai_res["classification"],
                "confidence_score": confidence_val,
                "ood_score": ai_res["ood_score"],
                "model_version": engine.config.get("model_version", "v1.0.0-presumptive-idpad")
            },
            timestamp_iso=now_ts
        )

        integrity_eval = EvidenceIntegrityEngine.evaluate(
            image_quality={
                "blur_score": 145.0,
                "brightness_mean": 130.0,
                "contrast_std": 52.0,
                "reference_card_detected": True,
                "calibration_applied": True
            },
            provenance={
                "authenticated_operator": True,
                "badge_number": "BADGE-OFFLINE-88",
                "device_id": device_id,
                "gps_latitude": gps_lat,
                "gps_longitude": gps_lon
            },
            metadata={
                "timestamp": now_ts,
                "case_id": case_num,
                "test_id": test_id,
                "reagent_name": "MANDELIN",
                "model_version": engine.config.get("model_version", "v1.0.0-presumptive-idpad"),
                "sync_status": "LOCAL_VALID"
            },
            cryptography={
                "payload_hash": payload_hash,
                "hmac_valid": True,
                "tamper_detected": False
            }
        )
        self.assertGreaterEqual(integrity_eval["score"], 80)
        self.assertEqual(integrity_eval["status"], "HIGH")

        evidence_id = str(uuid.uuid4())
        evidence_record = {
            "test_id": test_id,
            "payload_hash": payload_hash,
            "canonical_hash": canonical_hash,
            "metadata_hash": calculate_sha256(str(meta_dict).encode("utf-8")),
            "device_id": device_id,
            "gps_latitude": gps_lat,
            "gps_longitude": gps_lon,
            "integrity_score": integrity_eval["score"],
            "integrity_status": integrity_eval["status"],
            "blur_score": 145.0,
            "brightness_mean": 130.0,
            "contrast_std": 52.0,
            "card_detected": True,
            "created_at": now_ts
        }
        store.save_evidence(evidence_id, evidence_record, raw_image_bytes)

        ai_result_record = {
            "test_id": test_id,
            "evidence_id": evidence_id,
            "classification": ai_res["classification"],
            "confidence_score": confidence_val,
            "ood_score": ai_res["ood_score"],
            "model_version": engine.config.get("model_version", "v1.0.0-presumptive-idpad"),
            "disclaimer": ai_res["disclaimer"],
            "created_at": now_ts
        }
        store.save_ai_result(str(uuid.uuid4()), ai_result_record)

        # Enqueue sync item
        sync_item_id = store.enqueue_sync_item(
            resource_type="evidence_bundle",
            resource_id=evidence_id,
            payload_hash=payload_hash
        )
        self.assertTrue(sync_item_id.startswith("SYNC-"))

        # Step 6: Close application (terminate instance)
        del store
        store = None

        # Step 7: Restart application (instantiate clean new vault connection)
        store2 = EncryptedLocalStorage(
            db_path=self.test_vault_path,
            encryption_key=self.test_vault_key
        )

        # Step 8: Verify local data exists and decrypts cleanly
        restored_case = store2.get_case(case_id)
        self.assertIsNotNone(restored_case)
        self.assertEqual(restored_case["case_number"], case_num)

        restored_ev = store2.get_evidence(evidence_id)
        self.assertIsNotNone(restored_ev)
        self.assertEqual(restored_ev["payload_hash"], payload_hash)
        self.assertEqual(restored_ev["integrity_score"], integrity_eval["score"])

        restored_raw_bytes = store2.get_raw_image(payload_hash)
        self.assertEqual(restored_raw_bytes, raw_image_bytes, "Decrypted raw bytes must match original bit-for-bit")
        self.assertEqual(calculate_sha256(restored_raw_bytes), payload_hash)

        pending_items = store2.get_pending_sync_items()
        self.assertEqual(len(pending_items), 1)
        self.assertEqual(pending_items[0]["idempotency_key"], sync_item_id)
        self.assertEqual(pending_items[0]["status"], "PENDING_SYNC")

        # Step 9: Restore internet - Configure SyncManager with client API bridge
        sync_mgr = SyncManager(
            local_store=store2,
            device_id=device_id,
            max_retries=3,
            base_backoff_sec=0.1
        )

        def api_post_bridge(path: str, json_data: dict) -> dict:
            resp = self.client.post(path, json=json_data, headers=self.auth_headers)
            return resp.json()

        # Step 10: Synchronize
        sync_results = sync_mgr.sync_all_pending(api_post_bridge)
        self.assertEqual(len(sync_results), 1)
        self.assertEqual(sync_results[0]["status"], SyncStatus.SYNCED)

        # Verify local status updated to SYNCED
        updated_pending = store2.get_pending_sync_items()
        self.assertEqual(len(updated_pending), 0, "No pending items should remain")
        all_queue = store2.get_all_queue_items()
        self.assertEqual(all_queue[0]["status"], SyncStatus.SYNCED)

        # Step 11: Verify server record exists in central database
        db = SessionLocal()
        try:
            server_case = db.query(Case).filter(Case.id == case_id).first()
            self.assertIsNotNone(server_case)
            self.assertEqual(server_case.case_number, case_num)

            server_test = db.query(Test).filter(Test.id == test_id).first()
            self.assertIsNotNone(server_test)

            server_ev = db.query(Evidence).filter(Evidence.id == evidence_id).first()
            self.assertIsNotNone(server_ev)
            self.assertEqual(server_ev.verification_status, "VALID")

            server_ai = db.query(AIResult).filter(AIResult.evidence_id == evidence_id).first()
            self.assertIsNotNone(server_ai)
            self.assertEqual(server_ai.classification, ai_res["classification"])

            # Step 12: Verify hash match and disk persistence
            self.assertEqual(server_ev.payload_hash, payload_hash)
            raw_storage_full = os.path.join(BASE_DIR, "storage", server_ev.raw_storage_path)
            self.assertTrue(os.path.exists(raw_storage_full))
            with open(raw_storage_full, "rb") as f:
                server_disk_bytes = f.read()
            self.assertEqual(calculate_sha256(server_disk_bytes), payload_hash)

            # Verify audit trail contains OFFLINE_SYNC_COMMITTED
            audit_entry = db.query(AuditLog).filter(
                AuditLog.case_id == case_id,
                AuditLog.action == "OFFLINE_SYNC_COMMITTED"
            ).first()
            self.assertIsNotNone(audit_entry)
            self.assertEqual(audit_entry.resource_id, evidence_id)
        finally:
            db.close()

    def test_tamper_detection_triggers_sync_rejected(self):
        """
        Tamper test:
        An adversary or transmission corruption alters the raw image bytes while leaving
        the original claimed payload_hash unchanged.
        Verify:
        - Server verification rejects the sync with SYNC_REJECTED
        - Status is set to VERIFICATION_FAILED
        - SYNC_TAMPER_REJECTED audit event is logged in backend.
        """
        store = EncryptedLocalStorage(
            db_path=self.test_vault_path,
            encryption_key=self.test_vault_key
        )

        case_id = str(uuid.uuid4())
        case_num = f"CASE-TAMPER-{int(time.time())}"
        store.save_case(case_id, {
            "case_number": case_num,
            "title": "Tamper Test Case",
            "created_at": "2026-09-19T11:00:00Z"
        })

        test_id = str(uuid.uuid4())
        store.save_test(test_id, {
            "case_id": case_id,
            "test_number": "TEST-TAMP-01",
            "reagent_name": "MARQUIS",
            "created_at": "2026-09-19T11:01:00Z"
        })

        # Original legitimate image
        original_bytes = self._create_synthetic_test_image()
        claimed_hash = calculate_sha256(original_bytes)

        ev_id = str(uuid.uuid4())
        store.save_evidence(ev_id, {
            "test_id": test_id,
            "payload_hash": claimed_hash,
            "canonical_hash": "CANONICAL-DUMMY",
            "integrity_score": 92,
            "integrity_status": "HIGH",
            "created_at": "2026-09-19T11:02:00Z"
        }, original_bytes)

        sync_key = store.enqueue_sync_item("evidence_bundle", ev_id, claimed_hash)

        # TAMPER INJECTION: Modify raw bytes in local vault directly to simulate tampering
        tampered_bytes = original_bytes + b"_MALICIOUS_TAMPER_INJECTION_"
        # Replace image in local encrypted DB with tampered bytes while keeping claimed_hash
        enc_tampered = store.cipher.encrypt(tampered_bytes)
        with store._get_connection() as conn:
            conn.execute(
                "UPDATE offline_evidence SET encrypted_image_bytes = ? WHERE payload_hash = ?",
                (enc_tampered, claimed_hash)
            )
            conn.commit()

        # Connect SyncManager
        sync_mgr = SyncManager(
            local_store=store,
            device_id="TAMPER-TEST-DEVICE",
            max_retries=1,
            base_backoff_sec=0.05
        )

        def api_post_bridge(path: str, json_data: dict) -> dict:
            resp = self.client.post(path, json=json_data, headers=self.auth_headers)
            return resp.json()

        sync_results = sync_mgr.sync_all_pending(api_post_bridge)
        self.assertEqual(len(sync_results), 1)

        # Must be rejected with VERIFICATION_FAILED
        res = sync_results[0]
        self.assertEqual(res["status"], SyncStatus.VERIFICATION_FAILED)
        self.assertIn("mismatch", res["error"].lower())

        # Check queue status in local store
        queue_item = store.get_all_queue_items()[0]
        self.assertEqual(queue_item["status"], SyncStatus.VERIFICATION_FAILED)

        # Verify backend recorded tamper audit event
        db = SessionLocal()
        try:
            tamper_log = db.query(AuditLog).filter(
                AuditLog.action == "SYNC_TAMPER_REJECTED",
                AuditLog.resource_id == ev_id
            ).first()
            self.assertIsNotNone(tamper_log, "Server must log SYNC_TAMPER_REJECTED audit event")
            self.assertEqual(tamper_log.action, "SYNC_TAMPER_REJECTED")
        finally:
            db.close()

    def test_idempotency_duplicate_prevention(self):
        """
        Verify that re-submitting an already synced bundle does not create duplicate
        database records, and safely reports ALREADY_SYNCED / SYNCED.
        """
        store = EncryptedLocalStorage(
            db_path=self.test_vault_path,
            encryption_key=self.test_vault_key
        )
        case_id = str(uuid.uuid4())
        test_id = str(uuid.uuid4())
        ev_id = str(uuid.uuid4())
        raw_bytes = self._create_synthetic_test_image()
        p_hash = calculate_sha256(raw_bytes)

        store.save_case(case_id, {"case_number": f"IDEM-CASE-{int(time.time())}"})
        store.save_test(test_id, {"case_id": case_id, "test_number": "TEST-01", "reagent_name": "MANDELIN"})
        store.save_evidence(ev_id, {
            "test_id": test_id,
            "payload_hash": p_hash,
            "created_at": "2026-09-19T12:00:00Z"
        }, raw_bytes)

        key1 = store.enqueue_sync_item("evidence_bundle", ev_id, p_hash)

        sync_mgr = SyncManager(store, "DEVICE-IDEM", max_retries=1)
        res1 = sync_mgr.sync_all_pending(lambda p, j: self.client.post(p, json=j, headers=self.auth_headers).json())
        self.assertEqual(res1[0]["status"], SyncStatus.SYNCED)

        # Enqueue same bundle again with a new idempotency key
        key2 = store.enqueue_sync_item("evidence_bundle", ev_id, p_hash)
        res2 = sync_mgr.sync_all_pending(lambda p, j: self.client.post(p, json=j, headers=self.auth_headers).json())
        self.assertEqual(res2[0]["status"], SyncStatus.SYNCED)

        # Check DB evidence count for this hash
        db = SessionLocal()
        try:
            count = db.query(Evidence).filter(Evidence.payload_hash == p_hash).count()
            self.assertEqual(count, 1, "Duplicate evidence record must not be created")
        finally:
            db.close()

    def test_exponential_backoff_and_retry_resilience(self):
        """
        Simulate a flaky network where the first 2 attempts fail with connection error
        and the 3rd attempt succeeds.
        """
        store = EncryptedLocalStorage(
            db_path=self.test_vault_path,
            encryption_key=self.test_vault_key
        )
        case_id = str(uuid.uuid4())
        test_id = str(uuid.uuid4())
        ev_id = str(uuid.uuid4())
        raw_bytes = self._create_synthetic_test_image()
        p_hash = calculate_sha256(raw_bytes)

        store.save_case(case_id, {"case_number": f"RETRY-CASE-{int(time.time())}"})
        store.save_test(test_id, {"case_id": case_id, "test_number": "TEST-RETRY", "reagent_name": "MANDELIN"})
        store.save_evidence(ev_id, {"test_id": test_id, "payload_hash": p_hash, "created_at": "2026-09-19T12:00:00Z"}, raw_bytes)
        store.enqueue_sync_item("evidence_bundle", ev_id, p_hash)

        sync_mgr = SyncManager(store, "DEVICE-RETRY", max_retries=3, base_backoff_sec=0.05)

        attempts = [0]

        def flaky_api_post(path: str, json_data: dict) -> dict:
            attempts[0] += 1
            if attempts[0] < 3:
                raise ConnectionResetError("Simulated intermittent network drop")
            resp = self.client.post(path, json=json_data, headers=self.auth_headers)
            return resp.json()

        res = sync_mgr.sync_all_pending(flaky_api_post)
        self.assertEqual(attempts[0], 3, "Should have retried exactly 3 times")
        self.assertEqual(res[0]["status"], SyncStatus.SYNCED)

    def test_encrypted_vault_key_security(self):
        """
        Verify that encrypted local storage data cannot be decrypted with an invalid key.
        """
        store1 = EncryptedLocalStorage(
            db_path=self.test_vault_path,
            encryption_key=self.test_vault_key
        )
        raw_bytes = b"SECRET_OFFLINE_EVIDENCE_PAYLOAD"
        p_hash = calculate_sha256(raw_bytes)
        store1.save_evidence("ev-secret-1", {"payload_hash": p_hash, "test_id": "t1"}, raw_bytes)
        del store1

        # Attempt to open with wrong key
        wrong_key = EncryptedLocalStorage.generate_device_key()
        store_wrong = EncryptedLocalStorage(
            db_path=self.test_vault_path,
            encryption_key=wrong_key
        )

        with self.assertRaises(Exception):
            store_wrong.get_raw_image(p_hash)


if __name__ == "__main__":
    unittest.main()
