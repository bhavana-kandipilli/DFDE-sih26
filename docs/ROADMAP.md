# Development Roadmap - Digital Field Drug Evidence System

## Phase 1: Foundation & Architecture Setup (COMPLETED - Task 1)
- [x] Environment inspection and technology stack selection.
- [x] Monorepo directory structure setup (`mobile`, `web`, `backend`, `ml`, `database`, `scripts`, `tests`, `docs`, `storage`, `docker`).
- [x] Comprehensive documentation suite creation (`ARCHITECTURE.md`, `SECURITY.md`, `DATASET_AUDIT.md`, `MODEL_CARD.md`, `MODEL_EVALUATION.md`, `API_DOCUMENTATION.md`, `LIMITATIONS.md`).
- [x] Dataset audit framework (`scripts/dataset_audit.py`) and initial audit execution across 50 raw & averaged spectral datafiles.
- [x] Database schema design (`database/schema.sql` and SQLAlchemy models).
- [x] Backend FastAPI application structure with authentication, evidence quality, and cryptographic integrity endpoints.
- [x] Core Cryptography & Quality engines (`SHA-256` payload hashing, `HMAC-SHA256` signatures, Laplacian blur evaluator).
- [x] Initial automated unit test suite with 100% pass rate.

---

## Phase 2: ML Model Training & Calibration Engine (Next Step - Task 2)
- [ ] Implement RGB color patch extraction and reference-card color calibration pipeline.
- [ ] Train multi-modal classification models on spectral and colorimetric datasets.
- [ ] Implement Platt scaling / isotonic regression confidence calibration.
- [ ] Build Out-of-Distribution (OOD) detector using Mahalanobis distance / Isolation Forest.
- [ ] Integrate ML models into FastAPI inference service (`backend/app/services/ml_engine.py`).

---

## Phase 3: Web & Mobile Frontends
- [ ] Build Flutter field application interface (Smart camera preview, reference-card target overlays, offline SQLite cache).
- [ ] Build React/Next.js Forensic Admin Dashboard (Case management, audit trail inspection, digital certificate generation).

---

## Phase 4: Full System Integration & Security Audit
- [ ] End-to-end containerized deployment using Docker Compose (PostgreSQL, FastAPI, S3/MinIO storage).
- [ ] Cryptographic chain-of-custody audit validation.
- [ ] Complete automated integration & stress testing suite.
