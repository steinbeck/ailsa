# NMR Basics Reference

Shared reference for all CASE team agents. Read by agents that need NMR experiment and shift region context.

---

## NMR Experiment Types

| Experiment | Information Provided | Key Insight |
|------------|---------------------|-------------|
| **1H** | Proton chemical shifts | Hydrogen environment |
| **13C** | Carbon chemical shifts | All carbons including quaternary |
| **DEPT-135** | Protonated carbons only | CH/CH3 positive, **CH2 negative** (sign is critical!) |
| **DEPT-90** | CH only | Distinguishes CH from CH3 |
| **HSQC** | Direct C-H connections | Which H is attached to which C |
| **HMBC** | 2-3 bond C-H correlations | Connectivity through bonds |
| **COSY** | H-H correlations | Adjacent protons |

---

## 13C Chemical Shift Regions

| Region (ppm) | Typical Assignment |
|--------------|-------------------|
| 0-50 | Aliphatic carbons (CH3, CH2, CH) |
| 50-90 | Carbons attached to oxygen (C-O) |
| 90-120 | Anomeric carbons, alkenes |
| 120-160 | Aromatic carbons, alkenes |
| 160-175 | Esters (C=O), amides |
| 170-185 | Carboxylic acids (COOH) |
| 190-220 | Aldehydes, ketones |

---

## DEPT-135 Sign Convention

DEPT-135: positive peaks = CH and CH3, negative peaks = CH2. Sign is critical for multiplicity assignment. Never invert or ignore negative peaks — they are CH2 carbons, not noise.
