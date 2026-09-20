#!/usr/bin/env python3
"""
Master Test Runner for Digital Field Drug Evidence System.
Executes all automated tests across:
- Phase 1: Cryptographic Integrity, Image Quality, Schema Guards, Dataset Audits
- Stage 1: Data Pipeline, Preprocessing, Group-Aware Splitting, Leakage Detection
- Stage 2: Model Inference, Calibration, Inconclusive Logic, Out-of-Distribution Rejection
- Stage 3: Perspective Correction, Chromatic Adaptation, Evidence Immutability, Smart Camera Validation
- Backend & DB: Full RBAC, Authentication, Authorization, Case/Test/Evidence/Analyze APIs, Verification
"""

import os
import sys
import unittest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from tests.test_crypto_integrity import (
    test_sha256_payload_hashing,
    test_hmac_signature_and_tamper_detection,
    test_append_only_audit_log_hash_chain
)
from tests.test_image_quality import (
    test_sharp_image_quality_passed,
    test_blurry_image_quality_rejected
)
from tests.test_api import (
    test_presumptive_allowed_terminology,
    test_invalid_conclusive_terminology_rejected
)
from tests.test_dataset_audit import test_dataset_audit_json_output_exists
from tests.test_data_pipeline import TestDataPipeline
from tests.test_models import TestModelInference
from tests.test_stage3_workflow import TestStage3Workflow
from tests.test_backend_api import TestBackendAPI
from tests.test_evidence_integrity import TestEvidenceIntegrityEngine
from tests.test_offline_sync import TestOfflineSync
from tests.test_dashboard import TestForensicWebDashboard
from tests.test_security import TestSecurityHardening
from tests.test_complete_workflow import TestCompleteForensicWorkflow
from tests.test_failure_modes import TestFailureModesAndEdgeCases

class TestCryptoIntegrity(unittest.TestCase):
    def test_sha256(self):
        test_sha256_payload_hashing()
        
    def test_hmac_tamper(self):
        test_hmac_signature_and_tamper_detection()
        
    def test_audit_chain(self):
        test_append_only_audit_log_hash_chain()

class TestQualityEvaluation(unittest.TestCase):
    def test_sharp_image(self):
        test_sharp_image_quality_passed()
        
    def test_blurry_image(self):
        test_blurry_image_quality_rejected()

class TestAPISchemas(unittest.TestCase):
    def test_allowed_terms(self):
        test_presumptive_allowed_terminology()
        
    def test_forbidden_terms(self):
        test_invalid_conclusive_terminology_rejected()

class TestDatasetAudit(unittest.TestCase):
    def test_audit_json(self):
        test_dataset_audit_json_output_exists()

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestCryptoIntegrity))
    suite.addTests(loader.loadTestsFromTestCase(TestQualityEvaluation))
    suite.addTests(loader.loadTestsFromTestCase(TestAPISchemas))
    suite.addTests(loader.loadTestsFromTestCase(TestDatasetAudit))
    suite.addTests(loader.loadTestsFromTestCase(TestDataPipeline))
    suite.addTests(loader.loadTestsFromTestCase(TestModelInference))
    suite.addTests(loader.loadTestsFromTestCase(TestStage3Workflow))
    suite.addTests(loader.loadTestsFromTestCase(TestBackendAPI))
    suite.addTests(loader.loadTestsFromTestCase(TestEvidenceIntegrityEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestOfflineSync))
    suite.addTests(loader.loadTestsFromTestCase(TestForensicWebDashboard))
    suite.addTests(loader.loadTestsFromTestCase(TestSecurityHardening))
    suite.addTests(loader.loadTestsFromTestCase(TestCompleteForensicWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestFailureModesAndEdgeCases))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Cleanup synthetic test records and restore authentic real datasets
    try:
        from scripts.seed_real_datasets import purge_and_seed_real_data
        purge_and_seed_real_data()
    except Exception as e:
        print(f"Notice: post-test data purge error: {e}")

    if not result.wasSuccessful():
        print("\nTEST SUITE FAILED!")
        sys.exit(1)
        
    print(f"\nALL {result.testsRun} TESTS COMPLETED WITH 100% PASS RATE!")
