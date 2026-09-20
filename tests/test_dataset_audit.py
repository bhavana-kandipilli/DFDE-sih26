import os
import json

def test_dataset_audit_json_output_exists():
    json_path = os.path.join(os.path.dirname(__file__), "..", "storage", "dataset_audit_results.json")
    md_path = os.path.join(os.path.dirname(__file__), "..", "DATASET_AUDIT.md")
    
    assert os.path.exists(json_path), "dataset_audit_results.json should exist"
    assert os.path.exists(md_path), "DATASET_AUDIT.md should exist"
    
    with open(json_path) as f:
        data = json.load(f)
        
    assert data["raw_files_count"] == 24
    assert data["avg_files_count"] == 24
    assert data["total_raw_samples"] > 0
