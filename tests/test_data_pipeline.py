#!/usr/bin/env python3
import os
import json
import unittest
import pandas as pd
import numpy as np

from ml.preprocessing.pipeline import ImagePreprocessor

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

class TestDataPipeline(unittest.TestCase):
    def setUp(self):
        self.preprocessor = ImagePreprocessor(target_size=(224, 224), min_blur_var=100.0)
        self.manifest_path = os.path.join(ROOT_DIR, "dataset_manifest.json")
        self.train_path = os.path.join(ROOT_DIR, "train_manifest.csv")
        self.val_path = os.path.join(ROOT_DIR, "validation_manifest.csv")
        self.test_path = os.path.join(ROOT_DIR, "test_manifest.csv")

    def test_manifest_files_exist(self):
        self.assertTrue(os.path.exists(self.manifest_path), "dataset_manifest.json missing")
        self.assertTrue(os.path.exists(self.train_path), "train_manifest.csv missing")
        self.assertTrue(os.path.exists(self.val_path), "validation_manifest.csv missing")
        self.assertTrue(os.path.exists(self.test_path), "test_manifest.csv missing")

    def test_no_missing_labels(self):
        df_train = pd.read_csv(self.train_path)
        df_val = pd.read_csv(self.val_path)
        df_test = pd.read_csv(self.test_path)
        
        for name, df in [("train", df_train), ("val", df_val), ("test", df_test)]:
            self.assertFalse(df["presumptive_label"].isnull().any(), f"Missing labels found in {name}")
            self.assertFalse(df["sample_id"].isnull().any(), f"Missing sample_id in {name}")
            # Ensure only allowed terminologies
            valid_labels = {"PRESUMPTIVE_POSITIVE", "PRESUMPTIVE_NEGATIVE"}
            self.assertTrue(set(df["presumptive_label"].unique()).issubset(valid_labels), f"Invalid labels in {name}")

    def test_group_aware_splitting_no_leakage(self):
        df_train = pd.read_csv(self.train_path)
        df_val = pd.read_csv(self.val_path)
        df_test = pd.read_csv(self.test_path)

        train_ids = set(df_train["sample_id"])
        val_ids = set(df_val["sample_id"])
        test_ids = set(df_test["sample_id"])

        # Physical samples must not appear in multiple splits
        train_test_overlap = train_ids.intersection(test_ids)
        train_val_overlap = train_ids.intersection(val_ids)
        val_test_overlap = val_ids.intersection(test_ids)

        self.assertEqual(len(train_test_overlap), 0, f"Train-Test leakage detected: {train_test_overlap}")
        self.assertEqual(len(train_val_overlap), 0, f"Train-Val leakage detected: {train_val_overlap}")
        self.assertEqual(len(val_test_overlap), 0, f"Val-Test leakage detected: {val_test_overlap}")

    def test_preprocessing_output_structure(self):
        # Create a synthetic image
        synth_img = np.full((150, 300, 3), 120, dtype=np.uint8)
        res = self.preprocessor.load_and_preprocess(synth_img)

        self.assertTrue(res["valid"])
        self.assertEqual(res["normalized_image"].shape, (224, 224, 3))
        self.assertEqual(res["feature_vector"].shape, (21,))
        self.assertIn("quality", res)
        self.assertIn("color_metrics", res)

    def test_corrupted_image_handling(self):
        # Malformed bytes
        corrupted_bytes = b"NOT_A_VALID_IMAGE_FILE_HEADER"
        res = self.preprocessor.load_and_preprocess(corrupted_bytes)
        self.assertFalse(res["valid"])
        self.assertEqual(res["error"], "DECODE_FAILED")

    def test_compatibility_matrix(self):
        compat_path = os.path.join(ROOT_DIR, "dataset_compatibility.csv")
        self.assertTrue(os.path.exists(compat_path))
        df_compat = pd.read_csv(compat_path)
        self.assertGreaterEqual(len(df_compat), 3)
        self.assertIn("Dataset_Name", df_compat.columns)
        self.assertIn("Compatible_With_NIR", df_compat.columns)

if __name__ == "__main__":
    unittest.main(verbosity=2)
