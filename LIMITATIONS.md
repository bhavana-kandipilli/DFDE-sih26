# LIMITATIONS.md - System & Operational Limitations

## 1. Scientific & Forensic Limitations

> [!WARNING]
> **PRESUMPTIVE FIELD TESTING BOUNDARY**:
> Field colorimetric chemical tests and portable spectrophotometry provide **presumptive** indication only. They operate on functional group reactions and broad spectral band absorption, which can be shared by structural isomers, cross-reacting OTC compounds, or benign cutting agents.

1. **Mandatory Lab Confirmation**: No result produced by this system, regardless of confidence score, constitutes conclusive chemical identification. Laboratory GC-MS or LC-MS confirmatory analysis is legally required.
2. **Reagent Degradation**: Chemical field test kits (e.g. Marquis, Scott reagent) degrade over time, when exposed to heat, or when exposed to UV light. Expired or degraded reagents produce invalid color reactions.
3. **Complex Mixtures & Cutting Agents**: High concentrations of adulterants (e.g. caffeine, phenacetin, diltiazem) may obscure or alter primary color reactions.

---

## 2. Technical & Environmental Limitations

1. **Environmental Lighting**: Ambient lighting with heavy color cast (e.g., sodium vapor streetlights) may degrade color card calibration if illumination intensity is below 50 lux.
2. **Camera Sensor Variations**: Variations in smartphone image sensor ISP (Image Signal Processor) tone mapping may introduce subtle RGB distortions.
3. **Camera Motion Blur**: Low light conditions causing shutter speeds below $1/30\text{ s}$ will induce motion blur, triggering quality rejection.

---

## 3. Operational & Legal Usage Boundaries

1. **Evidentiary Standard**: System outputs must be presented in court as "presumptive field test interpretations" accompanied by the generated Digital Evidence Certificate.
2. **Chain of Custody**: If an image payload hash fails SHA-256 verification or HMAC signature validation, the evidence item must be marked as `TAMPERED_DISQUALIFIED` and excluded from legal proceedings.
