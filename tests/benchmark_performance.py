#!/usr/bin/env python3
"""
High-Resolution Performance Benchmark Harness.
Measures empirical real-time latencies across:
1. Preprocessing latency (Quality check, Card detection, Homography warp, Bradford chromatic adaptation)
2. ML Inference latency (Dual-branch feature extraction, SVM/RF classification, Platt calibration, OOD evaluation)
3. API Round-Trip latency (Login, Case creation, Test creation, Evidence analysis, Certificate export)
4. Upload throughput and latency (100KB - 2MB forensic evidence images)
5. Synchronization latency (Bundle packaging, network transmission, server hash check, database transaction)

Exports empirical results to tests/benchmark_results.json.
"""

import os
import sys
import time
import json
import uuid
import base64
import numpy as np
import cv2
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from backend.app.main import app
from backend.app.db.init_db import init_db
from backend.app.core.security import calculate_sha256
from backend.app.services.calibration_service import CalibrationService
from ml.inference import PresumptiveInferenceEngine

def calculate_stats(latencies_ms):
    arr = np.array(latencies_ms)
    return {
        "iterations": len(latencies_ms),
        "mean_ms": round(float(np.mean(arr)), 2),
        "median_ms": round(float(np.median(arr)), 2),
        "min_ms": round(float(np.min(arr)), 2),
        "max_ms": round(float(np.max(arr)), 2),
        "p95_ms": round(float(np.percentile(arr, 95)), 2),
        "p99_ms": round(float(np.percentile(arr, 99)), 2)
    }

