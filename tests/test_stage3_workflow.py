#!/usr/bin/env python3
"""
Stage 3 Automated Tests: Calibration, Smart Camera Validation, and End-to-End Workflow.
"""

import os
import sys
import unittest
import numpy as np
import cv2
from io import BytesIO

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from backend.app.services.calibration_service import CalibrationService
from backend.app.core.security import calculate_sha256
from fastapi.testclient import TestClient
from backend.app.main import app

class TestStage3Workflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Load a real sample image from PMC7332374 idPAD dataset
        sample_path = os.path.join(ROOT_DIR, "storage", "processed_images", "idpad", "image25.jpeg")
        with open(sample_path, "rb") as f:
            cls.sample_bytes = f.read()

    def test_corner_ordering(self):
        pts = np.array([[100, 200], [10, 10], [200, 10], [200, 200]], dtype="float32")
        ordered = CalibrationService.order_points(pts)
        self.assertEqual(ordered.shape, (4, 2))
        # Top-left has smallest sum
        np.testing.assert_array_equal(ordered[0], [10, 10])

    def test_perspective_rectification_and_color_calibration(self):
        nparr = np.frombuffer(self.sample_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        found, pts = CalibrationService.detect_card_corners(img)
        self.assertTrue(found)

        rectified = CalibrationService.perspective_rectification(img, pts, target_size=(400, 220))
        self.assertEqual(rectified.shape, (220, 400, 3))

        calibrated = CalibrationService.chromatic_adaptation(rectified)
        self.assertEqual(calibrated.shape, (220, 400, 3))

        roi = CalibrationService.extract_reaction_roi(calibrated)
        self.assertGreater(roi.shape[0], 50)
        self.assertGreater(roi.shape[1], 100)

    def test_raw_evidence_immutability(self):
        # Process evidence and ensure raw file is strictly isolated and never overwritten
        case_id = "CASE-TEST-IMMUTABLE"
        res = CalibrationService.process_and_store(self.sample_bytes, case_id, "idPAD Test")
        
        raw_full_path = os.path.join(ROOT_DIR, "storage", res["raw_storage_path"])
        calib_full_path = os.path.join(ROOT_DIR, "storage", res["calibrated_storage_path"])
        patch_full_path = os.path.join(ROOT_DIR, "storage", res["patch_storage_path"])

        self.assertTrue(os.path.exists(raw_full_path))
        self.assertTrue(os.path.exists(calib_full_path))
        self.assertTrue(os.path.exists(patch_full_path))

        # Raw file sha256 MUST exactly match raw_bytes sha256
        with open(raw_full_path, "rb") as f:
            saved_raw_bytes = f.read()
        self.assertEqual(calculate_sha256(saved_raw_bytes), calculate_sha256(self.sample_bytes))

        # Raw file path and calibrated path must be completely distinct
        self.assertNotEqual(raw_full_path, calib_full_path)

    def test_validate_frame_api_endpoint(self):
        files = {"frame": ("frame.jpg", self.sample_bytes, "image/jpeg")}
        response = self.client.post("/api/v1/evidence/validate-frame", files=files)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("can_capture", data)
        self.assertIn("reference_card_detected", data)
        self.assertIn("lighting_ok", data)
        self.assertIn("focus_ok", data)
        self.assertIn("quality_score", data)
        self.assertIn("actionable_instruction", data)

    def test_calibrate_and_analyze_api_endpoint(self):
        data = {
            "case_id": "CASE-2026-STAGE3-TEST",
            "reagent_name": "idPAD 12-Lane Analytical Device",
            "officer_id": "BADGE-4092"
        }
        files = {"file": ("evidence.jpg", self.sample_bytes, "image/jpeg")}
        response = self.client.post("/api/v1/evidence/calibrate-and-analyze", data=data, files=files)
        self.assertEqual(response.status_code, 200)

        result = response.json()
        valid_classifications = {
            "PRESUMPTIVE_POSITIVE",
            "PRESUMPTIVE_NEGATIVE",
            "INCONCLUSIVE",
            "UNSUPPORTED / OUT_OF_DISTRIBUTION"
        }
        self.assertIn(result["classification"], valid_classifications)
        self.assertGreater(result["calibrated_confidence"], 0.0)
        self.assertIn("processing_time_ms", result)
        self.assertIn("evidence_integrity", result)
        self.assertEqual(len(result["evidence_integrity"]["payload_hash"]), 64)
        self.assertEqual(len(result["evidence_integrity"]["hmac_signature"]), 64)
        self.assertIn("artifacts", result)

if __name__ == "__main__":
    unittest.main(verbosity=2)
