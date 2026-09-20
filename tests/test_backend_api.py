#!/usr/bin/env python3
"""
Comprehensive API Integration Tests for Backend & Database.
Covers:
- Authentication (valid credentials, invalid password, bad payload)
- Authorization (RBAC permissions for FIELD_OFFICER, FORENSIC_ANALYST, ADMIN, AUDITOR, READ_ONLY)
- Unauthorized Access (missing / invalid token -> 401)
- Forbidden Access (insufficient role -> 403)
- Invalid Requests (422 / 400)
- Case Creation & Listing
- Field Test Initialization
- Evidence Upload & Calibration Storage
- AI Model Inference Execution & Result Retrieval
- Cryptographic Evidence Integrity & Tamper Verification
- Offline Sync Processing
- Audit Trail Inspection
- Current Model Version Metadata
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from backend.app.main import app
from backend.app.db.init_db import init_db

class TestBackendAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize database and seed role accounts
        init_db()
        cls.client = TestClient(app)

        # Load real forensic sample image
        sample_path = os.path.join(ROOT_DIR, "storage", "processed_images", "idpad", "image25.jpeg")
        with open(sample_path, "rb") as f:
            cls.sample_bytes = f.read()

        # Obtain tokens for each role
        cls.officer_token = cls._get_token("officer1", "fieldpass123")
        cls.analyst_token = cls._get_token("analyst1", "analystpass123")
        cls.admin_token = cls._get_token("admin1", "adminpass123")
        cls.auditor_token = cls._get_token("auditor1", "auditorpass123")
        cls.readonly_token = cls._get_token("readonly1", "readonlypass123")

    @classmethod
    def _get_token(cls, username, password):
        res = cls.client.post("/auth/login", json={"username": username, "password": password})
        if res.status_code != 200:
            raise RuntimeError(f"Failed to authenticate seed user {username}: {res.text}")
        return res.json()["access_token"]

    def _headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    # 1. Authentication Tests
    def test_auth_login_success(self):
        res = self.client.post("/auth/login", json={"username": "officer1", "password": "fieldpass123"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["role"], "FIELD_OFFICER")
        self.assertEqual(data["badge_number"], "BADGE-4092")

    def test_auth_login_invalid_password(self):
        res = self.client.post("/auth/login", json={"username": "officer1", "password": "wrongpassword"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("Invalid username or password", res.json()["detail"])

    def test_auth_login_unknown_user(self):
        res = self.client.post("/auth/login", json={"username": "ghost_user", "password": "anypassword"})
        self.assertEqual(res.status_code, 401)

    # 2. Unauthorized Access Tests
    def test_unauthorized_access_without_token(self):
        res = self.client.get("/cases")
        self.assertEqual(res.status_code, 401)
        self.assertIn("credentials were not provided", res.json()["detail"])

    def test_unauthorized_access_invalid_token(self):
        res = self.client.get("/cases", headers={"Authorization": "Bearer fake.tampered.token"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("Invalid or expired", res.json()["detail"])

    # 3. Role-Based Access Control (Authorization Tests)
    def test_rbac_case_creation_permitted_for_officer(self):
        case_num = f"CASE-INT-{os.urandom(4).hex().upper()}"
        res = self.client.post(
            "/cases",
            json={"case_number": case_num, "incident_location": "Pier 9 Cargo", "notes": "Suspected cocaine"},
            headers=self._headers(self.officer_token)
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["case_number"], case_num)

    def test_rbac_case_creation_forbidden_for_readonly(self):
        res = self.client.post(
            "/cases",
            json={"case_number": "CASE-FORBIDDEN-01", "incident_location": "Airport Terminal 2"},
            headers=self._headers(self.readonly_token)
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("Forbidden", res.json()["detail"])

    def test_rbac_evidence_upload_forbidden_for_auditor(self):
        # Auditor should not be able to upload evidence
        res = self.client.post(
            "/tests/test-dummy-id/evidence",
            files={"file": ("evidence.jpg", self.sample_bytes, "image/jpeg")},
            headers=self._headers(self.auditor_token)
        )
        self.assertEqual(res.status_code, 403)

    def test_rbac_audit_logs_accessible_to_auditor(self):
        res = self.client.get("/audit/case-2026-001", headers=self._headers(self.auditor_token))
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

    # 4. Invalid Requests & Validation Error Handling
    def test_invalid_request_missing_required_fields(self):
        # Missing required incident_location
        res = self.client.post(
            "/cases",
            json={"case_number": "CASE-BAD"},
            headers=self._headers(self.officer_token)
        )
        self.assertEqual(res.status_code, 422)

    def test_invalid_request_nonexistent_case(self):
        res = self.client.get("/cases/nonexistent-case-uuid-9999", headers=self._headers(self.officer_token))
        self.assertEqual(res.status_code, 404)

    def test_invalid_request_test_creation_bad_case_id(self):
        res = self.client.post(
            "/tests",
            json={"case_id": "nonexistent-case-id", "reagent_name": "Marquis"},
            headers=self._headers(self.officer_token)
        )
        self.assertEqual(res.status_code, 404)

    # 5. Full End-to-End Workflow (Case -> Test -> Evidence -> Analyze -> Result -> Integrity)
    def test_full_forensic_workflow(self):
        # Step A: Create Case
        case_num = f"CASE-E2E-{os.urandom(4).hex().upper()}"
        res_case = self.client.post(
            "/cases",
            json={"case_number": case_num, "incident_location": "Highway 101 Checkpoint", "notes": "Seized test matrix"},
            headers=self._headers(self.officer_token)
        )
        self.assertEqual(res_case.status_code, 201)
        case_id = res_case.json()["id"]

        # Step B: Create Field Test
        res_test = self.client.post(
            "/tests",
            json={"case_id": case_id, "reagent_name": "idPAD 12-Lane Analytical Device"},
            headers=self._headers(self.officer_token)
        )
        self.assertEqual(res_test.status_code, 201)
        test_id = res_test.json()["id"]
        self.assertEqual(res_test.json()["status"], "PENDING")

        # Step C: Upload Evidence Binary
        res_evidence = self.client.post(
            f"/tests/{test_id}/evidence",
            files={"file": ("field_capture.jpg", self.sample_bytes, "image/jpeg")},
            headers=self._headers(self.officer_token)
        )
        self.assertEqual(res_evidence.status_code, 200)
        evidence_id = res_evidence.json()["id"]
        payload_hash = res_evidence.json()["payload_hash"]
        self.assertEqual(len(payload_hash), 64)
        self.assertEqual(res_evidence.json()["verification_status"], "VALID")

        # Step D: Run AI Analysis with Stage 2 Model
        res_analyze = self.client.post(
            f"/tests/{test_id}/analyze",
            headers=self._headers(self.officer_token)
        )
        self.assertEqual(res_analyze.status_code, 200)
        ai_res = res_analyze.json()
        self.assertIn(ai_res["classification"], ["PRESUMPTIVE_POSITIVE", "PRESUMPTIVE_NEGATIVE", "INCONCLUSIVE", "UNSUPPORTED / OUT_OF_DISTRIBUTION"])
        self.assertGreater(ai_res["confidence_score"], 0.0)
        self.assertIn("processing_time_ms", ai_res)
        self.assertTrue(ai_res["lab_confirmation_required"])
        self.assertIn("presumptive field-test interpretation", ai_res["disclaimer"].lower())

        # Step E: Retrieve Test Result
        res_get_result = self.client.get(f"/tests/{test_id}/result", headers=self._headers(self.readonly_token))
        self.assertEqual(res_get_result.status_code, 200)
        self.assertEqual(res_get_result.json()["id"], ai_res["id"])

        # Step F: Check Cryptographic Evidence Integrity
        res_integrity = self.client.get(f"/tests/{test_id}/integrity", headers=self._headers(self.officer_token))
        self.assertEqual(res_integrity.status_code, 200)
        self.assertEqual(res_integrity.json()["verification_status"], "VALID")
        self.assertFalse(res_integrity.json()["is_tampered"])

        # Step G: Verify Evidence as Forensic Analyst
        res_verify = self.client.post(
            f"/evidence/{evidence_id}/verify",
            headers=self._headers(self.analyst_token)
        )
        self.assertEqual(res_verify.status_code, 200)
        self.assertTrue(res_verify.json()["hash_matched"])
        self.assertTrue(res_verify.json()["hmac_valid"])
        self.assertEqual(res_verify.json()["tamper_status"], "VALID")

        # Step H: Inspect Audit Trail for Case
        res_audit = self.client.get(f"/audit/{case_id}", headers=self._headers(self.analyst_token))
        self.assertEqual(res_audit.status_code, 200)
        logs = res_audit.json()
        self.assertGreaterEqual(len(logs), 4) # CASE_CREATED, TEST_INITIALIZED, EVIDENCE_UPLOADED, AI_ANALYSIS_EXECUTED

    # 6. Offline Synchronization Endpoint
    def test_sync_offline_records(self):
        sync_payload = {
            "device_id": "FIELD-TERMINAL-DELTA-9",
            "client_sync_timestamp": "2026-09-19T10:00:00Z",
            "items": [
                {"client_record_id": "local-case-101", "type": "case", "data": {"case_num": "CASE-SYNC-01"}}
            ]
        }
        res = self.client.post("/sync", json=sync_payload, headers=self._headers(self.officer_token))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["records_processed"], 1)
        self.assertEqual(res.json()["status"], "COMPLETED")

    # 7. Model Version & Health Endpoints
    def test_get_current_model_version(self):
        res = self.client.get("/models/current", headers=self._headers(self.readonly_token))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["version_tag"], "v1.0.0-presumptive-idpad")
        self.assertGreater(res.json()["accuracy"], 0.8)

    def test_health_check_public(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "healthy")

if __name__ == "__main__":
    unittest.main(verbosity=2)
