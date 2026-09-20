# System Architecture - Digital Field Drug Evidence System

## 1. Executive Summary
The **Digital Field Drug Evidence System** is an enterprise, forensic-grade field interpretation platform for presumptive drug screening. It is designed for law enforcement field officers, forensic technicians, and evidence chain auditors.

> [!IMPORTANT]
> **MANDATORY FORENSIC CONSTRAINT**:
> This system interprets presumptive chemical colorimetric and spectroscopic reactions. It **NEVER** claims to conclusively identify a controlled substance. All output is strictly categorized as:
> - `PRESUMPTIVE_POSITIVE`
> - `PRESUMPTIVE_NEGATIVE`
> - `INCONCLUSIVE`
> - `UNSUPPORTED / OUT_OF_DISTRIBUTION`
> Laboratory confirmation (GC-MS / LC-MS) is required for judicial evidentiary proceedings.

---

## 2. Monorepo Architecture Overview

```
digital-field-drug-evidence/
├── mobile/                 # Flutter mobile field application (iOS/Android)
├── web/                    # React/Next.js forensic & admin dashboard
├── backend/                # Python FastAPI core application engine
│   └── app/
│       ├── api/            # API endpoints (v1 routes)
│       ├── core/           # Security, Cryptography, Config, HMAC
│       ├── db/             # Database connection, Models, Migrations
│       ├── schemas/        # Pydantic Request/Response validation
│       └── services/       # Image quality engine, Calibration, AI inference
├── ml/                     # Machine learning models, pipelines, OOD detectors
├── database/               # Database schema (PostgreSQL / SQLite)
├── scripts/                # Utility scripts (e.g. dataset audit framework)
├── tests/                  # Automated test suite (Pytest)
├── docs/                   # Architectural & operational documentation
└── storage/                # Immutable evidence & dataset store
```

---

## 3. Core Component Architecture

### A. Smart Image Capture & Reference-Color-Card Detection Engine
1. **Quality Guard**: Evaluates incoming field reaction images for blur (Laplacian variance > 100), glare, uniform illumination, and minimum resolution (1080p).
2. **Color Calibration**: Detects standard forensic color reference targets (e.g. Macbeth / X-Rite color patch arrays or custom 4-patch reference cards) using HSV color space segmentation and contour extraction.
3. **RGB Normalization**: Applies von Kries / Bradford chromatic adaptation transform to eliminate field lighting variations (warm streetlights, direct sunlight, shaded vehicles).

### B. Presumptive AI Classification & Out-of-Distribution (OOD) Engine
1. **Model Stack**: Ensemble of calibrated CNN/ViT image classifiers and PLS/Random Forest spectral classifiers.
2. **Confidence Calibration**: Platt scaling / Isotonic regression calibrated probabilities. Raw softmax values are NEVER displayed directly as confidence metrics.
3. **Inconclusive & OOD Safeguards**:
   - If confidence is between 0.40 and 0.70, result triggers `INCONCLUSIVE`.
   - If Mahalanobis distance / Isolation Forest OOD score exceeds 99th percentile threshold, result triggers `UNSUPPORTED / OUT_OF_DISTRIBUTION`.

### C. Cryptographic Evidence Integrity & Tamper Detection
1. **Dual SHA-256 Hashing**:
   - `payload_hash`: SHA-256 digest of raw byte stream of captured image.
   - `metadata_hash`: SHA-256 digest of timestamp, GPS coordinates, officer ID, reagent kit lot number.
2. **Evidence Signature**: HMAC-SHA256 calculated over `payload_hash + metadata_hash` using server hardware security key.
3. **Immutable Audit Trail**: Append-only ledger storing all state transitions. Each audit entry links to the previous entry's cryptographic hash (blockchain-style hash chain).

---

## 4. Offline-First Synchronization Architecture
- Field devices cache captures in encrypted local storage (SQLite with SQLCipher).
- Automatic sync queue uploads evidence items when connection is re-established.
- Server validates `payload_hash` upon upload to guarantee zero payload mutation during transit.
