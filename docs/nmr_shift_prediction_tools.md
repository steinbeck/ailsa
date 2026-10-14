# Python-Based Open Source Tools for NMR Chemical Shift Prediction

A comprehensive overview of available open source tools for predicting NMR chemical shifts using Python, compiled January 2026.

---

## Table of Contents

1. [Graph Neural Network-Based Tools](#1-graph-neural-network-based-tools)
2. [NMRNet - State of the Art (2024/2025)](#2-nmrnet---state-of-the-art-20242025)
3. [ShiftML - Molecular Solids](#3-shiftml---molecular-solids)
4. [ISiCLE - DFT-Based with Python Wrapper](#4-isicle---dft-based-with-python-wrapper)
5. [ml4nmr - Grimme Lab](#5-ml4nmr---grimme-lab)
6. [nmrshiftdb2 Predictor Tools](#6-nmrshiftdb2-predictor-tools)
7. [PROSPRE - 1H Prediction Webserver](#7-prospre---1h-prediction-webserver)
8. [GeqShift - Carbohydrates](#8-geqshift---carbohydrates)
9. [General NMR Processing Tools](#9-general-nmr-processing-tools)
10. [Summary and Recommendations](#10-summary-and-recommendations)

---

## 1. Graph Neural Network-Based Tools

### nmrgnn (White Lab, University of Rochester)

| Property | Details |
|----------|---------|
| **GitHub** | https://github.com/ur-whitelab/nmrgnn |
| **License** | MIT |
| **Nuclei** | 1H, 13C, 15N (proteins and organic molecules) |
| **Installation** | `pip install nmrgnn` |

A library with pre-trained models to predict NMR chemical shifts from protein structures and organic molecules using graph neural networks. Works with MDAnalysis for coordinate reading.

**Key Features:**
- Command-line tool for structure evaluation
- Trajectory analysis support
- Confidence estimation for predictions
- Pre-trained models included

**Example Usage:**
```python
import MDAnalysis as md
import nmrgnn

model = nmrgnn.load_model()
u = md.Universe('molecule.pdb')
g = nmrgnn.universe2graph(u)
peaks = model(g)
confident = nmrgnn.check_peaks(g[0], peaks)
```

**Citation:**
> Yang, Z., Chakraborty, M., & White, A.D. (2021). Predicting chemical shifts with graph neural networks. *Chemical Science*, 12(32), 10802-10809.

---

### CASCADE (Paton Lab, Colorado State University)

| Property | Details |
|----------|---------|
| **GitHub** | https://github.com/patonlab/CASCADE |
| **Webserver** | https://nova.chem.colostate.edu/cascade/predict |
| **Nuclei** | 13C, 1H |
| **Framework** | TensorFlow 1.12 |

CASCADE (ChemicAl Shift CAlculation with DEep learning) is a stereochemically-aware online calculator for NMR chemical shifts using a graph network approach. 

**Key Features:**
- Accepts SMILES or graphical structure input
- Automated 3D structure embedding and MMFF conformer searching
- Considers stereochemistry and conformational ensembles
- Three trained models: DFTNN, ExpNN-dft, ExpNN-ff

**Performance:**
- ExpNN-ff model: MAE of 1.43 ppm for 13C compared to experimental shifts
- Trained on 8000 diverse structures from NMRShiftDB

**Citation:**
> Guan, Y., Sowndarya, S.V.S., Gallegos, L.C., St. John, P.C., & Paton, R.S. (2021). *Chem. Sci.*, DOI: 10.1039/D1SC03343C

---

### nmr_mpnn (PyTorch Implementation)

| Property | Details |
|----------|---------|
| **GitHub** | https://github.com/seokhokang/nmr_mpnn_pytorch |
| **Framework** | PyTorch |
| **Dependencies** | RDKit, NumPy, scikit-learn |

PyTorch implementation of neural message passing for NMR chemical shift prediction, trained on nmrshiftdb2 data.

**Also available:** TensorFlow version at https://github.com/seokhokang/nmr_mpnn

**Citation:**
> Kwon, Y., Lee, D., Choi, Y.-S., Kang, M., & Kang, S. (2020). Neural message passing for NMR chemical shift prediction. *J. Chem. Inf. Model.*, 60(4), 2024-2030.

---

### nmr_sgnn (Scalable GNN)

| Property | Details |
|----------|---------|
| **GitHub** | https://github.com/hjm9702/nmr_sgnn |
| **Nuclei** | 13C, 1H |

Source code for "Scalable graph neural network for NMR chemical shift prediction" with optimized message passing for larger molecules.

**Usage:**
```bash
python main.py --target 13C --message_passing_mode proposed --readout_mode proposed --graph_representation sparsified
```

---

## 2. NMRNet - State of the Art (2024/2025)

| Property | Details |
|----------|---------|
| **Publication** | Nature Computational Science (2025) |
| **Architecture** | SE(3) Transformer |
| **Benchmark Dataset** | nmrshiftdb2-2024 |

NMRNet represents the current state of the art in deep learning for NMR chemical shift prediction, using a pre-training and fine-tuning paradigm for atomic environment modeling.

**Key Features:**
- Unified framework for both liquid-state and solid-state NMR
- Comprehensive benchmark covering diverse chemical systems
- Strong correlation (R² > 0.80) for multiple nuclei
- Pre-training significantly improves performance, especially with limited data

**Supported Nuclei:** 1H, 13C, 19F, and others

**Performance on nmrshiftdb2-2024:**
- Achieves competitive performance across benchmark datasets
- Robust practical utility in real-world scenarios

**Citation:**
> Toward a unified benchmark and framework for deep learning-based prediction of nuclear magnetic resonance chemical shifts. *Nature Computational Science* (2025).

---

## 3. ShiftML - Molecular Solids

| Property | Details |
|----------|---------|
| **GitHub** | https://github.com/lab-cosmo/shiftml |
| **Web Tool** | https://tools.materialscloud.org/shiftml/ |
| **Installation** | `pip install shiftml` |
| **License** | Open Source |

A Python package for the prediction of chemical shieldings of organic solids and beyond, using machine learning with DFT accuracy.

**Supported Elements:** H, C, N, O, S, F, P, Cl, Na, Ca, Mg, K

**Key Features:**
- ShiftML3 model trained on 1.4 million chemical shieldings from 14,000 organic crystals
- Includes anisotropy predictions
- Error estimates for predictions
- Integration with ASE (Atomistic Simulation Environment)

**Performance:**
- 1H isotropic shielding RMSE: 0.43 ppm
- 13C isotropic shielding RMSE: 4.3 ppm
- >24,000x speedup compared to DFT calculations

**Example Usage:**
```python
from ase.build import bulk
from shiftml.ase import ShiftML

frame = bulk("C", "diamond", a=3.566)
calculator = ShiftML("ShiftML3")
cs_iso = calculator.get_cs_iso(frame)
```

**Citations:**
> Paruzzo, F.M., et al. (2018). Chemical shifts in molecular solids by machine learning. *Nature Communications*, 9(1), 4501.
>
> Cordova, M., et al. (2022). A machine learning model of chemical shifts for chemically and structurally diverse molecular solids. *J. Phys. Chem. C*, 126, 16710-16720.

---

## 4. ISiCLE - DFT-Based with Python Wrapper

| Property | Details |
|----------|---------|
| **GitHub** | https://github.com/pnnl/isicle |
| **Institution** | Pacific Northwest National Laboratory |
| **Backend** | NWChem (DFT) |
| **License** | GNU GPL |

ISiCLE (in silico Chemical Library Engine) NMR chemical shift module employs DFT methods through NWChem for predicting NMR chemical shifts of small organic molecules.

**Key Features:**
- Automated workflow for DFT calculations
- Multiple DFT methods supported (B3LYP, B35LYP, etc.)
- Solvent effects via COSMO implicit solvent model
- Conformer generation with Boltzmann weighting

**Tested Performance (312 molecules):**
- 13C MAE: 5-10 ppm depending on method/basis set
- 1H MAE: ~0.30-0.35 ppm

**Note:** Computationally expensive compared to ML methods but provides ab initio quality predictions.

**Citation:**
> Yesiltepe, Y., et al. (2018). An automated framework for NMR chemical shift calculations of small organic molecules. *J. Cheminform.*, 10, 52.

---

## 5. ml4nmr - Grimme Lab

| Property | Details |
|----------|---------|
| **GitHub** | https://github.com/grimme-lab/ml4nmr |
| **Framework** | TensorFlow |
| **Nuclei** | 1H, 13C |

Machine learning-based correction for DFT-computed NMR chemical shifts, providing two main functionalities:

1. **ΔcorrML:** Correct DFT chemical shifts toward CCSD(T) quality
2. **ΔSOML:** Predict spin-orbit relativistic contributions to chemical shifts

**Requirements:**
- Python 3.7/3.11 (depending on method)
- TensorFlow 2.7/2.12
- ORCA calculation outputs

**Usage:**
```bash
# Predict corrected shifts
mlcorrect_corr --predict ml_mol_c.dat tf_model_c --nucleus c

# Predict spin-orbit contributions
mlcorrect_so --predict ml_mol_h.dat tf_model_h --nucleus h
```

**Citations:**
> ΔcorrML: https://doi.org/10.1021/acs.jctc.3c00165
>
> ΔSOML: https://doi.org/10.1039/d3cp05556f

---

## 6. nmrshiftdb2 Predictor Tools

### Python API Wrapper

| Property | Details |
|----------|---------|
| **GitHub** | https://github.com/jvansan/nmrshiftdb_predictors_app |
| **Dependencies** | FastAPI, RDKit, JDK |
| **Database** | nmrshiftdb2 |

A web API wrapper for nmrshiftdb2 predictors that parses InChI and SMILES strings and returns predictions.

**Supported Solvents:**
- Chloroform-D1 (CDCl3)
- Methanol-D4 (CD3OD)
- Dimethylsulphoxide-D6 (DMSO-D6)

**Example Usage:**
```python
import requests
from urllib.parse import quote

smiles = ["C", "CC", "CCC", "c1ccccc1"]
solvent = "Chloroform-D1 (CDCl3)"

r = requests.post(
    f"http://localhost:8000/api/predict/carbon?solvent={quote(solvent)}",
    json={"smiles": smiles}
)
carbon_preds = r.json()
```

### Standalone JAR Predictors

Available from https://sourceforge.net/p/nmrshiftdb2/code/HEAD/tree/trunk/nmrshiftdb2/lib/

- `predictorc.jar` - Carbon shift prediction
- `predictorh.jar` - Proton shift prediction

Uses HOSE (Hierarchically Ordered Spherical Environment) codes with the Chemistry Development Kit (CDK).

**Note:** HOSE codes require proper molecule configuration (aromaticity detected, explicit hydrogens).

### HOSE Code + Machine Learning Models

Recent work shows that graph neural networks trained on nmrshiftdb2 data outperform HOSE codes when trained on >1000 spectra, but HOSE codes remain competitive for limited data scenarios (<1000 examples).

**Citation:**
> Kuhn, S., et al. (2023). NMR shift prediction from small data quantities. *J. Cheminform.*, 15, 785.

---

## 7. PROSPRE - 1H Prediction Webserver

| Property | Details |
|----------|---------|
| **URL** | https://prospre.ca |
| **Also at** | https://np-mrd.org (under Utilities → 1H NMR Predictor) |
| **Backend** | Python with GNN |

A comprehensive webserver for 1H NMR chemical shift prediction in multiple solvents.

**Workflow:**
1. Input SMILES or SDF file
2. ChemAxon's JChem interface processes input
3. RDKit generates 3D coordinates
4. GNN algorithm predicts chemical shifts

**Features:**
- Multiple solvent support
- High accuracy for small molecules
- Integration with NP-MRD database

**Citation:**
> Accurate Prediction of 1H NMR Chemical Shifts of Small Molecules Using Machine Learning. *Metabolites* (2024), 14(5), 290.

---

## 8. GeqShift - Carbohydrates

| Property | Details |
|----------|---------|
| **Architecture** | E(3) equivariant GNN |
| **Dependencies** | PyTorch, PyTorch Geometric, e3nn, RDKit |
| **Domain** | Carbohydrates (mono- to trisaccharides) |

A specialized tool for carbohydrate NMR prediction using E(3) equivariant graph neural networks.

**Dataset:**
- 375 carbohydrates in aqueous solution
- 5356 1H and 4713 13C chemical shifts
- Based on CASPER database

**Key Innovation:**
- Data augmentation with conformational ensembles (100 conformations per molecule)
- MAE reduction from 0.55 to 0.34 ppm for 13C (monosaccharides) with ensemble approach

**Citation:**
> Carbohydrate NMR chemical shift prediction by GeqShift employing E(3) equivariant graph neural networks. *Digital Discovery* (2024).

---

## 9. General NMR Processing Tools

### nmrglue

| Property | Details |
|----------|---------|
| **Website** | https://www.nmrglue.com/ |
| **GitHub** | https://github.com/jjhelmus/nmrglue |
| **License** | New BSD |

An open source Python package for working with multidimensional NMR data.

**Supported Formats:**
- Bruker
- Agilent/Varian
- NMRPipe
- Sparky
- SIMPSON
- Rowland NMR Toolkit

**Features:**
- Linear prediction
- Peak picking
- Lineshape fitting
- Baseline correction
- Integration with NumPy, SciPy, matplotlib

**Note:** Not for chemical shift prediction, but essential for NMR data processing and analysis.

**Citation:**
> Helmus, J.J., & Jaroniec, C.P. (2013). Nmrglue: an open source Python package for the analysis of multidimensional NMR data. *J. Biomol. NMR*, 55(4), 355-367.

---

### ssNake

| Property | Details |
|----------|---------|
| **Focus** | Solid-state NMR |
| **Features** | Processing, simulation, fitting |

An NMR processing program for solid-state NMR with interactive and script-based processing tools, with extensive fitting capabilities for spectrum deconvolution.

**Key Feature:** Simultaneous fitting of multiple spectra with shared parameters.

---

### MRSimulator

| Property | Details |
|----------|---------|
| **GitHub** | https://github.com/deepanshs/mrsimulator |
| **Documentation** | https://mrsimulator.readthedocs.io/ |

Open-source Python package for rapid solid-state NMR spectral simulation and analysis.

**Citation:**
> Srivastava, D.J., et al. (2024). MRSimulator: A cross-platform, object-oriented software package for rapid solid-state NMR spectral simulation and analysis. *J. Chem. Phys.*, 161(21), 212501.

---

## 10. Summary and Recommendations

### Quick Selection Guide

| Use Case | Recommended Tool |
|----------|------------------|
| Small organic molecules (solution) | CASCADE, nmrgnn, nmr_mpnn |
| Proteins | nmrgnn |
| Molecular solids/crystals | ShiftML |
| Carbohydrates | GeqShift |
| DFT-quality predictions | ISiCLE, ml4nmr |
| Quick HOSE-based lookup | nmrshiftdb2 predictors |
| Limited training data | HOSE codes or 2023 GNN model |
| State-of-the-art benchmarking | NMRNet |

### For Natural Products / CASE Applications

1. **CASCADE** or **nmrgnn** - Good for small organic molecules with 3D structure consideration
2. **nmr_mpnn_pytorch** - Well-documented PyTorch implementation, easy to customize
3. **nmrshiftdb2 HOSE predictors** - Traditional approach, accessible via Python/CDK wrappers

### Key Considerations

- Most modern tools use **RDKit** for molecular representation and conformer generation
- **3D structure** consideration significantly improves prediction accuracy for stereoisomers
- **Solvent effects** are often neglected; solvent-specific models perform better
- For **heteronuclei** (19F, 15N, 31P), data is more limited; HOSE codes may outperform ML with <1000 examples
- **Ensemble/conformational averaging** improves predictions for flexible molecules

### Performance Comparison (Typical MAE)

| Method | 13C (ppm) | 1H (ppm) | Speed |
|--------|-----------|----------|-------|
| HOSE codes | 1.4-2.2 | 0.2-0.4 | Fast |
| Graph Neural Networks | 1.3-2.0 | 0.2-0.4 | Fast |
| DFT (B3LYP/6-31G*) | 5-10 | 0.3-0.4 | Slow |
| ML-corrected DFT | 1-2 | 0.2-0.3 | Medium |
| ShiftML (solids) | 4.3 | 0.4-0.5 | Very Fast |

---

## Additional Resources

### Databases

- **nmrshiftdb2**: https://nmrshiftdb.nmr.uni-koeln.de/ - Open database with >57,000 measured 1D spectra
- **BMRB**: https://bmrb.io/ - Biological Magnetic Resonance Bank (proteins)
- **NP-MRD**: https://np-mrd.org/ - Natural Products Magnetic Resonance Database

### Historical Benchmark Reference

A comprehensive list of NMR prediction methods and their historical performance is maintained at:
https://nmrshiftdb2.sourceforge.io/predictionhistory/history.html

### Python HOSE Code Generator

For generating HOSE codes in Python:
https://github.com/Ratsemaat/HOSE_code_generator

---

*Document compiled: January 2026*
*For the latest developments, check the respective GitHub repositories and recent publications.*
