import unittest
import os
import io
import json
import uuid
import base64
import datetime
from PIL import Image
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.init_db import init_db
from backend.app.core.config import settings

class TestForensicWebDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

        # Login Officer
        res_off = cls.client.post("/auth/login", json={"username": "officer1", "password": "fieldpass123"})
        assert res_off.status_code == 200
        cls.officer_token = res_off.json()["access_token"]

        # Login Analyst
        res_ana = cls.client.post("/auth/login", json={"username": "analyst1", "password": "analystpass123"})
        assert res_ana.status_code == 200
        cls.analyst_token = res_ana.json()["access_token"]

        # Login Admin
        res_adm = cls.client.post("/auth/login", json={"username": "admin1", "password": "adminpass123"})
        assert res_adm.status_code == 200
        cls.admin_token = res_adm.json()["access_token"]

        # Login Auditor
        res_aud = cls.client.post("/auth/login", json={"username": "auditor1", "password": "auditorpass123"})
        assert res_aud.status_code == 200
        cls.auditor_token = res_aud.json()["access_token"]

        # Login ReadOnly
        res_ro = cls.client.post("/auth/login", json={"username": "readonly1", "password": "readonlypass123"})
        assert res_ro.status_code == 200
        cls.readonly_token = res_ro.json()["access_token"]

    def _headers(self, token: str):
        return {"Authorization": f"Bearer {token}"}

    def _create_sample_image_bytes(self):
        img = Image.new("RGB", (640, 480), color=(180, 180, 180))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

    def test_dashboard_summary_rbac(self):
        """Dashboard summary must only be accessible to analysts, admins, and auditors."""
        # 1. Analyst -> 200
        res_ana = self.client.get("/dashboard/summary", headers=self._headers(self.analyst_token))
        self.assertEqual(res_ana.status_code, 200)
        data = res_ana.json()
        self.assertIn("total_cases", data)
        self.assertIn("total_tests", data)
        self.assertIn("pending_sync", data)
        self.assertIn("presumptive_positive", data)
        self.assertIn("presumptive_negative", data)
        self.assertIn("inconclusive", data)
        self.assertIn("unsupported_ood", data)
        self.assertIn("integrity_warnings_count", data)
        self.assertIn("recent_activity", data)
        self.assertIn("Application record metrics only", data["disclaimer"])

        # 2. Admin -> 200
        res_adm = self.client.get("/dashboard/summary", headers=self._headers(self.admin_token))
        self.assertEqual(res_adm.status_code, 200)

        # 3. Auditor -> 200
        res_aud = self.client.get("/dashboard/summary", headers=self._headers(self.auditor_token))
        self.assertEqual(res_aud.status_code, 200)

        # 4. Field Officer -> 403 Forbidden
        res_off = self.client.get("/dashboard/summary", headers=self._headers(self.officer_token))
        self.assertEqual(res_off.status_code, 403)

        # 5. Read-Only -> 403 Forbidden
        res_ro = self.client.get("/dashboard/summary", headers=self._headers(self.readonly_token))
        self.assertEqual(res_ro.status_code, 403)

        # 6. Unauthenticated -> 401 Unauthorized
        res_anon = self.client.get("/dashboard/summary")
        self.assertEqual(res_anon.status_code, 401)

    def test_case_search_and_multifilter(self):
        """Test cases filtering by case number, incident location, status, officer, and reagent."""
        uid = uuid.uuid4().hex[:6]
        c1_num = f"CASE-ALPHA-{uid}"
        c2_num = f"CASE-BETA-{uid}"

        # Create distinct cases
        c1 = self.client.post("/cases", json={
            "case_number": c1_num,
            "incident_location": "Airport Terminal 3 Gate 12",
            "notes": "Target suspect luggage inspection"
        }, headers=self._headers(self.officer_token)).json()

        c2 = self.client.post("/cases", json={
            "case_number": c2_num,
            "incident_location": "Downtown Metro Station Plaza",
            "notes": "Paraphernalia recovery"
        }, headers=self._headers(self.officer_token)).json()

        # Add test with distinct reagent
        t1 = self.client.post("/tests", json={
            "case_id": c1["id"],
            "reagent_name": "Cobalt_Thiocyanate"
        }, headers=self._headers(self.officer_token)).json()

        # 1. Search by keyword
        res_search = self.client.get("/cases?search=Airport", headers=self._headers(self.analyst_token))
        self.assertEqual(res_search.status_code, 200)
        cases = res_search.json()
        self.assertTrue(any(c["id"] == c1["id"] for c in cases))
        self.assertFalse(any(c["id"] == c2["id"] for c in cases))

        # 2. Search by case number
        res_num = self.client.get(f"/cases?search={c2_num}", headers=self._headers(self.analyst_token))
        self.assertEqual(res_num.status_code, 200)
        self.assertEqual(len(res_num.json()), 1)
        self.assertEqual(res_num.json()[0]["case_number"], c2_num)

        # 3. Filter by reagent
        res_reagent = self.client.get("/cases?reagent=Cobalt", headers=self._headers(self.analyst_token))
        self.assertEqual(res_reagent.status_code, 200)
        self.assertTrue(any(c["id"] == c1["id"] for c in res_reagent.json()))

        # 4. Filter by officer
        res_off = self.client.get("/cases?officer=officer1", headers=self._headers(self.analyst_token))
        self.assertEqual(res_off.status_code, 200)
        self.assertGreaterEqual(len(res_off.json()), 2)

    def test_case_details_and_9_stage_audit_timeline(self):
        """Verify that case details endpoint constructs the 9-stage forensic chain of custody timeline."""
        uid = uuid.uuid4().hex[:6]
        c_num = f"CASE-TIMELINE-{uid}"

        # Setup case, test, and evidence
        c_res = self.client.post("/cases", json={
            "case_number": c_num,
            "incident_location": "Highway Interdiction Checkpoint",
            "notes": "Powder packet recovered"
        }, headers=self._headers(self.officer_token))
        self.assertEqual(c_res.status_code, 201)
        case_id = c_res.json()["id"]

        t_res = self.client.post("/tests", json={
            "case_id": case_id,
            "reagent_name": "Marquis_Reagent"
        }, headers=self._headers(self.officer_token))
        self.assertEqual(t_res.status_code, 201)
        test_id = t_res.json()["id"]

        # Upload evidence
        img_bytes = self._create_sample_image_bytes()
        ev_res = self.client.post(
            f"/tests/{test_id}/evidence",
            files={"file": ("capture.jpg", img_bytes, "image/jpeg")},
            data={"device_id": "DEVICE-TEST-001", "latitude": 37.7749, "longitude": -122.4194},
            headers=self._headers(self.officer_token)
        )
        self.assertEqual(ev_res.status_code, 200)
        ev_id = ev_res.json()["id"]

        # Run AI inference
        ai_res = self.client.post(f"/tests/{test_id}/analyze", headers=self._headers(self.officer_token))
        self.assertEqual(ai_res.status_code, 200)

        # Run verification
        v_res = self.client.post(f"/evidence/{ev_id}/verify", headers=self._headers(self.analyst_token))
        self.assertEqual(v_res.status_code, 200)

        # 1. Fetch Case Details
        details_res = self.client.get(f"/cases/{case_id}/details", headers=self._headers(self.analyst_token))
        self.assertEqual(details_res.status_code, 200)
        details = details_res.json()

        self.assertEqual(details["case"]["case_number"], c_num)
        self.assertEqual(details["officer_name"], "officer1")
        self.assertGreaterEqual(len(details["tests"]), 1)
        self.assertIsNotNone(details["tests"][0]["evidence"])
        self.assertIsNotNone(details["tests"][0]["ai_result"])

        # 2. Check 9-stage Timeline
        timeline = details["timeline"]
        self.assertEqual(len(timeline), 9)

        expected_stages = [
            (1, "Officer Authenticated"),
            (2, "Case Created"),
            (3, "Test Created"),
            (4, "Image Captured"),
            (5, "AI Inference"),
            (6, "Evidence Finalized"),
            (7, "Hash Generated"),
            (8, "Sync"),
            (9, "Verification")
        ]

        for idx, (expected_num, expected_name) in enumerate(expected_stages):
            stage = timeline[idx]
            self.assertEqual(stage["stage_number"], expected_num)
            self.assertEqual(stage["stage_name"], expected_name)
            self.assertEqual(stage["status"], "COMPLETED")
            self.assertTrue(stage["verified"])
            self.assertIsNotNone(stage["details"])
            self.assertIsNotNone(stage["actor"])

        # 3. Direct GET /cases/{id}/timeline
        timeline_direct = self.client.get(f"/cases/{case_id}/timeline", headers=self._headers(self.auditor_token))
        self.assertEqual(timeline_direct.status_code, 200)
        self.assertEqual(len(timeline_direct.json()), 9)

    def test_certificate_export_rbac_and_disclaimers(self):
        """Verify digital evidence certificate contents, legal disclaimers, and role restrictions."""
        uid = uuid.uuid4().hex[:6]
        c_num = f"CASE-CERT-{uid}"

        # Create case & test & evidence
        c_res = self.client.post("/cases", json={
            "case_number": c_num,
            "incident_location": "Maritime Port Sector 4",
            "notes": "Crate inspection"
        }, headers=self._headers(self.officer_token))
        self.assertEqual(c_res.status_code, 201)
        case_id = c_res.json()["id"]

        t_res = self.client.post("/tests", json={
            "case_id": case_id,
            "reagent_name": "Scott_Reagent"
        }, headers=self._headers(self.officer_token))
        test_id = t_res.json()["id"]

        img_bytes = self._create_sample_image_bytes()
        ev_res = self.client.post(
            f"/tests/{test_id}/evidence",
            files={"file": ("port_sample.jpg", img_bytes, "image/jpeg")},
            data={"device_id": "DEVICE-CERT-01", "latitude": 34.0522, "longitude": -118.2437},
            headers=self._headers(self.officer_token)
        )
        self.assertEqual(ev_res.status_code, 200)
        evidence_id = ev_res.json()["id"]

        # Inference
        self.client.post(f"/tests/{test_id}/analyze", headers=self._headers(self.officer_token))

        # 1. Analyst export certificate -> 200
        res_ana = self.client.get(f"/evidence/{evidence_id}/certificate", headers=self._headers(self.analyst_token))
        self.assertEqual(res_ana.status_code, 200)
        cert = res_ana.json()
        self.assertIn("CERT-", cert["certificate_id"])
        self.assertIn("presumptive", cert["disclaimer"].lower())
        self.assertIn("conclusive identification", cert["disclaimer"])
        self.assertIn("GC-MS", cert["disclaimer"])
        self.assertIn("raw_image_sha256", cert["cryptographic_hashes"])
        self.assertIn("canonical_record_sha256", cert["cryptographic_hashes"])
        self.assertIn("hmac_signature", cert["cryptographic_hashes"])

        # 2. Admin export certificate -> 200
        res_adm = self.client.get(f"/evidence/{evidence_id}/certificate", headers=self._headers(self.admin_token))
        self.assertEqual(res_adm.status_code, 200)

        # 3. Auditor export certificate -> 200
        res_aud = self.client.get(f"/evidence/{evidence_id}/certificate", headers=self._headers(self.auditor_token))
        self.assertEqual(res_aud.status_code, 200)

        # 4. Read-Only user export certificate -> 403 Forbidden
        res_ro = self.client.get(f"/evidence/{evidence_id}/certificate", headers=self._headers(self.readonly_token))
        self.assertEqual(res_ro.status_code, 403)

if __name__ == "__main__":
    unittest.main()
