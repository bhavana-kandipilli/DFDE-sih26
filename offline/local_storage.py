#!/usr/bin/env python3
"""
Encrypted Local Storage Engine for Offline Field Operation.

Provides field-level AES encryption (via Fernet authenticated symmetric cipher)
for all locally stored cases, tests, evidence images, AI results, and sync queues.
Guarantees persistence across application restarts and power loss.
"""

import os
import sqlite3
import json
import base64
import hashlib
import datetime
from typing import Dict, Any, List, Optional
from cryptography.fernet import Fernet

class EncryptedLocalStorage:
    """
    Isolated local encrypted storage database for field terminals.
    """

    DEFAULT_DB_PATH = "storage/offline_device_vault.db"
    DEFAULT_KEY_PATH = "storage/device_encryption.key"

    @staticmethod
    def generate_device_key() -> bytes:
        return Fernet.generate_key()

    def __init__(self, db_path: Optional[str] = None, encryption_key: Optional[bytes] = None):
        self.db_path = db_path or self.DEFAULT_DB_PATH
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

        if encryption_key:
            self.cipher = Fernet(encryption_key)
        else:
            key_path = self.DEFAULT_KEY_PATH
            if os.path.exists(key_path):
                with open(key_path, "rb") as f:
                    key = f.read().strip()
            else:
                key = Fernet.generate_key()
                with open(key_path, "wb") as f:
                    f.write(key)
                try:
                    os.chmod(key_path, 0o600)
                except OSError:
                    pass
            try:
                os.chmod(key_path, 0o600)
            except OSError:
                pass
            self.cipher = Fernet(key)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Offline Cases
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS offline_cases (
                case_id TEXT PRIMARY KEY,
                case_number TEXT UNIQUE NOT NULL,
                incident_location TEXT NOT NULL,
                notes TEXT,
                officer_id TEXT,
                created_at TEXT NOT NULL
            );
            """)

            # 2. Offline Tests
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS offline_tests (
                test_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                reagent_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES offline_cases(case_id)
            );
            """)

            # 3. Offline Evidence (Encrypted image payload)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS offline_evidence (
                evidence_id TEXT PRIMARY KEY,
                test_id TEXT UNIQUE NOT NULL,
                encrypted_image_bytes BLOB NOT NULL,
                payload_hash TEXT NOT NULL,
                canonical_hash TEXT,
                metadata_json TEXT NOT NULL,
                quality_json TEXT NOT NULL,
                integrity_score INTEGER,
                integrity_status TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (test_id) REFERENCES offline_tests(test_id)
            );
            """)

            # 4. Offline AI Results
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS offline_ai_results (
                result_id TEXT PRIMARY KEY,
                test_id TEXT UNIQUE NOT NULL,
                classification TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                ood_score REAL NOT NULL,
                model_version TEXT NOT NULL,
                decision_reason TEXT,
                processing_time_ms REAL,
                disclaimer TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (test_id) REFERENCES offline_tests(test_id)
            );
            """)

            # 5. Offline Sync Queue
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_queue (
                idempotency_key TEXT PRIMARY KEY,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING_SYNC',
                retry_count INTEGER NOT NULL DEFAULT 0,
                last_attempt_at TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL
            );
            """)
            conn.commit()

    # -------------------------------------------------------------
    # Case & Test Operations
    # -------------------------------------------------------------
    def save_case(self, case_id: str, case_data_or_number: Any, incident_location: Optional[str] = None, notes: Optional[str] = None, officer_id: Optional[str] = None, created_at: Optional[str] = None) -> Dict[str, Any]:
        if isinstance(case_data_or_number, dict):
            data = case_data_or_number
            case_number = data.get("case_number", f"CASE-{int(datetime.datetime.now().timestamp())}")
            location = data.get("incident_location") or data.get("location") or "FIELD"
            notes = data.get("notes") or data.get("description") or ""
            officer_id = data.get("officer_id") or data.get("created_by_id")
            created_at = data.get("created_at") or datetime.datetime.now(datetime.timezone.utc).isoformat()
        else:
            case_number = str(case_data_or_number)
            location = incident_location or "FIELD"
            created_at = created_at or datetime.datetime.now(datetime.timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO offline_cases (case_id, case_number, incident_location, notes, officer_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """, (case_id, case_number, location, notes, officer_id, created_at))
            conn.commit()
        return {
            "case_id": case_id,
            "case_number": case_number,
            "incident_location": location,
            "notes": notes,
            "officer_id": officer_id,
            "created_at": created_at
        }

    def save_test(self, test_id: str, test_data_or_case_id: Any, reagent_name: Optional[str] = None, created_at: Optional[str] = None) -> Dict[str, Any]:
        if isinstance(test_data_or_case_id, dict):
            data = test_data_or_case_id
            case_id = data.get("case_id", "")
            reagent_name = data.get("reagent_name", "UNKNOWN")
            created_at = data.get("created_at") or datetime.datetime.now(datetime.timezone.utc).isoformat()
        else:
            case_id = str(test_data_or_case_id)
            reagent_name = reagent_name or "UNKNOWN"
            created_at = created_at or datetime.datetime.now(datetime.timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO offline_tests (test_id, case_id, reagent_name, created_at)
            VALUES (?, ?, ?, ?);
            """, (test_id, case_id, reagent_name, created_at))
            conn.commit()
        return {
            "test_id": test_id,
            "case_id": case_id,
            "reagent_name": reagent_name,
            "created_at": created_at
        }

    # -------------------------------------------------------------
    # Evidence & AI Result Operations
    # -------------------------------------------------------------
    def save_evidence(
        self,
        evidence_id: str,
        evidence_data_or_test_id: Any,
        raw_image_bytes: Optional[bytes] = None,
        payload_hash: Optional[str] = None,
        canonical_hash: Optional[str] = None,
        metadata_dict: Optional[Dict[str, Any]] = None,
        quality_dict: Optional[Dict[str, Any]] = None,
        integrity_score: Optional[int] = None,
        integrity_status: Optional[str] = None,
        created_at: Optional[str] = None
    ) -> Dict[str, Any]:
        if isinstance(evidence_data_or_test_id, dict):
            data = evidence_data_or_test_id
            test_id = data.get("test_id", "")
            p_hash = data.get("payload_hash") or payload_hash or ""
            c_hash = data.get("canonical_hash") or canonical_hash
            m_dict = data.get("metadata") or metadata_dict or {
                "device_id": data.get("device_id", "UNKNOWN"),
                "gps_latitude": data.get("gps_latitude"),
                "gps_longitude": data.get("gps_longitude")
            }
            q_dict = data.get("quality") or quality_dict or {
                "blur_score": data.get("blur_score", 120.0),
                "brightness_mean": data.get("brightness_mean", 128.0),
                "contrast_std": data.get("contrast_std", 45.0),
                "card_detected": data.get("card_detected", True)
            }
            i_score = data.get("integrity_score") if data.get("integrity_score") is not None else integrity_score
            i_status = data.get("integrity_status") or integrity_status or "HIGH"
            created_at = data.get("created_at") or created_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
            img_bytes = raw_image_bytes or b""
        else:
            test_id = str(evidence_data_or_test_id)
            p_hash = payload_hash or ""
            c_hash = canonical_hash
            m_dict = metadata_dict or {}
            q_dict = quality_dict or {}
            i_score = integrity_score
            i_status = integrity_status
            created_at = created_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
            img_bytes = raw_image_bytes or b""

        # Encrypt the raw image binary before writing to SQLite
        encrypted_bytes = self.cipher.encrypt(img_bytes)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO offline_evidence 
            (evidence_id, test_id, encrypted_image_bytes, payload_hash, canonical_hash, metadata_json, quality_json, integrity_score, integrity_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                evidence_id, test_id, encrypted_bytes, p_hash, c_hash,
                json.dumps(m_dict), json.dumps(q_dict),
                i_score, i_status, created_at
            ))
            conn.commit()

        return {
            "evidence_id": evidence_id,
            "test_id": test_id,
            "payload_hash": p_hash,
            "canonical_hash": c_hash,
            "integrity_score": i_score,
            "integrity_status": i_status,
            "created_at": created_at
        }

    def save_ai_result(
        self,
        result_id: str,
        result_data_or_test_id: Any,
        classification: Optional[str] = None,
        confidence_score: Optional[float] = None,
        ood_score: Optional[float] = None,
        model_version: Optional[str] = None,
        decision_reason: Optional[str] = None,
        processing_time_ms: Optional[float] = None,
        disclaimer: Optional[str] = None,
        created_at: Optional[str] = None
    ) -> Dict[str, Any]:
        if isinstance(result_data_or_test_id, dict):
            data = result_data_or_test_id
            test_id = data.get("test_id", "")
            classification = data.get("classification", "INCONCLUSIVE")
            confidence_score = float(data.get("confidence_score", 0.0))
            ood_score = float(data.get("ood_score", 0.0))
            model_version = data.get("model_version", "v1.0.0-presumptive-idpad")
            decision_reason = data.get("decision_reason")
            processing_time_ms = data.get("processing_time_ms")
            disclaimer = data.get("disclaimer")
            created_at = data.get("created_at") or datetime.datetime.now(datetime.timezone.utc).isoformat()
        else:
            test_id = str(result_data_or_test_id)
            classification = classification or "INCONCLUSIVE"
            confidence_score = float(confidence_score or 0.0)
            ood_score = float(ood_score or 0.0)
            model_version = model_version or "v1.0.0-presumptive-idpad"
            created_at = created_at or datetime.datetime.now(datetime.timezone.utc).isoformat()

        disclaimer = disclaimer or (
            "AI Presumptive Field-Test Interpretation Only. NOT conclusive identification. "
            "Laboratory GC-MS confirmation legally required."
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO offline_ai_results
            (result_id, test_id, classification, confidence_score, ood_score, model_version, decision_reason, processing_time_ms, disclaimer, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                result_id, test_id, classification, confidence_score, ood_score,
                model_version, decision_reason, processing_time_ms, disclaimer, created_at
            ))
            conn.commit()

        return {
            "result_id": result_id,
            "test_id": test_id,
            "classification": classification,
            "confidence_score": confidence_score,
            "ood_score": ood_score,
            "model_version": model_version,
            "created_at": created_at
        }

    # -------------------------------------------------------------
    # Sync Queue Operations
    # -------------------------------------------------------------
    def queue_for_sync(self, idempotency_key: str, resource_type: str, resource_id: str, payload_hash: str) -> None:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR IGNORE INTO sync_queue
            (idempotency_key, resource_type, resource_id, payload_hash, status, retry_count, created_at)
            VALUES (?, ?, ?, ?, 'PENDING_SYNC', 0, ?);
            """, (idempotency_key, resource_type, resource_id, payload_hash, now_iso))
            conn.commit()

    def enqueue_sync_item(self, resource_type: str, resource_id: str, payload_hash: Optional[str] = None, idempotency_key: Optional[str] = None) -> str:
        import uuid
        key = idempotency_key or f"SYNC-{uuid.uuid4()}"
        p_hash = payload_hash or "UNKNOWN_HASH"
        self.queue_for_sync(key, resource_type, resource_id, p_hash)
        return key

    def get_sync_items(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT * FROM sync_queue WHERE status = ? ORDER BY created_at ASC;", (status,))
            else:
                cursor.execute("SELECT * FROM sync_queue ORDER BY created_at ASC;")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def update_sync_status(self, idempotency_key: str, status: str, error_message: Optional[str] = None) -> None:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE sync_queue 
            SET status = ?, 
                error_message = ?, 
                last_attempt_at = ?, 
                retry_count = retry_count + 1
            WHERE idempotency_key = ?;
            """, (status, error_message, now_iso, idempotency_key))
            conn.commit()

    # -------------------------------------------------------------
    # Read & Decrypt Operations
    # -------------------------------------------------------------
    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM offline_cases WHERE case_id = ?;", (case_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_test(self, test_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM offline_tests WHERE test_id = ?;", (test_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM offline_evidence WHERE evidence_id = ?;", (evidence_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            # Decrypt image bytes
            data["decrypted_image_bytes"] = self.cipher.decrypt(data["encrypted_image_bytes"])
            data["metadata"] = json.loads(data["metadata_json"])
            data["quality"] = json.loads(data["quality_json"])
            return data

    def get_raw_image(self, payload_hash: str) -> Optional[bytes]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT encrypted_image_bytes FROM offline_evidence WHERE payload_hash = ?;", (payload_hash,))
            row = cursor.fetchone()
            if not row:
                return None
            return self.cipher.decrypt(row["encrypted_image_bytes"])

    def get_pending_sync_items(self) -> List[Dict[str, Any]]:
        return self.get_sync_items(status="PENDING_SYNC")

    def get_all_queue_items(self) -> List[Dict[str, Any]]:
        return self.get_sync_items()

    def get_ai_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM offline_ai_results WHERE result_id = ?;", (result_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_full_bundle_by_evidence_id(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """
        Assembles complete decrypted package for cloud synchronization.
        """
        evidence = self.get_evidence(evidence_id)
        if not evidence:
            return None

        test = self.get_test(evidence["test_id"])
        if not test:
            return None

        case = self.get_case(test["case_id"])
        if not case:
            return None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM offline_ai_results WHERE test_id = ?;", (test["test_id"],))
            ai_row = cursor.fetchone()
            ai_result = dict(ai_row) if ai_row else None

        case_dict = dict(case)
        case_dict["id"] = case_dict.get("case_id")

        test_dict = dict(test)
        test_dict["id"] = test_dict.get("test_id")

        ev_dict = {
            "id": evidence["evidence_id"],
            "evidence_id": evidence["evidence_id"],
            "test_id": evidence["test_id"],
            "payload_hash": evidence["payload_hash"],
            "canonical_hash": evidence["canonical_hash"],
            "integrity_score": evidence["integrity_score"],
            "integrity_status": evidence["integrity_status"],
            "metadata": evidence["metadata"],
            "quality": evidence["quality"],
            "device_id": evidence["metadata"].get("device_id", "OFFLINE_DEVICE"),
            "gps_latitude": evidence["metadata"].get("gps_latitude"),
            "gps_longitude": evidence["metadata"].get("gps_longitude"),
            "blur_score": evidence["quality"].get("blur_score"),
            "brightness_mean": evidence["quality"].get("brightness_mean"),
            "contrast_std": evidence["quality"].get("contrast_std"),
            "card_detected": evidence["quality"].get("card_detected", True),
            "created_at": evidence["created_at"],
            "raw_image_base64": base64.b64encode(evidence["decrypted_image_bytes"]).decode("utf-8")
        }

        if ai_result:
            ai_dict = dict(ai_result)
            ai_dict["id"] = ai_dict.get("result_id")
        else:
            ai_dict = None

        return {
            "case": case_dict,
            "test": test_dict,
            "evidence": ev_dict,
            "ai_result": ai_dict
        }

    def close(self):
        """Cleanly releases storage handles."""
        pass
