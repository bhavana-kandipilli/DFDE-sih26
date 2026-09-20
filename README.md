# Digital Field Drug Evidence System

An AI-assisted presumptive field-test interpretation and digital evidence monorepo platform. Designed for law enforcement field officers, crime scene investigators, and forensic laboratories.

> [!IMPORTANT]
> **CRITICAL FORENSIC & LEGAL CONSTRAINT**:
> This system must **NEVER** claim that AI has conclusively identified a drug. The AI provides interpretation of a presumptive field-test reaction.
> Allowed result terminology:
> - `PRESUMPTIVE_POSITIVE`
> - `PRESUMPTIVE_NEGATIVE`
> - `INCONCLUSIVE`
> - `UNSUPPORTED / OUT_OF_DISTRIBUTION`
> Laboratory confirmation (GC-MS / LC-MS) remains strictly required for court proceedings.

---

## Technical Stack & Architecture

- **Backend**: Python 3.13 + FastAPI + Pydantic v2 + SQLAlchemy
- **ML & Computer Vision**: OpenCV, PyTorch, scikit-learn, NumPy, Pandas
- **Database**: PostgreSQL (with SQLite compatibility for isolated testing)
- **Cryptography & Audit Trail**: SHA-256 binary payload hashing, HMAC-SHA256 evidence signatures, append-only hash-chain audit ledger
- **Frontend / Mobile**: Flutter (mobile) & React (web admin dashboard)

---

## Monorepo Directory Structure

```
digital-field-drug-evidence/
├── mobile/                 # Mobile field application
├── web/                    # Forensic & admin web dashboard
├── backend/                # FastAPI application engine
│   └── app/
│       ├── api/            # API endpoints
│       ├── core/           # Security, SHA-256 / HMAC, Config
│       ├── db/             # Database models & connection
│       ├── schemas/        # Pydantic request/response schemas
│       ├── services/       # Quality evaluation & calibration engine
│       └── main.py
├── ml/                     # ML training, preprocessing, OOD detectors
├── database/               # PostgreSQL schema (`schema.sql`)
├── scripts/                # Dataset audit framework (`dataset_audit.py`)
├── tests/                  # Automated test suite (`run_tests.py`)
├── docs/                   # Development roadmap & operational guides
├── storage/                # Evidence & dataset storage
├── docker/                 # Container configs
├── .env.example
├── docker-compose.yml
├── requirements.txt
├── README.md
├── ARCHITECTURE.md
├── SECURITY.md
├── DATASET_AUDIT.md
├── MODEL_CARD.md
├── MODEL_EVALUATION.md
├── API_DOCUMENTATION.md
├── TEST_REPORT.md
└── LIMITATIONS.md
```

---

## Core Documentation Suite
- [`ARCHITECTURE.md`](file:///Users/bhavanaavyyakandipilli/.gemini/antigravity-ide/scratch/digital-field-drug-evidence/ARCHITECTURE.md): System architecture, microservices, and offline sync model.
- [`SECURITY.md`](file:///Users/bhavanaavyyakandipilli/.gemini/antigravity-ide/scratch/digital-field-drug-evidence/SECURITY.md): AES-256, TLS 1.3, SHA-256 payload hashing, HMAC evidence signatures, RBAC.
- [`DATASET_AUDIT.md`](file:///Users/bhavanaavyyakandipilli/.gemini/antigravity-ide/scratch/digital-field-drug-evidence/DATASET_AUDIT.md): Comprehensive audit of 48 raw & averaged spectral datafiles across 5 portable sensing devices.
- [`MODEL_CARD.md`](file:///Users/bhavanaavyyakandipilli/.gemini/antigravity-ide/scratch/digital-field-drug-evidence/MODEL_CARD.md): Model card, inputs/outputs, intended use, prohibited use cases.
- [`MODEL_EVALUATION.md`](file:///Users/bhavanaavyyakandipilli/.gemini/antigravity-ide/scratch/digital-field-drug-evidence/MODEL_EVALUATION.md): Evaluation metrics, rejection standards, blur & exposure thresholds.
- [`API_DOCUMENTATION.md`](file:///Users/bhavanaavyyakandipilli/.gemini/antigravity-ide/scratch/digital-field-drug-evidence/API_DOCUMENTATION.md): REST API specification for case management and evidence interpretation.
- [`TEST_REPORT.md`](file:///Users/bhavanaavyyakandipilli/.gemini/antigravity-ide/scratch/digital-field-drug-evidence/TEST_REPORT.md): Initial automated test suite execution report (100% pass rate).
- [`LIMITATIONS.md`](file:///Users/bhavanaavyyakandipilli/.gemini/antigravity-ide/scratch/digital-field-drug-evidence/LIMITATIONS.md): Scientific, environmental, and operational boundaries.

---

## Running the Automated Test Suite

```bash
cd digital-field-drug-evidence
python3 tests/run_tests.py
```
