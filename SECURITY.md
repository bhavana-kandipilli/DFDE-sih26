# Security Architecture & Threat Model

**Digital Field Drug Evidence System**  
*Document Version:* 1.0.0  
*Classification:* Technical Documentation & Threat Assessment  

---

## 1. Executive Summary & Scope

The **Digital Field Drug Evidence System** is an AI-assisted presumptive field-test interpretation and digital evidence platform designed for field officers, forensic analysts, administrators, and judicial auditors. 

Because presumptive field test records may form critical chain-of-custody artifacts in legal proceedings, the application must withstand adversarial tampering, accidental contamination, network interception, and evidentiary repudiation.

> [!IMPORTANT]
> **Scientific & Legal Boundary:**  
> The system strictly interprets *presumptive* colorimetric field-test reactions. It **never** claims that AI has conclusively identified a controlled substance. All findings remain presumptive until confirmed by accredited analytical laboratory methods (GC-MS/FTIR).  
> **Compliance Notice:** The technical controls documented herein reflect empirical engineering implementations. No claim of formal compliance with external forensic accreditations (e.g., ISO/IEC 17025, CJIS Policy, or legal evidentiary admissibility standards) is made or implied without independent laboratory validation and official organizational audit.

---

## 2. Threat Model (STRIDE Methodology)

The system boundary encompasses three primary domains:
1. **Field Edge Device:** Offline mobile browser terminal executing capture, optical quality validation, local AES-Fernet encryption, and sync queuing.
2. **Central Application & Storage Gateway:** FastAPI server hosting cryptographic gates, RBAC enforcement, object-addressed evidence storage, and audit logs.
3. **Forensic Web Dashboard:** Restricted interface for forensic analysts, administrators, and auditors inspecting sealed evidence chains.

```
       +-----------------------+
       |   Mobile Field Unit   |
       |  (Offline Capture)    |
       +-----------+-----------+
                   |
     TLS 1.3 / AES-256 Fernet (Sync)
                   |
                   v
       +-----------+-----------+
       |   Central Gateway     |
       |  - Cryptographic Gate |
       |  - RBAC & IDOR Guards |
       |  - Magic Byte Filter  |
       +-----+-----------+-----+
             |           |
             v           v
    +--------+----+ +----+-------------+
    | PostgreSQL  | | Object Storage   |
    | Audit Chain | | Hash-Addressed   |
    +-------------+ +------------------+
```

### STRIDE Assessment Matrix

| Threat Category | Potential Attack Vector | Impact Level | Implemented Mitigation | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **Spoofing** | Adversary imitates field officer credentials or injects counterfeit test results. | High | Bcrypt password hashing; scoped JWT session tokens (8-hr lifespan); cryptographic HMAC signatures bound to officer badge number and device ID. | **Verified** (`test_security.py`) |
| **Tampering** | Officer or external actor alters image pixels or metadata after capture to frame a suspect or destroy evidence. | Critical | Dual SHA-256 payload and canonical representation hashing; HMAC-SHA256 signature verification; synchronization rejected upon any bit difference (`SYNC_REJECTED`). | **Verified** (`test_crypto_integrity.py`, `test_offline_sync.py`) |
| **Repudiation** | Operator denies conducting a test or claims results were falsified in transit. | High | Immutable, append-only Merkle-style cryptographic audit chain (`previous_hash` + `current_hash`); operator badge and device ID embedded in canonical evidence hash. | **Verified** (`test_crypto_integrity.py`) |
| **Information Disclosure** | Unauthorized officer snoops on other jurisdictions or cases (IDOR); sensitive data leaks into cache or logs. | High | Object-level authorization filters (`FIELD_OFFICER` restricted strictly to assigned cases); `Cache-Control: no-store` on sensitive routes; automated redaction of tokens/secrets in JSON logs. | **Verified** (`test_security.py`) |
| **Denial of Service** | Malicious actor uploads decompression bombs (huge pixel count) or bursts requests to crash API. | Medium | 15 MB file size limit; image dimension safety cap (8192px / 32MP limit); in-memory rate limiting (120 req/min per IP); fast OpenCV stream decoding. | **Verified** (`test_security.py`) |
| **Elevation of Privilege** | Field officer accesses administrative settings, dashboard summaries, or verifies unsealed evidence. | Critical | Role-Based Access Control (`require_roles`) enforced at route dependency layer; field officers prohibited from accessing `/dashboard/summary`, user management, or audit controls. | **Verified** (`test_dashboard.py`, `test_backend_api.py`) |

