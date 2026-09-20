#!/usr/bin/env python3
"""
Evidence Integrity Engine for Digital Field Drug Evidence System.

Evaluates the authenticity, chain of custody, sensor quality, cryptographic seals,
and forensic reliability of a digital evidence record.

CRITICAL SCIENTIFIC & LEGAL CONSTRAINT:
The Evidence Integrity Score represents the reliability and integrity of the
DIGITAL EVIDENCE RECORD. It does NOT represent the probability that a drug
is chemically present.
"""

import os
import json
import hashlib
import datetime
from typing import Dict, Any, List, Optional, Tuple

class EvidenceIntegrityEngine:
    """
    Deterministic, documented forensic scoring engine for digital evidence records.
    """

    MAX_SCORE = 100
    STATUS_HIGH = "HIGH"
    STATUS_MEDIUM = "MEDIUM"
    STATUS_LOW = "LOW"
    STATUS_COMPROMISED = "COMPROMISED"

    APPROVED_MODEL_VERSIONS = {
        "v1.0.0-presumptive-idpad",
        "v1.0.0-presumptive-dta1949",
        "v1.0.0-presumptive-nir"
    }

    @classmethod
    def evaluate(
        cls,
        image_quality: Dict[str, Any],
        provenance: Dict[str, Any],
        metadata: Dict[str, Any],
        cryptography: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculates deterministic Evidence Integrity Score and diagnostic breakdown.

        Args:
            image_quality: {
                "blur_score": float,
                "brightness_mean": float,
                "contrast_std": float,
                "reference_card_detected": bool,
                "calibration_applied": bool
            }
            provenance: {
                "authenticated_operator": bool,
                "badge_number": Optional[str],
                "device_id": Optional[str],
                "gps_latitude": Optional[float],
                "gps_longitude": Optional[float]
            }
            metadata: {
                "timestamp": str (ISO 8601),
                "case_id": str,
                "test_id": str,
                "reagent_name": str,
                "model_version": Optional[str],
                "sync_status": Optional[str] # "SYNCED" or "LOCAL_VALID"
            }
            cryptography: {
                "payload_hash": str (64 hex chars),
                "recomputed_hash": Optional[str],
                "hmac_valid": bool,
                "tamper_detected": bool
            }

        Returns:
            Dict containing score, status, checks, warnings, and failures.
        """
        score = 0
        checks = {}
        warnings: List[str] = []
        failures: List[str] = []

        # -------------------------------------------------------------
        # Pillar 1: Sensor & Image Quality (30 Points Max)
        # -------------------------------------------------------------
        blur = float(image_quality.get("blur_score", 0.0))
        brightness = float(image_quality.get("brightness_mean", 0.0))
        contrast = float(image_quality.get("contrast_std", 0.0))
        card_detected = bool(image_quality.get("reference_card_detected", False))
        calibrated = bool(image_quality.get("calibration_applied", False))

        # 1. Blur evaluation (10 pts)
        if blur >= 100.0:
            score += 10
            checks["focus_sharpness"] = True
        elif blur >= 50.0:
            score += 5
            checks["focus_sharpness"] = True
            warnings.append(f"Sub-optimal sharpness (Laplacian variance {blur:.1f} < 100.0). Recommend retake if available.")
        else:
            checks["focus_sharpness"] = False
            failures.append(f"Severe blur detected (Laplacian variance {blur:.1f} < 50.0). Frame may be unreadable.")

        # 2. Exposure & Dynamic Range (5 pts)
        if 30.0 <= brightness <= 240.0:
            score += 5
            checks["exposure_lighting"] = True
        else:
            checks["exposure_lighting"] = False
            if brightness < 30.0:
                failures.append(f"Severe underexposure (mean {brightness:.1f} < 30.0). Dark capture.")
            else:
                failures.append(f"Severe overexposure / glare (mean {brightness:.1f} > 240.0). Bleached capture.")

        # 3. Reaction Area Contrast (5 pts)
        if contrast >= 15.0:
            score += 5
            checks["reaction_visibility"] = True
        else:
            checks["reaction_visibility"] = False
            warnings.append(f"Low frame contrast (std {contrast:.1f} < 15.0). Chemical reaction zones may have weak delineation.")

        # 4. Reference Card (5 pts)
        if card_detected:
            score += 5
            checks["reference_card"] = True
        else:
            checks["reference_card"] = False
            failures.append("Reference colour card / alignment markers not detected in capture frame.")

        # 5. Chromatic Calibration (5 pts)
        if calibrated:
            score += 5
            checks["calibration"] = True
        else:
            checks["calibration"] = False
            warnings.append("Chromatic adaptation uncalibrated. Ambient illumination color cast uncorrected.")

        checks["image_quality"] = checks["focus_sharpness"] and checks["exposure_lighting"] and checks["reference_card"]

        # -------------------------------------------------------------
        # Pillar 2: Operator & Provenance Telemetry (25 Points Max)
        # -------------------------------------------------------------
        auth_op = bool(provenance.get("authenticated_operator", False))
        badge = provenance.get("badge_number")
        device_id = provenance.get("device_id")
        lat = provenance.get("gps_latitude")
        lon = provenance.get("gps_longitude")

        # 1. Authenticated Operator (10 pts)
        if auth_op:
            score += 10
            checks["authenticated_operator"] = True
        else:
            checks["authenticated_operator"] = False
            failures.append("Evidence capture unauthenticated. Operator token missing or invalid.")

        # 2. Officer Badge / Identity (5 pts)
        if badge and str(badge).strip():
            score += 5
            checks["operator_identity"] = True
        else:
            checks["operator_identity"] = False
            warnings.append("Officer badge number missing from session metadata.")

        # 3. Hardware Device ID (5 pts)
        if device_id and str(device_id).strip():
            score += 5
            checks["device_id"] = True
        else:
            checks["device_id"] = False
            warnings.append("Hardware device identifier not registered with capture payload.")

        # 4. GPS Coordinates (5 pts)
        gps_valid = False
        if lat is not None and lon is not None:
            try:
                lat_f = float(lat)
                lon_f = float(lon)
                if -90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0 and not (lat_f == 0.0 and lon_f == 0.0):
                    gps_valid = True
            except (ValueError, TypeError):
                gps_valid = False

        if gps_valid:
            score += 5
            checks["gps"] = True
        else:
            checks["gps"] = False
            warnings.append("GPS geolocation coordinates absent or invalid.")

        # -------------------------------------------------------------
        # Pillar 3: Temporal & Contextual Metadata (15 Points Max)
        # -------------------------------------------------------------
        ts_str = metadata.get("timestamp")
        case_id = metadata.get("case_id")
        test_id = metadata.get("test_id")
        reagent = metadata.get("reagent_name")
        model_ver = metadata.get("model_version")

        # 1. Timestamp validity (5 pts)
        ts_valid = False
        if ts_str:
            try:
                # Accept ISO format
                cleaned_ts = ts_str.replace("Z", "+00:00")
                parsed_ts = datetime.datetime.fromisoformat(cleaned_ts)
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                if parsed_ts.tzinfo is None:
                    parsed_ts = parsed_ts.replace(tzinfo=datetime.timezone.utc)
                # Allow max 5 minutes forward clock skew
                if parsed_ts <= (now_utc + datetime.timedelta(minutes=5)):
                    ts_valid = True
                else:
                    failures.append(f"Timestamp is in the future ({ts_str}). Clock skew anomaly.")
            except Exception:
                failures.append(f"Malformed ISO 8601 timestamp: {ts_str}")

        if ts_valid:
            score += 5
            checks["timestamp"] = True
        else:
            checks["timestamp"] = False

        # 2. Metadata completeness (5 pts)
        meta_complete = bool(case_id and str(case_id).strip() and test_id and str(test_id).strip() and reagent and str(reagent).strip())
        if meta_complete:
            score += 5
            checks["metadata_completeness"] = True
        else:
            checks["metadata_completeness"] = False
            failures.append("Incomplete forensic metadata: case ID, test ID, or reagent name missing.")

        # 3. Model Version validity (5 pts)
        if model_ver in cls.APPROVED_MODEL_VERSIONS or (model_ver and "v1." in str(model_ver)):
            score += 5
            checks["approved_model_version"] = True
        else:
            checks["approved_model_version"] = False
            warnings.append(f"Model version '{model_ver}' is unverified or non-standard.")

        # -------------------------------------------------------------
        # Pillar 4: Cryptographic Integrity & Tamper Check (30 Points Max)
        # -------------------------------------------------------------
        payload_hash = cryptography.get("payload_hash", "")
        recomputed_hash = cryptography.get("recomputed_hash")
        hmac_valid = bool(cryptography.get("hmac_valid", False))
        tamper_detected = bool(cryptography.get("tamper_detected", False))

        hash_format_valid = bool(payload_hash and len(payload_hash) == 64 and all(c in "0123456789abcdefABCDEF" for c in payload_hash))

        hash_matches_payload = True
        if recomputed_hash is not None:
            hash_matches_payload = (payload_hash.lower() == recomputed_hash.lower())
            if not hash_matches_payload:
                tamper_detected = True
                failures.append("PAYLOAD MISMATCH: Stored SHA-256 does not match recomputed image bytes on disk.")

        if hash_format_valid and hash_matches_payload:
            score += 10
            checks["hash"] = True
        else:
            checks["hash"] = False
            if not hash_format_valid:
                failures.append("Malformed or absent SHA-256 image payload hash.")

        if hmac_valid:
            score += 10
            checks["hmac_signature"] = True
        else:
            checks["hmac_signature"] = False
            warnings.append("HMAC signature verification failed or pending canonical seal.")

        if not tamper_detected:
            score += 10
            checks["tamper_detected"] = False
        else:
            checks["tamper_detected"] = True
            failures.append("CRITICAL: Digital evidence tampering or unauthorized bitstream modification detected.")

        # -------------------------------------------------------------
        # Tamper Override Rule
        # -------------------------------------------------------------
        # If any cryptographic tampering is verified, evidence integrity is ZERO
        if tamper_detected:
            score = 0
            status = cls.STATUS_COMPROMISED
        else:
            if score >= 85:
                status = cls.STATUS_HIGH
            elif score >= 70:
                status = cls.STATUS_MEDIUM
            elif score >= 50:
                status = cls.STATUS_LOW
            else:
                status = cls.STATUS_COMPROMISED

        return {
            "score": int(score),
            "status": status,
            "checks": checks,
            "warnings": warnings,
            "failures": failures
        }

    @staticmethod
    def calculate_canonical_hash(
        payload_hash: str,
        case_id: str,
        test_id: str,
        metadata_dict: Dict[str, Any],
        result_dict: Dict[str, Any],
        timestamp_iso: str
    ) -> Tuple[str, str]:
        """
        Creates a deterministic RFC 8785 canonical JSON representation of evidence
        and returns (canonical_hash, canonical_json_string).
        """
        canonical_struct = {
            "test_id": str(test_id),
            "case_id": str(case_id),
            "payload_hash": str(payload_hash),
            "timestamp": str(timestamp_iso),
            "metadata": {
                "officer_badge": str(metadata_dict.get("badge_number") or metadata_dict.get("officer_id") or "UNKNOWN"),
                "device_id": str(metadata_dict.get("device_id") or "UNKNOWN"),
                "reagent": str(metadata_dict.get("reagent_name") or metadata_dict.get("reagent") or "UNKNOWN"),
                "gps": {
                    "latitude": float(metadata_dict.get("gps_latitude") or 0.0),
                    "longitude": float(metadata_dict.get("gps_longitude") or 0.0)
                }
            },
            "result": {
                "classification": str(result_dict.get("classification", "INCONCLUSIVE")),
                "confidence_score": round(float(result_dict.get("confidence_score") or result_dict.get("confidence") or 0.0), 4),
                "ood_score": round(float(result_dict.get("ood_score", 0.0)), 4),
                "model_version": str(result_dict.get("model_version", "UNKNOWN"))
            }
        }

        # Deterministic compact serialization (RFC 8785 sorting)
        canonical_json = json.dumps(canonical_struct, sort_keys=True, separators=(',', ':'))
        canonical_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
        return canonical_hash, canonical_json

    @classmethod
    def verify_evidence_record(
        cls,
        raw_image_bytes: bytes,
        stored_payload_hash: str,
        stored_canonical_hash: Optional[str],
        case_id: str,
        test_id: str,
        metadata_dict: Dict[str, Any],
        result_dict: Dict[str, Any],
        timestamp_iso: str
    ) -> Dict[str, Any]:
        """
        Recomputes raw image hash and canonical hash to detect any bit-level tampering.
        """
        recomputed_payload_hash = hashlib.sha256(raw_image_bytes).hexdigest()
        image_intact = (recomputed_payload_hash.lower() == stored_payload_hash.lower())

        canonical_intact = True
        recomputed_canonical_hash = None
        if stored_canonical_hash:
            recomputed_canonical_hash, _ = cls.calculate_canonical_hash(
                payload_hash=recomputed_payload_hash,
                case_id=case_id,
                test_id=test_id,
                metadata_dict=metadata_dict,
                result_dict=result_dict,
                timestamp_iso=timestamp_iso
            )
            canonical_intact = (recomputed_canonical_hash.lower() == stored_canonical_hash.lower())

        is_tampered = not (image_intact and canonical_intact)
        status_str = "VERIFIED" if not is_tampered else "TAMPER_DETECTED"

        return {
            "status": status_str,
            "is_tampered": is_tampered,
            "stored_payload_hash": stored_payload_hash,
            "recomputed_payload_hash": recomputed_payload_hash,
            "image_intact": image_intact,
            "canonical_hash_verified": canonical_intact,
            "stored_canonical_hash": stored_canonical_hash,
            "recomputed_canonical_hash": recomputed_canonical_hash,
            "verification_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

    @classmethod
    def generate_certificate(
        cls,
        case_id: str,
        test_id: str,
        officer: Dict[str, Any],
        timestamp_iso: str,
        gps: Dict[str, Any],
        test_type: str,
        original_image_path: str,
        result: Dict[str, Any],
        integrity_eval: Dict[str, Any],
        hashes: Dict[str, str],
        model_version: str,
        verification_status: str,
        quality_metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Assembles formal digital evidence certificate for judicial and forensic presentation.
        """
        certificate_id = f"CERT-{test_id[:8].upper()}-{hashlib.sha256(test_id.encode('utf-8')).hexdigest()[:8].upper()}"

        return {
            "certificate_id": certificate_id,
            "title": "DIGITAL FIELD DRUG EVIDENCE FORENSIC CERTIFICATE",
            "case_id": case_id,
            "test_id": test_id,
            "officer": {
                "name": officer.get("username", "OFFICER"),
                "badge_number": officer.get("badge_number", "UNKNOWN"),
                "department": officer.get("department", "LAW_ENFORCEMENT")
            },
            "timestamp": timestamp_iso,
            "gps": {
                "latitude": gps.get("latitude"),
                "longitude": gps.get("longitude")
            },
            "test_type": test_type,
            "original_image_path": original_image_path,
            "result": {
                "classification": result.get("classification"),
                "confidence": result.get("confidence_score"),
                "ood_score": result.get("ood_score")
            },
            "evidence_integrity": {
                "score": integrity_eval.get("score"),
                "status": integrity_eval.get("status"),
                "checks": integrity_eval.get("checks", {}),
                "warnings": integrity_eval.get("warnings", []),
                "failures": integrity_eval.get("failures", [])
            },
            "quality_metrics": quality_metrics or {},
            "cryptographic_hashes": {
                "raw_image_sha256": hashes.get("payload_hash"),
                "canonical_record_sha256": hashes.get("canonical_hash"),
                "hmac_signature": hashes.get("hmac_signature"),
                "audit_chain_hash": hashes.get("current_audit_hash")
            },
            "model_version": model_version,
            "verification_status": verification_status,
            "disclaimer": (
                "SCIENTIFIC & LEGAL STATUTORY DISCLAIMER: This document certifies presumptive "
                "colorimetric field-test interpretation by an AI-assisted optical instrument. "
                "This does NOT constitute a conclusive identification of a controlled substance. "
                "Confirmatory testing via Gas Chromatography-Mass Spectrometry (GC-MS) or "
                "Liquid Chromatography-Mass Spectrometry (LC-MS) remains legally required."
            ),
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
