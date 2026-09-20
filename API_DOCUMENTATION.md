# Digital Field Drug Evidence System - Backend REST API Specification

## 1. Architecture & Standards

- **Framework**: Python 3.13 + FastAPI + SQLAlchemy ORM (PostgreSQL-compatible)
- **Authentication**: JWT (JSON Web Token) with HMAC-SHA256 signing (`HS256`)
- **Role-Based Access Control (RBAC)**: 5 granular roles
- **Rate Limiting**: Sliding minute window via `RateLimitingMiddleware`
- **Structured Logging**: JSON format including timestamp, client IP, method, path, status, and duration
- **OpenAPI / Swagger Documentation**: Available at `/docs` and `/redoc` (`/openapi.json`)
- **Scientific & Legal Constraint**: The system strictly produces presumptive interpretation terminology (`PRESUMPTIVE_POSITIVE`, `PRESUMPTIVE_NEGATIVE`, `INCONCLUSIVE`, `UNSUPPORTED / OUT_OF_DISTRIBUTION`) and mandates laboratory confirmation (`lab_confirmation_required: true`).

---

## 2. User Roles & Access Matrix

| Endpoint | Method | Allowed Roles | Description |
| :--- | :--- | :--- | :--- |
| `/health` | GET | *Public* | System health, version, timestamp |
| `/auth/login` | POST | *Public* | Issue JWT access token |
| `/cases` | POST | `FIELD_OFFICER`, `ADMIN` | Create new evidentiary case |
| `/cases` | GET | `ALL_ROLES` | List all cases with case metadata |
| `/cases/{id}` | GET | `ALL_ROLES` | Retrieve single case by UUID |
| `/tests` | POST | `FIELD_OFFICER`, `ADMIN` | Initialize new test session within a case |
| `/tests/{id}` | GET | `ALL_ROLES` | Retrieve test session details |
| `/tests/{id}/evidence` | POST | `FIELD_OFFICER`, `FORENSIC_ANALYST`, `ADMIN` | Upload & calibrate image; calculate SHA-256 |
| `/tests/{id}/analyze` | POST | `FIELD_OFFICER`, `FORENSIC_ANALYST`, `ADMIN` | Run calibrated Platt AI inference engine |
| `/tests/{id}/result` | GET | `ALL_ROLES` | Fetch presumptive AI interpretation & confidence |
| `/tests/{id}/integrity` | GET | `ALL_ROLES` | Verify payload SHA-256 & HMAC-SHA256 signature |
| `/evidence/{id}/verify` | POST | `FORENSIC_ANALYST`, `ADMIN`, `AUDITOR` | Cross-verify stored image bytes against database hash |
| `/sync` | POST | `FIELD_OFFICER`, `ADMIN` | Ingest offline edge records with idempotent replay |
| `/audit/{case_id}` | GET | `FORENSIC_ANALYST`, `ADMIN`, `AUDITOR` | Retrieve SHA-256 hash-chained immutable audit log |
| `/models/current` | GET | `ALL_ROLES` | Retrieve active model metadata and evaluation metrics |

---

## 3. Database Entities

1. **`User`**: System identities, roles (`FIELD_OFFICER`, `FORENSIC_ANALYST`, `ADMIN`, `AUDITOR`, `READ_ONLY`), badge numbers, bcrypt hashed credentials.
2. **`Case`**: Evidentiary investigation container (`case_number`, `incident_location`, `notes`, `status`, `created_by_id`).
3. **`Test`**: Specific reagent test session inside a case (`reagent_name`, `status`, `case_id`).
4. **`Evidence`**: Immutable digital evidence record (`raw_storage_path`, `calibrated_storage_path`, `patch_storage_path`, `payload_hash`, `metadata_hash`, `hmac_signature`, quality metrics).
5. **`AIResult`**: Calibrated inference interpretation (`classification`, `confidence_score`, `ood_score`, `model_version`, `lab_confirmation_required: true`, disclaimer).
6. **`AuditLog`**: Cryptographically chained tamper-evident audit ledger (`previous_hash`, `current_hash`, `action`, `resource_id`, `payload_snapshot`).
7. **`ModelVersion`**: Forensic validation registry of deployed models (`version_tag`, `model_type`, `accuracy`, `f1_score`, `is_active`).
8. **`SyncRecord`**: Mobile/edge offline synchronization telemetry (`device_id`, `client_sync_timestamp`, `records_synced`, `status`).

