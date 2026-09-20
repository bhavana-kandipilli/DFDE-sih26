#!/usr/bin/env python3
"""
Reusable Image Preprocessing Pipeline for Digital Field Drug Evidence System.
Provides:
- Image validation and integrity checking
- Standardized resizing and color normalization
- Blur detection (Laplacian variance)
- Brightness and contrast detection
- Multi-space color extraction (RGB, HSV, CIELAB)
- Statistical feature engineering for ML baselines
"""

import os
import cv2
import numpy as np
from typing import Dict, Any, Tuple, Optional

PREPROCESSING_VERSION = "v1.0.0"

class ImagePreprocessor:
    def __init__(self, target_size: Tuple[int, int] = (224, 224), min_blur_var: float = 100.0):
        self.target_size = target_size
        self.min_blur_var = min_blur_var

    def validate_image_file(self, file_path: str) -> bool:
        if not os.path.exists(file_path):
            return False
        if os.path.getsize(file_path) == 0:
            return False
        return True

    def load_and_preprocess(self, image_input) -> Dict[str, Any]:
        """
        Accepts either a file path (str) or raw binary bytes or numpy array.
        Returns extracted color spaces, quality scores, and standardized tensor/array.
        """
        if isinstance(image_input, str):
            if not self.validate_image_file(image_input):
                return {"valid": False, "error": "FILE_NOT_FOUND_OR_EMPTY"}
            img_bgr = cv2.imread(image_input)
        elif isinstance(image_input, bytes):
            nparr = np.frombuffer(image_input, np.uint8)
            img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif isinstance(image_input, np.ndarray):
            img_bgr = image_input.copy()
        else:
            return {"valid": False, "error": "UNSUPPORTED_INPUT_TYPE"}

        if img_bgr is None:
            return {"valid": False, "error": "DECODE_FAILED"}

        orig_h, orig_w, orig_c = img_bgr.shape

        # 1. Image Quality Assessment
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness_mean = float(np.mean(gray))
        contrast_std = float(np.std(gray))

        is_blurry = blur_score < self.min_blur_var
        is_underexposed = brightness_mean < 30.0
        is_overexposed = brightness_mean > 240.0
        quality_passed = (not is_blurry) and (not is_underexposed) and (not is_overexposed)

        # 2. Color Spaces
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        img_lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)

        # 3. Channel Statistics
        rgb_mean = [float(x) for x in np.mean(img_rgb, axis=(0, 1))]
        rgb_std = [float(x) for x in np.std(img_rgb, axis=(0, 1))]
        hsv_mean = [float(x) for x in np.mean(img_hsv, axis=(0, 1))]
        hsv_std = [float(x) for x in np.std(img_hsv, axis=(0, 1))]
        lab_mean = [float(x) for x in np.mean(img_lab, axis=(0, 1))]
        lab_std = [float(x) for x in np.std(img_lab, axis=(0, 1))]

        # 4. Standardized Resizing & Normalization for Vision Models
        resized_rgb = cv2.resize(img_rgb, self.target_size, interpolation=cv2.INTER_AREA)
        normalized_rgb = resized_rgb.astype(np.float32) / 255.0

        # Feature vector for ML baselines (18 color features + 3 quality features = 21 features)
        feature_vector = np.array(
            rgb_mean + rgb_std + hsv_mean + hsv_std + lab_mean + lab_std + [blur_score, brightness_mean, contrast_std],
            dtype=np.float32
        )

        return {
            "valid": True,
            "preprocessing_version": PREPROCESSING_VERSION,
            "original_dimensions": (orig_w, orig_h, orig_c),
            "quality": {
                "passed": quality_passed,
                "blur_score": round(blur_score, 2),
                "is_blurry": is_blurry,
                "brightness_mean": round(brightness_mean, 2),
                "is_underexposed": is_underexposed,
                "is_overexposed": is_overexposed,
                "contrast_std": round(contrast_std, 2)
            },
            "color_metrics": {
                "rgb_mean": rgb_mean, "rgb_std": rgb_std,
                "hsv_mean": hsv_mean, "hsv_std": hsv_std,
                "lab_mean": lab_mean, "lab_std": lab_std
            },
            "normalized_image": normalized_rgb,
            "feature_vector": feature_vector
        }
