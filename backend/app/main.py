import os
import time
import uuid
import datetime
import numpy as np
import cv2
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.app.core.config import settings
from backend.app.db.init_db import init_db
from backend.app.core.middleware import StructuredLoggingMiddleware, RateLimitingMiddleware, SecurityHeadersMiddleware
from backend.app.core.upload_security import validate_uploaded_image
from backend.app.api.endpoints import router as forensic_router
from backend.app.services.calibration_service import CalibrationService
from ml.inference import PresumptiveInferenceEngine
from backend.app.core.security import calculate_sha256, generate_hmac_signature

_inference_engine = None


def get_inference_engine():
    global _inference_engine
    if _inference_engine is None:
        _inference_engine = PresumptiveInferenceEngine()
    return _inference_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schemas and seed role accounts
    init_db()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production-grade AI-assisted presumptive field-test interpretation and digital evidence system.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Middlewares (Ordered: Security Headers -> CORS -> Structured Logging -> Rate Limiting)
app.add_middleware(SecurityHeadersMiddleware)

# CORS configuration
allowed_origins = settings.CORS_ORIGINS if settings.ENVIRONMENT == "production" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(StructuredLoggingMiddleware)
app.add_middleware(RateLimitingMiddleware, requests_per_minute=settings.RATE_LIMIT_PER_MINUTE)

# Include Complete Forensic REST API Router (both at root and /api/v1 for seamless API compatibility)
app.include_router(forensic_router)
app.include_router(forensic_router, prefix="/api/v1")

# Stage 3 Smart Camera Live Frame Validation (for backward compatibility with field UI)
@app.post("/validate-frame")
@app.post("/api/v1/evidence/validate-frame")
async def validate_camera_frame(frame: UploadFile = File(...)):
    contents = await frame.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty frame.")

    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid frame format.")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))

    card_detected, _ = CalibrationService.detect_card_corners(img)

    focus_ok = blur_score >= settings.MIN_LAPLACIAN_VAR
    lighting_ok = (brightness >= settings.MIN_EXPOSURE_VAL) and (brightness <= settings.MAX_EXPOSURE_VAL)
    reaction_area_ok = contrast >= 15.0 and card_detected

    can_capture = focus_ok and lighting_ok and card_detected and reaction_area_ok

    if not card_detected:
        instruction = "Place the reference card fully inside the frame."
    elif not focus_ok:
        instruction = "Hold the device steady. Camera is focusing..."
    elif brightness < settings.MIN_EXPOSURE_VAL:
        instruction = "Increase lighting. Target area is too dark."
    elif brightness > settings.MAX_EXPOSURE_VAL:
        instruction = "Reduce glare or direct reflection. Overexposed."
    elif not reaction_area_ok:
        instruction = "Move closer to make reaction zones clearly visible."
    else:
        instruction = "Optimal capture conditions. Hold steady to analyze."

    quality_score = min(100.0, max(0.0, (min(blur_score, 1000.0) / 10.0 * 0.4) + (min(contrast, 80.0) / 80.0 * 0.3 * 100.0) + (30.0 if lighting_ok else 0.0)))

    return {
        "can_capture": can_capture,
        "reference_card_detected": card_detected,
        "lighting_ok": lighting_ok,
        "focus_ok": focus_ok,
        "reaction_area_visible": reaction_area_ok,
        "quality_score": round(quality_score, 1),
        "metrics": {
            "blur_score": round(blur_score, 1),
            "brightness_mean": round(brightness, 1),
            "contrast_std": round(contrast, 1)
        },
        "actionable_instruction": instruction
    }

# Stage 3 Pipeline: Direct Calibrate & Analyze Endpoint
@app.post("/api/v1/evidence/calibrate-and-analyze")
async def calibrate_and_analyze_legacy(
    file: UploadFile = File(...),
    case_id: str = Form("DEFAULT-CASE"),
    reagent_name: str = Form("idPAD 12-Lane Analytical Device"),
    officer_id: str = Form("BADGE-001")
):
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Empty evidence binary.")

    calib_res = CalibrationService.process_and_store(raw_bytes, case_id, reagent_name)
    calibrated_full_path = os.path.join(settings.STORAGE_DIR, calib_res["calibrated_storage_path"])

    t0 = time.time()
    inference_engine = get_inference_engine()
    ai_res = inference_engine.predict(calibrated_full_path)
    latency_ms = round((time.time() - t0) * 1000.0, 2)

    metadata_dict = {
        "case_id": case_id,
        "officer_id": officer_id,
        "reagent": reagent_name,
        "payload_hash": calib_res["payload_hash"]
    }
    meta_hash = calculate_sha256(str(metadata_dict).encode("utf-8"))
    hmac_sig = generate_hmac_signature(calib_res["payload_hash"], metadata_dict)

    return {
        "status": "ANALYSIS_COMPLETE",
        "classification": ai_res["classification"],
        "calibrated_confidence": ai_res.get("calibrated_confidence", 0.0),
        "raw_confidence": ai_res.get("raw_confidence", 0.0),
        "ood_score": ai_res.get("ood_score", 0.0),
        "model_version": inference_engine.config.get("model_version", "v1.0.0-presumptive-idpad"),
        "decision_reason": ai_res.get("decision_reason", ""),
        "lab_confirmation_required": True,
        "disclaimer": ai_res["disclaimer"],
        "processing_time_ms": latency_ms,
        "evidence_integrity": {
            "payload_hash": calib_res["payload_hash"],
            "metadata_hash": meta_hash,
            "hmac_signature": hmac_sig,
            "quality": calib_res["quality"]
        },
        "artifacts": {
            "raw_url": f"/static/{calib_res['raw_storage_path']}",
            "calibrated_url": f"/static/{calib_res['calibrated_storage_path']}",
            "patch_url": f"/static/{calib_res['patch_storage_path']}"
        }
    }

