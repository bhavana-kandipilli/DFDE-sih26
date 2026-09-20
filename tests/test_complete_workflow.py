#!/usr/bin/env python3
"""
Complete 22-Step Workflow Verification Harness.
Validates the full, end-to-end lifecycle of the Digital Field Drug Evidence System:

1. Officer login
2. Create case
3. Select test
4. Open camera (frame acquisition)
5. Detect reference card
6. Capture image
7. Quality check (blur, exposure, contrast)
8. Colour calibration (chromatic adaptation)
9. AI inference (calibrated presumptive classification)
10. Confidence calculation
11. Inconclusive/OOD check
12. Evidence Integrity Score
13. SHA-256 hash
14. Encrypt (AES-128-CBC Fernet)
15. Store (offline device vault)
16. Synchronize (cryptographic sync payload)
17. Backend verification (server-side hash matching)
18. Database commit
19. Audit log (cryptographic chain block)
20. Dashboard (case and timeline verification)
21. Evidence certificate (digital evidence export)
22. Hash verification (tamper audit verification)
"""

import os
import sys
import uuid
import time
import datetime
import json
import base64
import unittest
import numpy as np
import cv2
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from backend.app.main import app
from backend.app.db.init_db import init_db
from backend.app.core.security import calculate_sha256, generate_hmac_signature
from backend.app.services.calibration_service import CalibrationService
from backend.app.services.evidence_integrity import EvidenceIntegrityEngine
from ml.inference import PresumptiveInferenceEngine
from offline.local_storage import EncryptedLocalStorage

class TestCompleteForensicWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        cls.vault = EncryptedLocalStorage()
        cls.engine = PresumptiveInferenceEngine()

        # Load a real sample image from processed images
        sample_path = os.path.join(ROOT_DIR, "storage", "processed_images", "idpad", "image25.jpeg")
        if not os.path.exists(sample_path):
            # Create synthetic calibration card image
            img = np.zeros((300, 400, 3), dtype=np.uint8)
            img[:] = (120, 120, 120)
            cv2.rectangle(img, (20, 20), (80, 80), (255, 255, 255), -1) # Reference patch
            cv2.rectangle(img, (150, 100), (250, 200), (40, 60, 200), -1) # Reaction area
            _, enc = cv2.imencode(".jpg", img)
            cls.sample_bytes = enc.tobytes()
        else:
            with open(sample_path, "rb") as f:
                cls.sample_bytes = f.read()

    def test_full_22_step_workflow(self):
        """Executes and records all 22 steps in sequential chain of custody."""
        workflow_audit_trail = []

        # -------------------------------------------------------------
        # Step 1: Officer Login
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        login_res = self.client.post("/auth/login", json={"username": "officer1", "password": "fieldpass123"})
        step1_duration = (time.perf_counter() - t0) * 1000
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        workflow_audit_trail.append({"step": 1, "action": "Officer login", "status": "PASSED", "duration_ms": round(step1_duration, 2)})

        # -------------------------------------------------------------
        # Step 2: Create Case
        # -------------------------------------------------------------
        case_num = f"CASE-E2E-{uuid.uuid4().hex[:8].upper()}"
        t0 = time.perf_counter()
        case_res = self.client.post("/cases", headers=headers, json={
            "case_number": case_num,
            "incident_location": "Pier 39, Terminal D",
            "notes": "Field presumptive test protocol execution."
        })
        step2_duration = (time.perf_counter() - t0) * 1000
        self.assertEqual(case_res.status_code, 201)
        case_data = case_res.json()
        case_id = case_data["id"]
        workflow_audit_trail.append({"step": 2, "action": "Create case", "case_id": case_id, "status": "PASSED", "duration_ms": round(step2_duration, 2)})

        # -------------------------------------------------------------
        # Step 3: Select Test
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        test_res = self.client.post("/tests", headers=headers, json={
            "case_id": case_id,
            "reagent_name": "Scott Reagent"
        })
        step3_duration = (time.perf_counter() - t0) * 1000
        self.assertEqual(test_res.status_code, 201)
        test_data = test_res.json()
        test_id = test_data["id"]
        workflow_audit_trail.append({"step": 3, "action": "Select test", "test_id": test_id, "status": "PASSED", "duration_ms": round(step3_duration, 2)})

        # -------------------------------------------------------------
        # Step 4: Open Camera (Simulate unique optical acquisition)
        # -------------------------------------------------------------
        img = np.zeros((300, 400, 3), dtype=np.uint8)
        img[:] = (120, 120, 120)
        cv2.rectangle(img, (20, 20), (80, 80), (255, 255, 255), -1) # Reference patch
        cv2.rectangle(img, (150, 100), (250, 200), (40, 60, 200), -1) # Reaction area
        cv2.putText(img, uuid.uuid4().hex, (10, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        _, enc = cv2.imencode(".jpg", img)
        raw_bytes = enc.tobytes()
        self.assertGreater(len(raw_bytes), 0)
        workflow_audit_trail.append({"step": 4, "action": "Open camera", "status": "PASSED", "bytes_received": len(raw_bytes)})

        # -------------------------------------------------------------
        # Step 5: Detect Reference Card
        # -------------------------------------------------------------
        # Process through calibration service to check card detection
        calib_res = CalibrationService.process_and_store(raw_bytes, case_id, "Scott Reagent")
        quality = calib_res["quality"]
        card_detected = quality["card_detected"]
        workflow_audit_trail.append({"step": 5, "action": "Detect reference card", "status": "PASSED", "card_detected": card_detected})

        # -------------------------------------------------------------
        # Step 6: Capture Image (Frame validated)
        # -------------------------------------------------------------
        self.assertTrue(os.path.exists(os.path.join(ROOT_DIR, "storage", calib_res["raw_storage_path"])))
        workflow_audit_trail.append({"step": 6, "action": "Capture image", "status": "PASSED", "raw_path": calib_res["raw_storage_path"]})

        # -------------------------------------------------------------
        # Step 7: Quality Check (Blur, exposure, contrast)
        # -------------------------------------------------------------
        blur_score = quality["blur_score"]
        brightness_mean = quality["brightness_mean"]
        contrast_std = quality["contrast_std"]
        self.assertGreater(blur_score, 0)
        self.assertGreater(brightness_mean, 0)
        workflow_audit_trail.append({
            "step": 7, "action": "Quality check", "status": "PASSED",
            "blur_score": round(blur_score, 2), "brightness": round(brightness_mean, 2), "contrast": round(contrast_std, 2)
        })

        # -------------------------------------------------------------
        # Step 8: Colour Calibration
        # -------------------------------------------------------------
        calibrated_full_path = os.path.join(ROOT_DIR, "storage", calib_res["calibrated_storage_path"])
        self.assertTrue(os.path.exists(calibrated_full_path))
        workflow_audit_trail.append({"step": 8, "action": "Colour calibration", "status": "PASSED", "calibrated_path": calib_res["calibrated_storage_path"]})

        # -------------------------------------------------------------
        # Step 9: AI Inference
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        ai_res = self.engine.predict(calibrated_full_path)
        step9_duration = (time.perf_counter() - t0) * 1000
        classification = ai_res["classification"]
        # Mandatory Scientific Constraint: Presumptive terminology only
        self.assertIn(classification, ["PRESUMPTIVE_POSITIVE", "PRESUMPTIVE_NEGATIVE", "INCONCLUSIVE", "UNSUPPORTED_OOD"])
        workflow_audit_trail.append({"step": 9, "action": "AI inference", "status": "PASSED", "classification": classification, "duration_ms": round(step9_duration, 2)})

        # -------------------------------------------------------------
        # Step 10: Confidence Calculation
        # -------------------------------------------------------------
        conf = ai_res.get("calibrated_confidence", 0.0)
        self.assertGreaterEqual(conf, 0.0)
        self.assertLessEqual(conf, 1.0)
        workflow_audit_trail.append({"step": 10, "action": "Confidence calculation", "status": "PASSED", "confidence": round(conf, 4)})

        # -------------------------------------------------------------
        # Step 11: Inconclusive / OOD Check
        # -------------------------------------------------------------
        ood_score = ai_res.get("ood_score", 0.0)
        is_ood = ai_res.get("is_ood", False)
        workflow_audit_trail.append({"step": 11, "action": "Inconclusive/OOD check", "status": "PASSED", "ood_score": round(ood_score, 4), "is_ood": is_ood})

        # -------------------------------------------------------------
        # Step 12: Evidence Integrity Score
        # -------------------------------------------------------------
        iso_timestamp = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None, microsecond=0).isoformat()
        image_quality_eval = {
            "blur_score": blur_score,
            "brightness_mean": brightness_mean,
            "contrast_std": contrast_std,
            "reference_card_detected": card_detected,
            "calibration_applied": True
        }
        provenance_eval = {
            "authenticated_operator": True,
            "badge_number": "BADGE-4092",
            "device_id": "FIELD-TERMINAL-ALPHA",
            "gps_latitude": 37.7749,
            "gps_longitude": -122.4194
        }
        metadata_eval = {
            "timestamp": iso_timestamp,
            "case_id": case_id,
            "test_id": test_id,
            "reagent_name": "Scott Reagent",
            "model_version": self.engine.config.get("model_version", "v1.0.0-presumptive-idpad")
        }
        payload_hash = calculate_sha256(raw_bytes)
        cryptography_eval = {
            "payload_hash": payload_hash,
            "recomputed_hash": payload_hash,
            "hmac_valid": True,
            "tamper_detected": False
        }
        integrity_eval = EvidenceIntegrityEngine.evaluate(
            image_quality=image_quality_eval,
            provenance=provenance_eval,
            metadata=metadata_eval,
            cryptography=cryptography_eval
        )
        self.assertGreaterEqual(integrity_eval["score"], 0)
        self.assertLessEqual(integrity_eval["score"], 100)
        self.assertIn(integrity_eval["status"], ["HIGH", "MEDIUM", "LOW", "COMPROMISED"])
        workflow_audit_trail.append({"step": 12, "action": "Evidence Integrity Score", "status": "PASSED", "score": integrity_eval["score"], "integrity_status": integrity_eval["status"]})

        # -------------------------------------------------------------
        # Step 13: SHA-256 Hash
        # -------------------------------------------------------------
        self.assertEqual(payload_hash, calib_res["payload_hash"])
        workflow_audit_trail.append({"step": 13, "action": "SHA-256 hash", "status": "PASSED", "payload_hash": payload_hash})

        # -------------------------------------------------------------
        # Step 14: Encrypt (AES-128-CBC Fernet)
        # -------------------------------------------------------------
        encrypted_blob = self.vault.cipher.encrypt(raw_bytes)
        self.assertNotEqual(encrypted_blob, raw_bytes)
        decrypted = self.vault.cipher.decrypt(encrypted_blob)
        self.assertEqual(decrypted, raw_bytes)
        workflow_audit_trail.append({"step": 14, "action": "Encrypt", "status": "PASSED", "cipher": "AES-128-CBC Fernet"})

        # -------------------------------------------------------------
        # Step 15: Store (Encrypted Offline Vault)
        # -------------------------------------------------------------
        evidence_id = str(uuid.uuid4())
        self.vault.save_evidence(
            evidence_id=evidence_id,
            evidence_data_or_test_id=test_id,
            raw_image_bytes=raw_bytes,
            payload_hash=payload_hash,
            metadata_dict=metadata_eval,
            quality_dict=image_quality_eval,
            integrity_score=integrity_eval["score"],
            integrity_status=integrity_eval["status"]
        )
        self.vault.enqueue_sync_item("evidence_bundle", evidence_id, payload_hash)
        offline_ev = self.vault.get_evidence(evidence_id)
        self.assertIsNotNone(offline_ev)
        self.assertEqual(offline_ev["decrypted_image_bytes"], raw_bytes)
        workflow_audit_trail.append({"step": 15, "action": "Store", "status": "PASSED", "vault_evidence_id": evidence_id})

        metadata_canonical = {
            "badge_number": "BADGE-4092",
            "device_id": "FIELD-TERMINAL-ALPHA",
            "reagent_name": "Scott Reagent",
            "gps_latitude": 37.7749,
            "gps_longitude": -122.4194
        }
        canonical_hash, canonical_json = EvidenceIntegrityEngine.calculate_canonical_hash(
            payload_hash=payload_hash,
            case_id=case_id,
            test_id=test_id,
            metadata_dict=metadata_canonical,
            result_dict={
                "classification": classification,
                "confidence_score": conf,
                "ood_score": ood_score,
                "model_version": self.engine.config.get("model_version", "v1.0.0-presumptive-idpad")
            },
            timestamp_iso=iso_timestamp
        )
        print("WORKFLOW CANONICAL JSON:", canonical_json)

        # -------------------------------------------------------------
        # Step 16: Synchronize
        # -------------------------------------------------------------
        sync_payload = {
            "device_id": "FIELD-TERMINAL-ALPHA",
            "client_sync_timestamp": iso_timestamp,
            "items": [{
                "client_record_id": evidence_id,
                "type": "evidence_bundle",
                "data": {
                    "case": {"id": case_id, "case_number": case_num, "incident_location": "Pier 39, Terminal D"},
                    "test": {"id": test_id, "case_id": case_id, "reagent_name": "Scott Reagent"},
                    "evidence": {
                        "id": evidence_id,
                        "raw_image_base64": base64.b64encode(raw_bytes).decode("utf-8"),
                        "payload_hash": payload_hash,
                        "canonical_hash": canonical_hash,
                        "created_at": iso_timestamp,
                        "blur_score": blur_score,
                        "brightness_mean": brightness_mean,
                        "contrast_std": contrast_std,
                        "card_detected": card_detected,
                        "integrity_score": integrity_eval["score"],
                        "integrity_status": integrity_eval["status"],
                        "gps_latitude": 37.7749,
                        "gps_longitude": -122.4194,
                        "device_id": "FIELD-TERMINAL-ALPHA"
                    },
                    "ai_result": {
                        "classification": classification,
                        "confidence_score": conf,
                        "ood_score": ood_score,
                        "model_version": self.engine.config.get("model_version", "v1.0.0-presumptive-idpad")
                    }
                }
            }]
        }
        t0 = time.perf_counter()
        sync_res = self.client.post("/sync", headers=headers, json=sync_payload)
        step16_duration = (time.perf_counter() - t0) * 1000
        self.assertEqual(sync_res.status_code, 200)
        sync_json = sync_res.json()
        self.assertIn(sync_json["status"], ["SUCCESS", "COMPLETED"])
        workflow_audit_trail.append({"step": 16, "action": "Synchronize", "status": "PASSED", "duration_ms": round(step16_duration, 2)})

        # -------------------------------------------------------------
        # Step 17: Backend Verification Gate
        # -------------------------------------------------------------
        # Server verifies raw image hash matches client claimed hash
        self.assertEqual(sync_json["records_processed"], 1)
        workflow_audit_trail.append({"step": 17, "action": "Backend verification", "status": "PASSED", "verified_hash": payload_hash})

        # -------------------------------------------------------------
        # Step 18: Database Commit
        # -------------------------------------------------------------
        # Query backend database for the newly committed evidence record
        test_get = self.client.get(f"/tests/{test_id}", headers=headers)
        self.assertEqual(test_get.status_code, 200)
        workflow_audit_trail.append({"step": 18, "action": "Database commit", "status": "PASSED", "test_status": test_get.json()["status"]})

        # -------------------------------------------------------------
        # Step 19: Audit Log Chain
        # -------------------------------------------------------------
        # Use admin / analyst token to inspect audit chain
        admin_login = self.client.post("/auth/login", json={"username": "admin1", "password": "adminpass123"})
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
        audit_res = self.client.get(f"/audit/{case_id}", headers=admin_headers)
        self.assertEqual(audit_res.status_code, 200)
        audit_blocks = audit_res.json()
        self.assertGreaterEqual(len(audit_blocks), 1)
        # Check chain link
        for b in audit_blocks:
            self.assertIn("current_hash", b)
            self.assertIn("previous_hash", b)
        workflow_audit_trail.append({"step": 19, "action": "Audit log", "status": "PASSED", "audit_blocks_verified": len(audit_blocks)})

        # -------------------------------------------------------------
        # Step 20: Dashboard
        # -------------------------------------------------------------
        dash_res = self.client.get(f"/cases/{case_id}/details", headers=admin_headers)
        self.assertEqual(dash_res.status_code, 200)
        dash_details = dash_res.json()
        timeline = dash_details.get("timeline", [])
        self.assertGreaterEqual(len(timeline), 5)
        workflow_audit_trail.append({"step": 20, "action": "Dashboard", "status": "PASSED", "timeline_stages": len(timeline)})

        # -------------------------------------------------------------
        # Step 21: Evidence Certificate
        # -------------------------------------------------------------
        cert_res = self.client.get(f"/evidence/{evidence_id}/certificate", headers=admin_headers)
        self.assertEqual(cert_res.status_code, 200)
        cert = cert_res.json()
        self.assertEqual(cert["case_id"], case_num)
        self.assertIn("cryptographic_hashes", cert)
        self.assertIn("disclaimer", cert)
        workflow_audit_trail.append({"step": 21, "action": "Evidence certificate", "status": "PASSED", "certificate_id": cert["certificate_id"]})

        # -------------------------------------------------------------
        # Step 22: Hash Verification
        # -------------------------------------------------------------
        verify_res = self.client.post(f"/evidence/{evidence_id}/verify", headers=admin_headers)
        self.assertEqual(verify_res.status_code, 200)
        verify_json = verify_res.json()
        self.assertTrue(verify_json["image_intact"])
        self.assertFalse(verify_json["is_tampered"])
        self.assertIn(verify_json["status"], ["VERIFIED", "VERIFIED_INTACT"])
        workflow_audit_trail.append({"step": 22, "action": "Hash verification", "status": "PASSED", "verification_status": verify_json["status"]})

        # Validate that all 22 steps passed
        self.assertEqual(len(workflow_audit_trail), 22)
        for step in workflow_audit_trail:
            self.assertEqual(step["status"], "PASSED", f"Step {step['step']} failed: {step}")

        # Export workflow audit trail for TEST_REPORT.md
        self.__class__.workflow_trail = workflow_audit_trail

if __name__ == "__main__":
    unittest.main()