---

## 3. Implemented Security Controls

### 3.1 Authentication & Session Management
- **Password Hashing:** Passwords are hashed using `bcrypt` with automatic salt generation. Plaintext passwords are never logged, transmitted in responses, or stored in persistent storage.
- **Session Tokens:** JSON Web Tokens (JWT) signed with `HS256`. Tokens enforce an 8-hour expiration limit (`ACCESS_TOKEN_EXPIRE_MINUTES`). Tampered signatures or expired tokens return `HTTP 401 Unauthorized`.
- **Credential Redaction:** The structured logging middleware inspects all request headers and query parameters, redacting `Authorization`, `password`, `token`, and `secret` strings before writing logs.

### 3.2 Role-Based Access Control (RBAC) & Object Authorization (IDOR Defense)
- **Role Hierarchy:**
  - `FIELD_OFFICER`: Restricted to creating cases, tests, capturing evidence, and viewing **only** their own assigned cases.
  - `FORENSIC_ANALYST`: Authorized to inspect all cases, review AI presumptive interpretations, run cryptographic verification gates, and generate legal evidence certificates.
  - `ADMIN`: Full operational oversight including user administration and forensic audit trail inspection.
  - `AUDITOR`: Read-only legal auditing permissions across all cases, evidence chains, and audit logs.
  - `READ_ONLY`: Restricted inquiry access.
- **Insecure Direct Object Reference (IDOR) Mitigation:** `GET /cases`, `GET /cases/{id}`, and `GET /cases/{id}/details` enforce ownership checks: if a `FIELD_OFFICER` attempts to query a case created by another officer, the API rejects the request with `HTTP 403 Forbidden`.

### 3.3 File Upload Security & Malware Defense
- **Strict File-Type / Magic Byte Inspection:** File extensions (`.jpg`, `.png`, `.webp`) are not trusted. The upload gateway reads binary file headers to verify authentic magic bytes (`\xFF\xD8\xFF` for JPEG, `\x89PNG\r\n\x1A\n` for PNG, `RIFF....WEBP` for WebP). Any shell script, ELF executable, SVG, or document masquerading as an image is rejected with `HTTP 415 Unsupported Media Type`.
- **Decompression Bomb Protection:** Prior to full decoding, image dimensions are verified against safety thresholds (maximum 8192px along any axis; maximum 32,000,000 total pixels). Oversized images intended to trigger memory exhaustion are rejected with `HTTP 422 Unprocessable Content`.
- **Payload Size Limits:** Enforces a strict 15 MB payload ceiling (`HTTP 413 Payload Too Large`).
- **Path Traversal Defenses:** Uploaded images are renamed to content-addressed hash filenames (`{payload_hash}.png`). Internal path resolution utilizes `safe_storage_path()`, which rejects any relative path components (`..`), root slashes, or null bytes (`\x00`), preventing directory traversal outside `storage/`.

### 3.4 Cryptographic Sealing & Immutability
- **Dual-Layer Hashing:**
  1. `payload_hash`: SHA-256 digest of the raw optical capture image bytes.
  2. `canonical_hash`: SHA-256 digest of a deterministic JSON structure comprising the payload hash, case ID, test ID, operator badge, device ID, GPS coordinates, reagent name, AI result, and capture timestamp.
- **HMAC Signatures:** Computes an HMAC-SHA256 signature using an environment secret key to bind the optical payload to capture provenance.
- **Append-Only Audit Log:** Central transactions generate a cryptographic audit block containing `previous_hash`, `event_type`, `user_id`, `record_id`, and `current_hash = SHA-256(previous_hash + payload)`, forming an immutable audit trail.
- **Offline Sync Gate:** When an offline field unit uploads queued evidence, the central gateway recomputes the SHA-256 hash of the received bytes. If the computed hash differs by even a single bit from the client-claimed hash, the sync is immediately rejected with `SYNC_REJECTED` and an audit security alert is generated.