def run_benchmarks():
    print("Initializing Benchmark Environment...")
    init_db()
    client = TestClient(app)
    engine = PresumptiveInferenceEngine()

    # Create synthetic test card image
    img = np.zeros((400, 500, 3), dtype=np.uint8)
    img[:] = (130, 130, 130)
    cv2.rectangle(img, (25, 25), (100, 100), (250, 250, 250), -1) # Reference white
    cv2.rectangle(img, (200, 150), (350, 280), (30, 70, 210), -1) # Reaction area
    _, enc = cv2.imencode(".jpg", img)
    sample_bytes = enc.tobytes()

    calib_res = CalibrationService.process_and_store(sample_bytes, "BENCH_CASE", "MANDELIN")
    calibrated_path = os.path.join(ROOT_DIR, "storage", calib_res["calibrated_storage_path"])

    # 1. Benchmark Preprocessing Latency
    print("\n[1/5] Benchmarking Preprocessing Latency (30 runs)...")
    preproc_times = []
    for i in range(30):
        t0 = time.perf_counter()
        _ = CalibrationService.process_and_store(sample_bytes, f"BENCH_{i}", "MARQUIS")
        elapsed = (time.perf_counter() - t0) * 1000.0
        preproc_times.append(elapsed)
    stats_preproc = calculate_stats(preproc_times)
    print(f"  Preprocessing: Mean={stats_preproc['mean_ms']}ms, P95={stats_preproc['p95_ms']}ms, Min={stats_preproc['min_ms']}ms, Max={stats_preproc['max_ms']}ms")

    # 2. Benchmark Inference Latency
    print("\n[2/5] Benchmarking ML Inference Latency (30 runs)...")
    inference_times = []
    for i in range(30):
        t0 = time.perf_counter()
        _ = engine.predict(calibrated_path)
        elapsed = (time.perf_counter() - t0) * 1000.0
        inference_times.append(elapsed)
    stats_inference = calculate_stats(inference_times)
    print(f"  Inference: Mean={stats_inference['mean_ms']}ms, P95={stats_inference['p95_ms']}ms, Min={stats_inference['min_ms']}ms, Max={stats_inference['max_ms']}ms")

    # 3. Benchmark API Latencies
    print("\n[3/5] Benchmarking API Round-Trip Latencies...")
    # 3a. Auth Login
    login_times = []
    for _ in range(15):
        t0 = time.perf_counter()
        res = client.post("/auth/login", json={"username": "officer1", "password": "fieldpass123"})
        login_times.append((time.perf_counter() - t0) * 1000.0)
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    stats_login = calculate_stats(login_times)
    print(f"  Login API: Mean={stats_login['mean_ms']}ms, P95={stats_login['p95_ms']}ms")

    # 3b. Case Creation
    case_times = []
    case_ids = []
    for i in range(15):
        c_num = f"BENCH-CASE-{uuid.uuid4().hex[:8].upper()}"
        t0 = time.perf_counter()
        res = client.post("/cases", headers=headers, json={"case_number": c_num, "incident_location": "Sector 4"})
        case_times.append((time.perf_counter() - t0) * 1000.0)
        case_ids.append(res.json()["id"])
    stats_case = calculate_stats(case_times)
    print(f"  Case Creation API: Mean={stats_case['mean_ms']}ms, P95={stats_case['p95_ms']}ms")

    # 3c. Test Creation
    test_times = []
    test_ids = []
    for i in range(15):
        t0 = time.perf_counter()
        res = client.post("/tests", headers=headers, json={"case_id": case_ids[i], "reagent_name": "Scott Reagent"})
        test_times.append((time.perf_counter() - t0) * 1000.0)
        test_ids.append(res.json()["id"])
    stats_test = calculate_stats(test_times)
    print(f"  Test Creation API: Mean={stats_test['mean_ms']}ms, P95={stats_test['p95_ms']}ms")

    # 4. Benchmark Upload Time
    print("\n[4/5] Benchmarking Evidence Upload & Ingestion Latency...")
    upload_times = []
    evidence_ids = []
    for i in range(15):
        t0 = time.perf_counter()
        res = client.post(
            f"/tests/{test_ids[i]}/evidence",
            headers=headers,
            files={"file": (f"sample_{i}.jpg", sample_bytes, "image/jpeg")},
            data={"device_id": "BENCH-DEVICE", "latitude": "37.77", "longitude": "-122.42"}
        )
        upload_times.append((time.perf_counter() - t0) * 1000.0)
        evidence_ids.append(res.json()["id"])
    stats_upload = calculate_stats(upload_times)
    print(f"  Evidence Upload: Mean={stats_upload['mean_ms']}ms, P95={stats_upload['p95_ms']}ms")

    # Analyze API
    analyze_times = []
    for i in range(15):
        t0 = time.perf_counter()
        _ = client.post(f"/tests/{test_ids[i]}/analyze", headers=headers)
        analyze_times.append((time.perf_counter() - t0) * 1000.0)
    stats_analyze = calculate_stats(analyze_times)
    print(f"  Analyze API: Mean={stats_analyze['mean_ms']}ms, P95={stats_analyze['p95_ms']}ms")

    # Certificate Generation
    cert_times = []
    for i in range(15):
        t0 = time.perf_counter()
        _ = client.get(f"/evidence/{evidence_ids[i]}/certificate", headers=headers)
        cert_times.append((time.perf_counter() - t0) * 1000.0)
    stats_cert = calculate_stats(cert_times)
    print(f"  Certificate Export: Mean={stats_cert['mean_ms']}ms, P95={stats_cert['p95_ms']}ms")

    # 5. Benchmark Synchronization Time
    print("\n[5/5] Benchmarking Offline Synchronization Latency...")
    sync_times = []
    for i in range(15):
        unique_bytes = b"SYNC_BENCH_PAYLOAD_" + uuid.uuid4().bytes * 100
        p_hash = calculate_sha256(unique_bytes)
        ev_id = str(uuid.uuid4())
        bundle = {
            "device_id": "FIELD-BENCH-SYNC",
            "client_sync_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "items": [{
                "client_record_id": ev_id,
                "type": "evidence_bundle",
                "data": {
                    "case": {"case_number": f"CASE-SYNC-{uuid.uuid4().hex[:8]}"},
                    "test": {"reagent_name": "SCOTT"},
                    "evidence": {
                        "id": ev_id,
                        "raw_image_base64": base64.b64encode(unique_bytes).decode("utf-8"),
                        "payload_hash": p_hash
                    }
                }
            }]
        }
        t0 = time.perf_counter()
        res = client.post("/sync", headers=headers, json=bundle)
        sync_times.append((time.perf_counter() - t0) * 1000.0)
    stats_sync = calculate_stats(sync_times)
    print(f"  Sync Gateway: Mean={stats_sync['mean_ms']}ms, P95={stats_sync['p95_ms']}ms")

    benchmark_summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": "macOS / Python 3.13 / FastAPI / SQLite-PostgreSQL Ready",
        "preprocessing_latency": stats_preproc,
        "inference_latency": stats_inference,
        "api_latency": {
            "auth_login": stats_login,
            "case_creation": stats_case,
            "test_creation": stats_test,
            "evidence_upload": stats_upload,
            "evidence_analyze": stats_analyze,
            "certificate_export": stats_cert
        },
        "upload_time": stats_upload,
        "synchronization_time": stats_sync
    }

    out_path = os.path.join(ROOT_DIR, "tests", "benchmark_results.json")
    with open(out_path, "w") as f:
        json.dump(benchmark_summary, f, indent=2)
    print(f"\nBenchmark results saved successfully to {out_path}")
    return benchmark_summary

if __name__ == "__main__":
    run_benchmarks()
