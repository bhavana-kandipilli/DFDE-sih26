#!/usr/bin/env python3
"""
Upload Security, Validation, and Storage Safety Module.
Enforces defense-in-depth controls:
1. Strict file size limits (Max 15 MB)
2. Authentic binary magic byte verification (JPEG, PNG, WebP)
3. Decompression bomb mitigation (Max 8192x8192, 32MP limit)
4. Path traversal mitigation (Boundary validation within STORAGE_DIR)
5. Filename sanitization
"""

import os
import re
import cv2
import numpy as np
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from backend.app.core.config import settings

# Security thresholds
MAX_UPLOAD_SIZE = getattr(settings, "MAX_UPLOAD_SIZE_BYTES", 15 * 1024 * 1024) # 15 MB
MAX_DIMENSION = getattr(settings, "MAX_IMAGE_DIMENSION", 8192) # 8192 px
MAX_PIXELS = 32_000_000 # 32 Megapixels

MAGIC_SIGNATURES = {
    "jpeg": [b"\xFF\xD8\xFF"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "webp": [b"RIFF"] # plus WEBP at byte 8
}

def detect_image_format(raw_bytes: bytes) -> Optional[str]:
    """Inspects authentic binary magic bytes rather than trusting file extensions."""
    if len(raw_bytes) < 12:
        return None
    
    # JPEG
    if raw_bytes.startswith(b"\xFF\xD8\xFF"):
        return "jpeg"
    
    # PNG
    if raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    
    # WebP
    if raw_bytes.startswith(b"RIFF") and raw_bytes[8:12] == b"WEBP":
        return "webp"
        
    return None

def validate_uploaded_image(raw_bytes: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Validates uploaded evidence binary against size limits, binary magic bytes,
    and decompression bomb memory exhaustion vulnerabilities.
    """
    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty evidence binary provided."
        )

    # 1. File size limit enforcement
    if len(raw_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Payload Too Large: Evidence file size ({round(len(raw_bytes)/(1024*1024), 2)} MB) exceeds maximum permitted limit ({int(MAX_UPLOAD_SIZE/(1024*1024))} MB)."
        )

    # 2. Magic byte verification
    fmt = detect_image_format(raw_bytes)
    if not fmt:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported Media Type: Only authentic JPEG, PNG, and WebP evidence images are permitted. Executables, scripts, SVGs, and generic documents are strictly rejected."
        )

    # 3. Decompression bomb & memory exhaustion defense
    nparr = np.frombuffer(raw_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corrupted or malformed image binary failed to decode."
        )

    h, w = img.shape[:2]
    if w > MAX_DIMENSION or h > MAX_DIMENSION or (w * h) > MAX_PIXELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unprocessable Entity: Image dimensions ({w}x{h}, {w*h} pixels) exceed safety ceiling (Max {MAX_DIMENSION}px / 32MP) to prevent decompression bomb memory exhaustion."
        )

    return {
        "format": fmt,
        "width": w,
        "height": h,
        "pixels": w * h,
        "size_bytes": len(raw_bytes),
        "sanitized_filename": sanitize_filename(filename) if filename else f"evidence_{fmt}"
    }

def safe_storage_path(relative_path: str, base_dir: Optional[str] = None) -> str:
    """
    Guarantees that a storage path cannot escape base_dir via directory traversal.
    """
    base = os.path.abspath(base_dir or settings.STORAGE_DIR)
    
    # Reject explicit traversal tokens
    if ".." in relative_path or relative_path.startswith("/") or relative_path.startswith("\\"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security violation: Path traversal attempt detected."
        )

    full_path = os.path.abspath(os.path.join(base, relative_path))
    if not full_path.startswith(base):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security violation: Path escapes authorized storage boundary."
        )

    return full_path

def sanitize_filename(filename: str) -> str:
    """Sanitizes user-provided filename to prevent path injection and control chars."""
    if not filename:
        return "unnamed_evidence"
    # Remove directory path separators
    clean = os.path.basename(filename)
    # Strip any dangerous chars, keep only alphanumeric, dots, hyphens, underscores
    clean = re.sub(r"[^a-zA-Z0-9._-]", "_", clean)
    # Prevent leading dots (hidden files)
    clean = clean.lstrip(".")
    return clean or "sanitized_evidence"