### 3.5 Transport & Response Header Hardening
All responses emitted by the FastAPI gateway include the following HTTP security headers:
- `X-Content-Type-Options: nosniff`: Prevents MIME-sniffing attacks.
- `X-Frame-Options: DENY`: Prevents clickjacking and framing.
- `X-XSS-Protection: 1; mode=block`: Legacy browser cross-site scripting filter.
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`: Enforces HTTPS transport.
- `Content-Security-Policy: default-src 'self'`: Restricts unauthorized script and resource execution.
- `Referrer-Policy: strict-origin-when-cross-origin`: Minimizes referrer leakage.
- `Cache-Control: no-store, no-cache, must-revalidate`: Enforced on all authenticated forensic data endpoints to prevent sensitive evidence from being cached to browser disk.

### 3.6 Local Vault & Data-at-Rest Protection
- **Encrypted Field Storage:** The offline field SQLite database (`storage/offline_device_vault.db`) stores encrypted blobs using AES-128-CBC with HMAC-SHA256 authentication (Fernet symmetric encryption).
- **Filesystem Permissions:** The device encryption key (`storage/device_encryption.key`) is created with strict POSIX permissions (`0o600`), permitting read/write access solely to the owning process user.
- **SQL Injection Prevention:** Database interactions utilize SQLAlchemy ORM with parameterized queries, eliminating string concatenation and SQL injection vulnerabilities.

---

## 4. Legal & Forensic Standards Assessment

> [!WARNING]
> **Forensic Evidentiary Disclaimer:**  
> While this software incorporates cryptographic integrity, chain-of-custody logging, and defensible audit mechanisms, **no claim of compliance with formal forensic accreditation standards (such as ISO/IEC 17025, SWGDRUG recommendations, or CJIS Security Policy) is made**.

Accreditation under forensic standards requires organizational, laboratory, and procedural qualifications beyond software engineering:
1. **ISO/IEC 17025 (Testing and Calibration Laboratories):** Requires physical laboratory validation, uncertainty measurement budgets, proficiency testing, environmental controls, and certified calibration standards.
2. **SWGDRUG (Scientific Working Group for the Analysis of Seized Drugs):** Categorizes colorimetric tests as Category C (lowest discriminating power). Category C presumptive tests **cannot** be used alone for qualitative identification without Category A (FTIR, GC-MS, NMR) or approved combinations.
3. **CJIS Security Policy:** Involves background screening of personnel, physical facility access controls, and formal federal audit validation.

---

## 5. Security Verification & Test Coverage

The security hardening implementations are verified via automated unit and integration tests:

| Test Module | Coverage | Status |
| :--- | :--- | :--- |
| `tests/test_security.py` | Upload size limits (413), magic byte inspection (415), decompression bomb defense (422), path traversal mitigation (400), IDOR ownership isolation (403), security headers, token tampering rejection (401), vault key permissions (0600), and password hashing. | **15 / 15 Passed** |
| `tests/test_crypto_integrity.py` | SHA-256 payload hashing, HMAC tampering detection, append-only hash chain integrity. | **3 / 3 Passed** |
| `tests/test_backend_api.py` | Full RBAC permissions matrix, authentication flows, model version endpoint, and audit trail inspection. | **16 / 16 Passed** |
| `tests/test_offline_sync.py` | Offline vault encryption, sync queue retry logic, and server-side hash verification gate (`SYNC_REJECTED`). | **11 / 11 Passed** |
| `tests/test_dashboard.py` | Dashboard RBAC isolation, search filtering, case details, and certificate export. | **9 / 9 Passed** |
| **Complete Master Suite** | `tests/run_tests.py` | **74 / 74 Passed (100%)** |

---

## 6. Incident Response & Security Vulnerability Disclosure

To report a suspected vulnerability in the Digital Field Drug Evidence System:
1. Do not file a public issue in open issue trackers.
2. Submit a cryptographic report detailing proof of concept, impact, and affected components to the designated security contact.
3. Allow a 60-day coordinated disclosure window prior to any public release.
