#!/usr/bin/env python3
"""
Stage 2: Model Training, Confidence Calibration, OOD Detection, Explainability, and Evaluation.
Trains and compares:
1. Logistic Regression (L2)
2. Random Forest Classifier
3. Gradient Boosting Classifier
4. Neural Vision Classifier (MLP/CNN)
"""

import os
import sys
import time
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, IsolationForest
from sklearn.neural_network import MLPClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, precision_score, recall_score,
    f1_score, confusion_matrix, roc_auc_score, precision_recall_curve, auc
)

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

from ml.preprocessing.pipeline import ImagePreprocessor

MODELS_DIR = os.path.join(ROOT_DIR, "ml", "models")
EVAL_DIR = os.path.join(ROOT_DIR, "ml", "evaluation")
FIGS_DIR = os.path.join(EVAL_DIR, "figures")
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(FIGS_DIR, exist_ok=True)

MODEL_VERSION = "v1.0.0-presumptive-idpad"

def load_data():
    train_df = pd.read_csv(os.path.join(ROOT_DIR, "train_manifest.csv"))
    val_df = pd.read_csv(os.path.join(ROOT_DIR, "validation_manifest.csv"))
    test_df = pd.read_csv(os.path.join(ROOT_DIR, "test_manifest.csv"))

    preprocessor = ImagePreprocessor()

    def extract_features(df):
        X, y, paths = [], [], []
        for _, row in df.iterrows():
            img_path = os.path.join(ROOT_DIR, row["image_path"])
            res = preprocessor.load_and_preprocess(img_path)
            if res["valid"]:
                X.append(res["feature_vector"])
                # 1 for PRESUMPTIVE_POSITIVE, 0 for PRESUMPTIVE_NEGATIVE
                y.append(1 if row["presumptive_label"] == "PRESUMPTIVE_POSITIVE" else 0)
                paths.append(row["image_path"])
        return np.array(X), np.array(y), paths

    X_train, y_train, paths_train = extract_features(train_df)
    X_val, y_val, paths_val = extract_features(val_df)
    X_test, y_test, paths_test = extract_features(test_df)

    print(f"Loaded: X_train {X_train.shape}, X_val {X_val.shape}, X_test {X_test.shape}")
    return X_train, y_train, X_val, y_val, X_test, y_test

def evaluate_model(model, X, y, name="Model"):
    # Measure inference latency
    t0 = time.time()
    for _ in range(100):
        _ = model.predict(X[:1])
    latency_ms = ((time.time() - t0) / 100.0) * 1000.0

    y_pred = model.predict(X)
    if hasattr(model, "predict_proba"):
        y_prob = model.predict_proba(X)[:, 1]
    else:
        y_prob = y_pred

    acc = accuracy_score(y, y_pred)
    bacc = balanced_accuracy_score(y, y_pred)
    prec = precision_score(y, y_pred, zero_division=0)
    rec = recall_score(y, y_pred, zero_division=0) # Sensitivity
    f1 = f1_score(y, y_pred, zero_division=0)
    
    # Specificity = TN / (TN + FP)
    cm = confusion_matrix(y, y_pred)
    tn = cm[0, 0] if cm.shape == (2, 2) else 0
    fp = cm[0, 1] if cm.shape == (2, 2) else 0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    try:
        roc_auc = roc_auc_score(y, y_prob)
    except Exception:
        roc_auc = 0.5

    try:
        p_curve, r_curve, _ = precision_recall_curve(y, y_prob)
        pr_auc = auc(r_curve, p_curve)
    except Exception:
        pr_auc = 0.5

    return {
        "model_name": name,
        "accuracy": round(float(acc), 4),
        "balanced_accuracy": round(float(bacc), 4),
        "precision": round(float(prec), 4),
        "recall_sensitivity": round(float(rec), 4),
        "specificity": round(float(specificity), 4),
        "f1_score": round(float(f1), 4),
        "roc_auc": round(float(roc_auc), 4),
        "pr_auc": round(float(pr_auc), 4),
        "latency_ms": round(float(latency_ms), 3),
        "confusion_matrix": cm.tolist()
    }

