import hashlib
import hmac
import json
import datetime
import bcrypt
import jwt
from typing import Dict, Any, Optional
from backend.app.core.config import settings

def hash_password(password: str) -> str:
    """Hashes a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def create_access_token(data: Dict[str, Any], expires_delta: Optional[datetime.timedelta] = None) -> str:
    """Encodes a JWT access token with role and subject claims."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and verifies a JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

def calculate_sha256(data_bytes: bytes) -> str:
    """Calculates SHA-256 hex digest of raw binary byte stream."""
    return hashlib.sha256(data_bytes).hexdigest()

def generate_hmac_signature(payload_hash: str, metadata_dict: Dict[str, Any]) -> str:
    """
    Computes HMAC-SHA256 signature combining image/spectral payload digest
    with canonical JSON representation of capture metadata.
    """
    canonical_meta = json.dumps(metadata_dict, sort_keys=True)
    meta_hash = hashlib.sha256(canonical_meta.encode("utf-8")).hexdigest()
    combined_message = f"{payload_hash}:{meta_hash}".encode("utf-8")
    secret_bytes = settings.HMAC_SECRET.encode("utf-8")
    return hmac.new(secret_bytes, combined_message, hashlib.sha256).hexdigest()

def verify_evidence_integrity(payload_bytes: bytes, metadata_dict: Dict[str, Any], expected_hmac: str) -> bool:
    """
    Verifies that raw payload bytes and metadata have not been altered or tampered with.
    """
    payload_hash = calculate_sha256(payload_bytes)
    recalculated_hmac = generate_hmac_signature(payload_hash, metadata_dict)
    return hmac.compare_digest(recalculated_hmac, expected_hmac)

def generate_chain_log_hash(previous_hash: str, payload_str: str) -> str:
    """
    Generates append-only audit log hash linking to previous log hash (blockchain-style ledger).
    """
    combined = f"{previous_hash or 'GENESIS_BLOCK'}:{payload_str}".encode("utf-8")
    return hashlib.sha256(combined).hexdigest()