---

## 4. API Endpoints Specification

### 1. GET `/health`
- **Auth**: None
- **Response** `200 OK`:
```json
{
  "status": "healthy",
  "system": "Digital Field Drug Evidence System",
  "version": "1.0.0",
  "timestamp": "2026-09-19T12:00:00Z"
}
```

### 2. POST `/auth/login`
- **Auth**: None
- **Request Body**:
```json
{
  "username": "officer1",
  "password": "Password123!"
}
```
- **Response** `200 OK`:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "role": "FIELD_OFFICER",
  "user_id": "u-officer-01",
  "username": "officer1"
}
```

### 3. POST `/cases`
- **Auth**: `FIELD_OFFICER`, `ADMIN`
- **Request Body**:
```json
{
  "case_number": "CASE-2026-SF-041",
  "incident_location": "Pier 39, Sector 4",
  "notes": "Suspected white powder seized in clear polythene packaging"
}
```
- **Response** `201 Created`:
```json
{
  "id": "c-91823-uuid",
  "case_number": "CASE-2026-SF-041",
  "incident_location": "Pier 39, Sector 4",
  "notes": "Suspected white powder seized in clear polythene packaging",
  "status": "OPEN",
  "created_by_id": "u-officer-01",
  "created_at": "2026-09-19T12:05:00Z"
}
```

### 4. GET `/cases`
- **Auth**: Authenticated (All roles)
- **Response** `200 OK`: Array of `Case` objects.

### 5. GET `/cases/{id}`
- **Auth**: Authenticated (All roles)
- **Response** `200 OK`: Single `Case` object.

### 6. POST `/tests`
- **Auth**: `FIELD_OFFICER`, `ADMIN`
- **Request Body**:
```json
{
  "case_id": "c-91823-uuid",
  "reagent_name": "idPAD 12-Lane Analytical Device"
}
```
- **Response** `201 Created`:
```json
{
  "id": "t-11029-uuid",
  "case_id": "c-91823-uuid",
  "reagent_name": "idPAD 12-Lane Analytical Device",
  "status": "PENDING",
  "created_by_id": "u-officer-01",
  "created_at": "2026-09-19T12:06:00Z"
}
```

### 7. GET `/tests/{id}`
- **Auth**: Authenticated (All roles)
- **Response** `200 OK`: Single `Test` object.

### 8. POST `/tests/{id}/evidence`
- **Auth**: `FIELD_OFFICER`, `FORENSIC_ANALYST`, `ADMIN`
- **Content-Type**: `multipart/form-data`
- **Form Data**: `file` (Binary image file)
- **Response** `200 OK`:
```json
{
  "id": "e-44021-uuid",
  "test_id": "t-11029-uuid",
  "raw_storage_path": "evidence/raw/e3b0c442...png",
  "calibrated_storage_path": "evidence/calibrated/e3b0c442..._calibrated.png",
  "patch_storage_path": "evidence/patches/e3b0c442..._reaction.png",
  "payload_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "metadata_hash": "a1b2c3d4e5f6...",
  "hmac_signature": "7f83b1657ff1...",
  "blur_score": 184.2,
  "brightness_mean": 128.4,
  "contrast_std": 42.1,
  "card_detected": true,
  "verification_status": "VALID",
  "created_at": "2026-09-19T12:07:00Z"
}
```

### 9. POST `/tests/{id}/analyze`
- **Auth**: `FIELD_OFFICER`, `FORENSIC_ANALYST`, `ADMIN`
- **Response** `200 OK`:
```json
{
  "id": "res-9901-uuid",
  "test_id": "t-11029-uuid",
  "evidence_id": "e-44021-uuid",
  "classification": "PRESUMPTIVE_POSITIVE",
  "confidence_score": 0.894,
  "ood_score": 0.082,
  "model_version": "v1.0.0-presumptive-idpad",
  "decision_reason": "Lane #5 Cobalt Thiocyanate turquoise precipitate detected (RGB=[42, 168, 192]). Calibrated probability exceeds 0.800 threshold.",
  "processing_time_ms": 24.5,
  "lab_confirmation_required": true,
  "disclaimer": "AI Presumptive Field-Test Interpretation Only. NOT conclusive identification. Laboratory GC-MS confirmation legally required.",
  "created_at": "2026-09-19T12:07:05Z"
}
```

### 10. GET `/tests/{id}/result`
- **Auth**: Authenticated (All roles)
- **Response** `200 OK`: `AIResult` object.

### 11. GET `/tests/{id}/integrity`
- **Auth**: Authenticated (All roles)
- **Response** `200 OK`:
```json
{
  "test_id": "t-11029-uuid",
  "evidence_id": "e-44021-uuid",
  "payload_hash": "e3b0c442...",
  "metadata_hash": "a1b2c3d4...",
  "hmac_signature": "7f83b165...",
  "verification_status": "VALID",
  "audit_verified": true
}
```

### 12. POST `/evidence/{id}/verify`
- **Auth**: `FORENSIC_ANALYST`, `ADMIN`, `AUDITOR`
- **Response** `200 OK` (when intact):
```json
{
  "status": "VERIFIED",
  "is_tampered": false,
  "image_intact": true,
  "canonical_hash_verified": true,
  "stored_payload_hash": "e3b0c442...",
  "recomputed_payload_hash": "e3b0c442...",
  "stored_canonical_hash": "75a18446...",
  "recomputed_canonical_hash": "75a18446...",
  "tamper_status": "VALID",
  "verification_timestamp": "2026-09-19T12:10:00Z"
}
```
- **Response** `200 OK` (when tampered):
```json
{
  "status": "TAMPER_DETECTED",
  "is_tampered": true,
  "image_intact": false,
  "canonical_hash_verified": false,
  "stored_payload_hash": "e3b0c442...",
  "recomputed_payload_hash": "401926ce...",
  "tamper_status": "TAMPERED_DISQUALIFIED",
  "verification_timestamp": "2026-09-19T12:10:00Z"
}
```

### 13. GET `/evidence/{id}/certificate`
- **Auth**: Authenticated (All roles)
- **Response** `200 OK`:
```json
{
  "certificate_id": "CERT-T-11029-7F83B165",
  "title": "DIGITAL FIELD DRUG EVIDENCE FORENSIC CERTIFICATE",
  "case_id": "CASE-2026-SF-041",
  "test_id": "t-11029-uuid",
  "officer": {
    "name": "officer1",
    "badge_number": "BADGE-4092",
    "department": "NARCOTICS_FIELD_OPERATIONS"
  },
  "timestamp": "2026-09-19T12:07:00Z",
  "gps": {
    "latitude": 37.7749,
    "longitude": -122.4194
  },
  "test_type": "idPAD 12-Lane Analytical Device",
  "original_image_path": "evidence/raw/e3b0c442...png",
  "result": {
    "classification": "PRESUMPTIVE_POSITIVE",
    "confidence": 0.894,
    "ood_score": 0.082
  },
  "evidence_integrity": {
    "score": 100,
    "status": "HIGH",
    "checks": {
      "focus_sharpness": true,
      "exposure_lighting": true,
      "reaction_visibility": true,
      "reference_card": true,
      "calibration": true,
      "image_quality": true,
      "authenticated_operator": true,
      "device_id": true,
      "gps": true,
      "timestamp": true,
      "metadata_completeness": true,
      "approved_model_version": true,
      "hash": true,
      "hmac_signature": true,
      "tamper_detected": false
    },
    "warnings": [],
    "failures": []
  },
  "cryptographic_hashes": {
    "raw_image_sha256": "e3b0c442...",
    "canonical_record_sha256": "75a18446...",
    "hmac_signature": "7f83b165...",
    "audit_chain_hash": "08f4c2e1..."
  },
  "model_version": "v1.0.0-presumptive-idpad",
  "verification_status": "VALID",
  "disclaimer": "SCIENTIFIC & LEGAL STATUTORY DISCLAIMER: This document certifies presumptive colorimetric field-test interpretation by an AI-assisted optical instrument. This does NOT constitute a conclusive identification of a controlled substance. Confirmatory testing via Gas Chromatography-Mass Spectrometry (GC-MS) or Liquid Chromatography-Mass Spectrometry (LC-MS) remains legally required."
}
```

### 13. POST `/sync`
- **Auth**: `FIELD_OFFICER`, `ADMIN`
- **Request Body**:
```json
{
  "device_id": "MOBILE-TERMINAL-409",
  "client_sync_timestamp": "2026-09-19T12:00:00Z",
  "records": [
    {
      "type": "OFFLINE_CAPTURE",
      "case_number": "CASE-OFFLINE-001",
      "timestamp": "2026-09-19T11:45:00Z"
    }
  ]
}
```
- **Response** `200 OK`:
```json
{
  "sync_id": "sync-7712-uuid",
  "status": "SUCCESS",
  "records_processed": 1,
  "server_timestamp": "2026-09-19T12:10:05Z"
}
```

### 14. GET `/audit/{case_id}`
- **Auth**: `FORENSIC_ANALYST`, `ADMIN`, `AUDITOR`
- **Response** `200 OK`:
Array of audit entries showing cryptographic hash-chaining:
```json
[
  {
    "id": "audit-1",
    "case_id": "c-91823-uuid",
    "action": "CASE_CREATED",
    "resource_id": "c-91823-uuid",
    "previous_hash": "GENESIS_FORENSIC_AUDIT_BLOCK",
    "current_hash": "08f4c2e1...",
    "created_at": "2026-09-19T12:05:00Z"
  },
  {
    "id": "audit-2",
    "case_id": "c-91823-uuid",
    "action": "EVIDENCE_UPLOADED",
    "resource_id": "e-44021-uuid",
    "previous_hash": "08f4c2e1...",
    "current_hash": "9c1b74a2...",
    "created_at": "2026-09-19T12:07:00Z"
  }
]
```

### 15. GET `/models/current`
- **Auth**: Authenticated (All roles)
- **Response** `200 OK`:
```json
{
  "version_tag": "v1.0.0-presumptive-idpad",
  "model_type": "Calibrated Logistic Regression (Platt Scaling)",
  "accuracy": 0.8596,
  "f1_score": 0.8974,
  "is_active": true,
  "created_at": "2026-09-19T08:00:00Z"
}
```

---

## 5. Evidence & Storage Architecture

1. **Object / File Storage**:
   - `storage/evidence/raw/{payload_hash}.png`: Original immutable camera frame. Never edited, overwritten, or compressed.
   - `storage/evidence/calibrated/{payload_hash}_calibrated.png`: Normalized, color-balanced, perspective-rectified card.
   - `storage/evidence/patches/{payload_hash}_reaction.png`: Cropped reaction zones for forensic review.
2. **Metadata & Cryptography**:
   - `payload_hash`: SHA-256 of raw image bytes computed immediately upon receipt.
   - `metadata_hash`: SHA-256 of canonical JSON metadata (case, test, badge, timestamp).
   - `hmac_signature`: HMAC-SHA256 signature binding payload and metadata using secret key (`HMAC_SECRET_KEY`).
   - `audit_logs`: Hash-chained append-only ledger (`current_hash = SHA256(previous_hash + payload)`).