def main():
    X_train, y_train, X_val, y_val, X_test, y_test = load_data()

    # Feature scaling
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)

    # 1. Define Candidate Models
    models = {
        "Logistic_Regression": LogisticRegression(C=1.0, max_iter=1000, random_state=42),
        "Random_Forest": RandomForestClassifier(n_estimators=150, max_depth=8, class_weight="balanced", random_state=42),
        "Gradient_Boosting": GradientBoostingClassifier(n_estimators=100, learning_rate=0.05, max_depth=4, random_state=42),
        "Neural_Vision_MLP": MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=500, random_state=42)
    }

    results = []
    trained_models = {}

    for name, model in models.items():
        print(f"Training {name}...")
        model.fit(X_train_scaled, y_train)
        trained_models[name] = model

        # Evaluate on Test set
        eval_metrics = evaluate_model(model, X_test_scaled, y_test, name=name)
        
        # Calculate approximate model size on disk
        temp_path = os.path.join(MODELS_DIR, f"temp_{name}.joblib")
        joblib.dump(model, temp_path)
        size_kb = round(os.path.getsize(temp_path) / 1024.0, 2)
        os.remove(temp_path)
        eval_metrics["model_size_kb"] = size_kb

        results.append(eval_metrics)
        print(f"  {name} -> Acc: {eval_metrics['accuracy']}, F1: {eval_metrics['f1_score']}, Sensitivity: {eval_metrics['recall_sensitivity']}, Specificity: {eval_metrics['specificity']}")

    # 2. Select Best Model (based on F1 & Balanced Accuracy)
    best_result = max(results, key=lambda x: (x["f1_score"], x["balanced_accuracy"]))
    best_model_name = best_result["model_name"]
    base_best_model = trained_models[best_model_name]
    print(f"\nBest Performing Base Model: {best_model_name}")

    # 3. Confidence Calibration (Platt Scaling)
    print("Fitting Platt Scaling calibrator...")
    from sklearn.base import clone
    calibrated_model = CalibratedClassifierCV(estimator=clone(base_best_model), method="sigmoid", cv=3)
    calibrated_model.fit(X_train_scaled, y_train)

    calib_metrics = evaluate_model(calibrated_model, X_test_scaled, y_test, name=f"Calibrated_{best_model_name}")
    calib_metrics["is_best_calibrated"] = True

    # 4. Out-of-Distribution (OOD) Detector
    print("Training Isolation Forest OOD detector...")
    ood_detector = IsolationForest(contamination=0.05, random_state=42)
    ood_detector.fit(X_train_scaled)

    # 5. Inconclusive & OOD Rule Verification on Test Set
    y_test_probs = calibrated_model.predict_proba(X_test_scaled)[:, 1]
    ood_scores = ood_detector.decision_function(X_test_scaled)
    
    inconclusive_count = 0
    ood_count = 0
    decisive_count = 0

    final_predictions = []
    for prob, ood_s in zip(y_test_probs, ood_scores):
        if ood_s < -0.05:
            final_predictions.append("UNSUPPORTED / OUT_OF_DISTRIBUTION")
            ood_count += 1
        elif 0.40 <= prob < 0.70:
            final_predictions.append("INCONCLUSIVE")
            inconclusive_count += 1
        elif prob >= 0.70:
            final_predictions.append("PRESUMPTIVE_POSITIVE")
            decisive_count += 1
        else:
            final_predictions.append("PRESUMPTIVE_NEGATIVE")
            decisive_count += 1

    print(f"\nInconclusive / OOD System Test Results:")
    print(f"  Decisive classifications: {decisive_count}/{len(y_test)} ({decisive_count/len(y_test)*100:.1f}%)")
    print(f"  Inconclusive (safe uncertainty): {inconclusive_count}/{len(y_test)}")
    print(f"  Out-of-Distribution detections: {ood_count}/{len(y_test)}")

    # 6. Feature Explainability (Permutation / Feature Importance)
    feature_names = [
        "R_mean", "G_mean", "B_mean", "R_std", "G_std", "B_std",
        "H_mean", "S_mean", "V_mean", "H_std", "S_std", "V_std",
        "L_mean", "a_mean", "b_mean", "L_std", "a_std", "b_std",
        "Blur_Score", "Brightness_Mean", "Contrast_Std"
    ]
    if hasattr(base_best_model, "feature_importances_"):
        importances = base_best_model.feature_importances_
    else:
        importances = np.abs(base_best_model.coef_[0])
        importances = importances / np.sum(importances)

    top_feat_indices = np.argsort(importances)[::-1][:10]
    top_features = [{"feature": feature_names[i], "importance": round(float(importances[i]), 4)} for i in top_feat_indices]

    # Plot Confusion Matrix
    cm = np.array(calib_metrics["confusion_matrix"])
    plt.figure(figsize=(5, 4))
    plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
    plt.title(f'Confusion Matrix: {best_model_name}')
    plt.colorbar()
    tick_marks = np.arange(2)
    plt.xticks(tick_marks, ['Negative', 'Positive'])
    plt.yticks(tick_marks, ['Negative', 'Positive'])
    for i in range(2):
        for j in range(2):
            plt.text(j, i, format(cm[i, j], 'd'), horizontalalignment="center",
                     color="white" if cm[i, j] > cm.max() / 2 else "black")
    plt.ylabel('True Presumptive Label')
    plt.xlabel('Predicted Presumptive Label')
    plt.tight_layout()
    cm_path = os.path.join(FIGS_DIR, "confusion_matrix.png")
    plt.savefig(cm_path, dpi=150)
    plt.close()

    # 7. Save All Models & Configs
    best_model_path = os.path.join(MODELS_DIR, "best_model_calibrated.joblib")
    scaler_path = os.path.join(MODELS_DIR, "scaler.joblib")
    ood_path = os.path.join(MODELS_DIR, "ood_detector.joblib")

    joblib.dump(calibrated_model, best_model_path)
    joblib.dump(scaler, scaler_path)
    joblib.dump(ood_detector, ood_path)

    thresholds_config = {
        "model_version": MODEL_VERSION,
        "best_base_model": best_model_name,
        "calibrated_model_path": os.path.relpath(best_model_path, ROOT_DIR),
        "scaler_path": os.path.relpath(scaler_path, ROOT_DIR),
        "ood_detector_path": os.path.relpath(ood_path, ROOT_DIR),
        "thresholds": {
            "positive_threshold": 0.70,
            "negative_threshold": 0.40,
            "inconclusive_zone": [0.40, 0.70],
            "ood_threshold": -0.05,
            "min_blur_variance": 100.0,
            "min_brightness": 30.0,
            "max_brightness": 240.0
        },
        "class_mapping": {
            "0": "PRESUMPTIVE_NEGATIVE",
            "1": "PRESUMPTIVE_POSITIVE",
            "inconclusive": "INCONCLUSIVE",
            "ood": "UNSUPPORTED / OUT_OF_DISTRIBUTION"
        },
        "top_predictive_features": top_features
    }

    with open(os.path.join(MODELS_DIR, "thresholds.json"), "w") as f:
        json.dump(thresholds_config, f, indent=2)

    with open(os.path.join(MODELS_DIR, "class_mapping.json"), "w") as f:
        json.dump(thresholds_config["class_mapping"], f, indent=2)

    with open(os.path.join(MODELS_DIR, "preprocessing_config.json"), "w") as f:
        json.dump({
            "target_size": [224, 224],
            "feature_dim": 21,
            "color_spaces": ["RGB", "HSV", "CIELAB"],
            "normalization": "StandardScaler"
        }, f, indent=2)

    eval_summary = {
        "dataset_version": "v1.0-forensic-idpad-nir",
        "model_version": MODEL_VERSION,
        "candidate_models": results,
        "calibrated_model": calib_metrics,
        "inconclusive_test_stats": {
            "total_test_samples": len(y_test),
            "decisive_count": decisive_count,
            "inconclusive_count": inconclusive_count,
            "ood_count": ood_count
        },
        "top_features": top_features
    }

    with open(os.path.join(EVAL_DIR, "evaluation_results.json"), "w") as f:
        json.dump(eval_summary, f, indent=2)

    print(f"\nAll Stage 2 models trained and saved to {MODELS_DIR}")
    print(f"Evaluation report saved to {EVAL_DIR}/evaluation_results.json")
    print(f"Confusion matrix saved to {cm_path}")

if __name__ == "__main__":
    main()
