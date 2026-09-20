import numpy as np
import cv2
from backend.app.services.quality_evaluator import QualityEvaluator

def create_synthetic_image(blur=False, brightness=128):
    # Create 200x200 RGB synthetic test image
    img = np.full((200, 200, 3), brightness, dtype=np.uint8)
    # Add a high-contrast rectangular border (reference card simulator)
    cv2.rectangle(img, (20, 20), (180, 180), (255, 255, 255), -1)
    cv2.rectangle(img, (40, 40), (160, 160), (0, 0, 0), -1)
    
    if blur:
        img = cv2.GaussianBlur(img, (25, 25), 0)
        
    _, buffer = cv2.imencode('.png', img)
    return buffer.tobytes()

def test_sharp_image_quality_passed():
    img_bytes = create_synthetic_image(blur=False, brightness=128)
    res = QualityEvaluator.evaluate_image_bytes(img_bytes)
    
    assert res["passed"] is True
    assert res["blur_score"] > 100.0
    assert res["color_card_detected"] is True

def test_blurry_image_quality_rejected():
    img_bytes = create_synthetic_image(blur=True, brightness=128)
    res = QualityEvaluator.evaluate_image_bytes(img_bytes)
    
    assert res["passed"] is False
    assert "QUALITY_REJECT_BLURRY" in res["failure_reasons"]
