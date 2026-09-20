# MODEL_CARD.md - Calibrated Presumptive Interpretation Model

## 1. Model Details
- **Model Name**: Calibrated Field Presumptive Interpretation Engine
- **Model Version**: `v1.0.0-presumptive-idpad`
- **Architecture**:
  - Feature Extractor: 21-dimensional normalized colorimetric tensor (RGB, HSV, CIELAB channel means and standard deviations, plus Laplacian blur variance, mean brightness, and contrast ratio).
  - Primary Estimator: Logistic Regression with balanced regularized formulation.
  - Probability Calibrator: Platt Scaling (sigmoid calibration via cross-validated `CalibratedClassifierCV`).
  - Anomaly & OOD Detector: `IsolationForest` fitted on in-distribution training features ($N=261$).
- **License**: Research & Field Evidence Prototyping License
- **Framework**: Python 3.13 / scikit-learn / OpenCV

---

## 2. Intended Use
- **Primary Use**: Screening and interpretation of field chemical test strip reactions (e.g. 12-lane idPAD paper analytical devices) to provide objective colorimetric interpretation for field personnel.
- **Target Setting**: Law enforcement field operations, borders and customs checkpoints, preliminary crime scene processing.
- **Target Users**: Trained field officers and forensic technicians.

---

## 3. Prohibited Use Cases
- **NO Conclusive Criminal Evidence**: The model MUST NOT be represented in court as a conclusive chemical determination. It is presumptive only.
- **NO Bypassing of Inconclusive Decisions**: Predictions falling in the inconclusive band ($0.40 - 0.70$) must be treated as inconclusive and never forced into positive/negative.
- **NO Uncalibrated / Degraded Imagery**: Images failing blur thresholds ($< 100.0$) or extreme exposure must be rejected.

---

## 4. Training Data & Leakage Prevention
- **Dataset**: PMC7332374 / NIHMS1576105 forensic dataset (374 total field card captures across 278 blinded formulations and 96 cutting agents/adulterants).
- **Ground Truth Verification**: All street samples and blinded matrices verified by the Berrien County Crime Laboratory using FTIR spectrometry and GC-MS.
- **Leakage Safeguards**: Group-aware split partitioning based on physical sample identifier. Zero physical sample overlap between training ($N=261$), validation ($N=56$), and test ($N=57$) sets.

---

## 5. Quantitative Test Performance
Evaluated on the holdout test set ($N=57$):
- **Accuracy**: 85.96%
- **Balanced Accuracy**: 82.30%
- **F1 Score**: 0.8974
- **Recall (Sensitivity on Presumptive Positive)**: **94.59%**
- **Specificity (True Negative Rate)**: **70.00%**
- **ROC-AUC**: 0.8865
- **PR-AUC**: 0.9283
- **Inference Latency**: **0.044 ms** per sample
- **Model Size on Disk**: **2.6 KB** (Calibrated estimator), **1.0 MB** (OOD detector)

---

## 6. Scientific Feature Importance (Explainability)
The top predictive features identified by the model:
1. `B_std` (Blue channel variance across lanes): Importance 0.2014. Captures localized colorimetric shifts (e.g. Cobalt Thiocyanate turquoise blue reaction in lanes A–C).
2. `b_std` (CIELAB b* variance across lanes): Importance 0.1169. Captures blue-to-yellow shifts across reagent test spots.
3. `R_std` (Red channel variance across lanes): Importance 0.1019. Captures Marquis / Liebermann / Fast Blue reddish/orange reactions.
4. `H_mean` (Hue mean): Importance 0.0978. Overall reaction spectrum tone.
5. `Blur_Score` (Laplacian variance): Importance 0.0506. Image focus guard.

---

## 7. Known Biases & Environmental Boundaries
- **Lighting Cast**: Model was trained on captures in standardized LED lightboxes. Ambient captures under monochromatic yellow streetlights may distort hue without white-balance reference cards.
- **Extreme Dilution**: Samples with drug concentration below $5\%$ by mass may produce low-intensity color shifts that fall into the `INCONCLUSIVE` zone.