# Real Dataset Presets (PMC7332374 & Wiley DTA.1949 with Berrien County Crime Lab Ground Truth)
@app.get("/api/v1/samples/preset-gallery")
def get_preset_gallery():
    return [
        {
            "id": "sample-cocaine-42",
            "title": "Blinded Sample #3R9 - Cocaine HCl (100%)",
            "category": "Controlled Substance Presumptive",
            "substance": "Cocaine Hydrochloride",
            "concentration": "100%",
            "matrix": "Pure Salt Form",
            "dataset": "PMC7332374 / Berrien County Crime Lab (FTIR & GC-MS)",
            "image_url": "/static/samples/image42.jpeg",
            "description": "Blinded 12-lane test card with Cobalt Thiocyanate turquoise reaction"
        },
        {
            "id": "sample-heroin-70",
            "title": "Blinded Sample #6JZ - Heroin (50% / Lactose 50%)",
            "category": "Borderline / Inconclusive Zone",
            "substance": "Diacetylmorphine",
            "concentration": "50%",
            "matrix": "Lactose Excipient (50%)",
            "dataset": "PMC7332374 / Berrien County Crime Lab (FTIR & GC-MS)",
            "image_url": "/static/samples/image70.jpeg",
            "description": "Blinded 12-lane test card exhibiting cut opiate profile in safe inconclusive band"
        },
        {
            "id": "sample-meth-109",
            "title": "Blinded Sample #CQK - Methamphetamine (50%)",
            "category": "Controlled Substance Presumptive",
            "substance": "Methamphetamine",
            "concentration": "50%",
            "matrix": "Dimethyl Sulfone (50%)",
            "dataset": "PMC7332374 / Berrien County Crime Lab (FTIR & GC-MS)",
            "image_url": "/static/samples/image109.jpeg",
            "description": "Blinded test card with Simon/Marquis amphetamine colorimetric reaction"
        },
        {
            "id": "sample-lactose-35",
            "title": "Blinded Sample #33P - Lactose Blank (0% Drug)",
            "category": "Negative / Excipient Blank",
            "substance": "Lactose Excipient",
            "concentration": "0% (Pure Excipient)",
            "matrix": "Lactose (100%)",
            "dataset": "PMC7332374 / Berrien County Crime Lab (Negative Baseline)",
            "image_url": "/static/samples/image35.jpeg",
            "description": "Unreacted negative paper analytical device spotted with 100% Lactose"
        },
        {
            "id": "sample-dmso2-56",
            "title": "Blinded Sample #4WZ - Dimethyl Sulfone Blank (0%)",
            "category": "Negative / Excipient Blank",
            "substance": "Dimethyl Sulfone (DMSO2)",
            "concentration": "0% (Pure Excipient)",
            "matrix": "Dimethyl Sulfone (100%)",
            "dataset": "PMC7332374 / Berrien County Crime Lab (Negative Baseline)",
            "image_url": "/static/samples/image56.jpeg",
            "description": "Common cutting agent blank demonstrating negative reagent baseline"
        },
        {
            "id": "sample-ood-121",
            "title": "Blinded Sample #DSW - Optical Anomaly (OOD)",
            "category": "Out-of-Distribution / Safety Rejection",
            "substance": "Optical / Illumination Distortion",
            "concentration": "N/A",
            "matrix": "Severe Lighting Discrepancy",
            "dataset": "PMC7332374 Optical Anomaly Gate",
            "image_url": "/static/samples/image121.jpeg",
            "description": "Severe lighting deviation triggering Out-of-Distribution safety rejection"
        }
    ]

@app.get("/api/v1/samples/dataset-manifest")
def get_dataset_manifest():
    return get_preset_gallery()

# Static File Mounts
storage_evidence_dir = os.path.join(settings.STORAGE_DIR, "evidence")
os.makedirs(storage_evidence_dir, exist_ok=True)
app.mount("/static/evidence", StaticFiles(directory=storage_evidence_dir), name="evidence")

processed_idpad_dir = os.path.join(settings.STORAGE_DIR, "processed_images", "idpad")
os.makedirs(processed_idpad_dir, exist_ok=True)
app.mount("/static/samples", StaticFiles(directory=processed_idpad_dir), name="samples")

# Mount web frontend
web_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web"))
os.makedirs(web_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
