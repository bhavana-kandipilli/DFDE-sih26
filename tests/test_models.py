#!/usr/bin/env python3
import os
import unittest
import numpy as np
import cv2

from ml.inference import PresumptiveInferenceEngine
from ml.preprocessing.pipeline import ImagePreprocessor

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

class TestModelInference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = PresumptiveInferenceEngine()
        cls.preprocessor = ImagePreprocessor()

    def test_model_loading(self):
        self.assertIsNotNone(self.engine.model)
        self.assertIsNotNone(self.engine.scaler)
        self.assertIsNotNone(self.engine.ood_detector)
        self.assertIn("positive_threshold", self.engine.thresholds)

    def test_real_image_inference(self):
        sample_img = os.path.join(ROOT_DIR, "storage", "processed_images", "idpad", "image25.jpeg")
        self.assertTrue(os.path.exists(sample_img))
        
        result = self.engine.predict(sample_img)
        self.assertIn("classification", result)
        self.assertIn("calibrated_confidence", result)
        self.assertIn("ood_score", result)
        self.assertIn("payload_hash", result)
        self.assertEqual(len(result["payload_hash"]), 64)
        self.assertIn("NOTICE: This output is a presumptive field-test interpretation", result["disclaimer"])

    def test_malformed_image_handling(self):
        malformed_bytes = b"CORRUPTED_NOT_AN_IMAGE_STREAM_0011"
        result = self.engine.predict(malformed_bytes)
        self.assertEqual(result["classification"], "INCONCLUSIVE")
        self.assertIn("IMAGE_INVALID", result["reason"])

    def test_blurry_image_triggers_inconclusive(self):
        # Synthetic blurry image
        img = np.full((200, 200, 3), 128, dtype=np.uint8)
        img = cv2.GaussianBlur(img, (25, 25), 0)
        _, buf = cv2.imencode(".png", img)
        
        result = self.engine.predict(buf.tobytes())
        self.assertEqual(result["classification"], "INCONCLUSIVE")
        self.assertIn("QUALITY_REJECT_BLURRY", result["reason"])

    def test_thresholding_consistency(self):
        # Test that allowed terminology is strictly maintained
        valid_classes = {
            "PRESUMPTIVE_POSITIVE",
            "PRESUMPTIVE_NEGATIVE",
            "INCONCLUSIVE",
            "UNSUPPORTED / OUT_OF_DISTRIBUTION"
        }
        sample_img = os.path.join(ROOT_DIR, "storage", "processed_images", "idpad", "image30.jpeg")
        result = self.engine.predict(sample_img)
        self.assertIn(result["classification"], valid_classes)

if __name__ == "__main__":
    unittest.main(verbosity=2)
