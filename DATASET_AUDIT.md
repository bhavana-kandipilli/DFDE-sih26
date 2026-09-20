# DATASET_AUDIT.md - Multi-Modal Forensic Dataset Audit & Integrity Report

## 1. Executive Summary
This audit provides full transparency into all forensic datasets integrated into the **Digital Field Drug Evidence System** under **Stage 1 (Data Pipeline)**:
- **Dataset Version**: `v1.0-forensic-idpad-nir`
- **Total Processed Reaction Images**: 374 high-resolution paper analytical device (`idPAD`) test card captures
- **Raw Spectral NIR Datasets**: 24 files across 5 portable spectrometer models
- **Sample-Averaged NIR Datasets**: 24 files
- **Total Unique Formulations / Samples**: 374 physical sample groups
- **Exact File Duplicates**: 0 (Verified via SHA-256 hash collision checks)
- **Data Leakage Safeguard**: Group-aware split partitioning (70% train / 15% val / 15% test) strictly enforcing zero sample ID overlap.

> [!IMPORTANT]
> **MANDATORY SCIENTIFIC CONSTRAINT**:
> All datasets represent **presumptive** field chemical or spectroscopic tests. The system strictly predicts:
> - `PRESUMPTIVE_POSITIVE`
> - `PRESUMPTIVE_NEGATIVE`
> - `INCONCLUSIVE`
> - `UNSUPPORTED / OUT_OF_DISTRIBUTION`
> Confirmatory chemical identification (GC-MS / LC-MS) remains legally required.

---

## 2. Comprehensive Dataset Inventory

### A. Primary Visual Reaction Dataset: PMC7332374 / NIHMS1576105 (`idPAD`)
- **Source**: *idPAD: Paper Analytical Device for Presumptive Identification of Illicit Drugs* (Weaver et al., PMC7332374).
- **Format**: High-resolution JPEG images extracted from archival forensic supplement.
- **Apparatus**: 12-lane microfluidic paper test strip in a standardized portable LED lightbox enclosure.
- **Confirmation Method**: All street samples and blinded test compounds verified by Berrien County Crime Laboratory via FTIR and GC-MS.
- **Image Count**:
  - Blinded Study (`Section S7`): 278 images corresponding 1-to-1 with Table 0 blinded formulation samples.
  - Adulterants & Cutting Agents (`Section S13`): 96 images corresponding to Table 2 compounds.
  - Total Usable Images: 374.
- **Substances Included**:
  - Controlled Drugs: Cocaine HCl, Crack Cocaine, Heroin, Methamphetamine, Opioids.
  - Cutting Agents & Excipients: Lactose, Caffeine, Inositol, Starch, Acetaminophen, Alizarian, Ciprofloxacin, etc.
- **Dimensions**: Ranging from $286 \times 161$ to $317 \times 178$ pixels ($3$-channel RGB).
- **Color Metric Extractions**: Full RGB, HSV, and CIELAB space statistics computed per sample.

### B. Secondary Spectral Modality: Portable NIR Spectrometry (`dataset.zip`)
- **Source**: Multi-instrument portable NIR spectrometry study.
- **Format**: Excel (`.xlsx`) raw and sample-averaged reflectance spectra across $800 - 2500 \text{ nm}$.
- **Sensors / Instruments**:
  1. `ASD`: High-performance lab-grade NIR spectrometer.
  2. `MicroNIR`: Compact field spectrometer.
  3. `NeoSpectra`: MEMS-based FT-NIR sensor.
  4. `NIRONE`: Multi-channel sensor module.
  5. `Scio`: Handheld consumer molecular sensor.
- **Substance Classes**: `K` (Ketamine & analogues), `NCD` (Non-controlled drugs/diluents), `P` (Paracetamol), `PAM` (Paracetamol + adulterant mixtures), `T` (Tramadol).
- **Compatibility Status**: **Isolated Modality**. Spectroscopic absorption signatures cannot be merged directly into RGB camera models. Maintained in separate feature branches.

### C. Reference Standard: NIJ Standard-0604.01
- **Source**: U.S. National Institute of Justice (*Color Test Reagents/Kits for Preliminary Identification of Drugs of Abuse*).
- **Content**:
  - Specifications for 12 standard reagents (A.1 Cobalt Thiocyanate through A.12 Simon's Reagent).
  - Standard Munsell color notations and ISCC-NIST centroid color codes.
  - Specificity and cross-reactivity matrix across 35+ drug and non-drug substances.
  - Drug detection limits ($\mu\text{g}$).
- **Role**: Authoritative ground-truth reference for colorimetry calibration and legal disclaimer requirements.

---

## 3. Data Compatibility Matrix Summary (`dataset_compatibility.csv`)

| Dataset | Modality | Reagents / Mechanism | Compatibility | Integration Strategy |
|---|---|---|---|---|
| **PMC7332374 idPAD** | RGB Images (12-lane strip) | Cobalt thiocyanate, Marquis, Liebermann, Simon, Fast Blue | Primary Visual | Trains computer vision & colorimetric baseline models |
| **dataset.zip (NIR)** | Spectral (800-2500nm) | Molecular vibrational reflectance (5 devices) | Incompatible with RGB | Kept in dedicated spectral interpretation module |
| **DTA1949 Library** | Tabular RGB values | 12 standard spot tests | Analytical Reference | Provides calibration boundaries & OOD rejection baseline |
| **NIJ Standard-0604.01** | Munsell / ISCC-NIST standards | Standard forensic reagents | Gold Standard Rule Engine | Enforces legal terminology and cross-reactivity warnings |

---

## 4. Group-Aware Split Distribution & Leakage Verification

To prevent optimistic bias and test contamination, splits are partitioned by physical `sample_id`:
- **Training Set (70%)**: 261 images (176 `PRESUMPTIVE_POSITIVE`, 85 `PRESUMPTIVE_NEGATIVE`)
- **Validation Set (15%)**: 56 images (37 `PRESUMPTIVE_POSITIVE`, 19 `PRESUMPTIVE_NEGATIVE`)
- **Test Set (15%)**: 57 images (39 `PRESUMPTIVE_POSITIVE`, 18 `PRESUMPTIVE_NEGATIVE`)

**Leakage Audit Result**:
- $\text{Train} \cap \text{Test} = \emptyset$ (0 overlapping physical samples)
- $\text{Train} \cap \text{Val} = \emptyset$ (0 overlapping physical samples)
- $\text{Val} \cap \text{Test} = \emptyset$ (0 overlapping physical samples)

---

## 5. Preprocessing & Quality Thresholds
- **Blur Assessment**: Laplacian variance $< 100.0$ flagged as blurry.
- **Brightness Assessment**: Mean grayscale intensity outside $[30.0, 240.0]$ rejected for underexposure or blooming glare.
- **Feature Extraction**: 21 normalized features engineered per sample (mean & std across RGB, HSV, CIELAB + image quality metrics).
