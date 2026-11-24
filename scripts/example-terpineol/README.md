# Public example dataset: alpha-terpineol (BMRB bmse000667)

AILSA's run-record acceptance run and the spectra view-product tests use a small public dataset:
alpha-terpineol, entry **bmse000667** of the BMRB metabolomics database. The entry holds raw
FIDs only (1H, 13C, DEPT-90, DEPT-135, 1H-13C HSQC, 1H-13C HMBC, HH-COSY, HH-TOCSY). AILSA
needs Bruker processed data (`pdata`), so the scripts here rebuild them.

**The data themselves are not in this repository.** BMRB names no licence and asks only to be
acknowledged, so the raw and processed data stay out of the public repo; the scripts and this
credit come instead.

## Acknowledgement and citation

The raw NMR data were obtained from the Biological Magnetic Resonance Data Bank (BMRB,
https://bmrb.io), metabolomics entry bmse000667. We acknowledge BMRB as the source of the data.
If you use the data, please cite BMRB:

> Hoch JC, Baskaran K, Burr H, Chin J, Eghbalnia HR, Fujiwara T, Gryk MR, Iwata T, Kojima C,
> Kurisu G, Maziuk D, Miyanoiri Y, Wedell JR, Wilburn C, Yao H, Yokochi M.
> Biological Magnetic Resonance Data Bank. *Nucleic Acids Res.* 2023, 51(D1), D368-D376.
> doi:10.1093/nar/gkac1050

Please check https://bmrb.io for the wording BMRB currently asks for.

## Rebuild in two steps

Both scripts refuse a destination inside the git repository. Use any folder outside it.

1. Download the raw experiments (stdlib only; BMRB serves a plain directory tree, no archive):

   ```bash
   python scripts/example-terpineol/download_bmrb.py --dest /path/to/example-download
   ```

   The raw data land in `/path/to/example-download/raw/<experiment>/`. The script prints one
   sha256 over all fetched files so two downloads can be compared.

2. Process the FIDs into Bruker `pdata` (needs `nmrglue` and `numpy`, both AILSA dependencies):

   ```bash
   python scripts/example-terpineol/process_fid.py \
       --raw /path/to/example-download/raw \
       --out /path/to/example-dataset \
       --template-1d /path/to/example-download/raw/1H/pdata/1 \
       --template-2d /path/to/example-download/raw/1H_13C_HSQC/pdata/1 \
       --plots /path/to/example-plots
   ```

   The templates are BMRB's own `pdata/1` folders; they are used only for the numeric layout of
   the processing-parameter files. Every text field is blanked, nothing from them is carried over.

The output dataset has seven experiments: 1 = 1H, 2 = 13C, 3 = DEPT-90, 4 = DEPT-135,
5 = 1H-13C HSQC, 6 = 1H-13C HMBC, 7 = HH-COSY, plus `Molecular-Formula.txt`.

## Processing decisions

- 1D phase: ACME autophase; DEPT-135 takes DEPT-90's phase (same sequence and receiver path).
- Referencing, as the code does it: 1H on the TMS line present in the sample (0.00 ppm); 13C has
  no visible TMS line and is referenced on the acetone-d6 solvent lines (CD3 29.84 ppm, C=O
  206.26 ppm). The heteronuclear F1 axes use the 13C correction. (The docstring in
  `process_fid.py` still says "TMS in 1H and 13C"; the code is authoritative.)
- HMBC and COSY: magnitude mode, as acquired. F1 orientation of the heteronuclear spectra is the
  one whose F1 projection matches the 13C spectrum; for COSY the one that makes the matrix
  symmetric about the diagonal.
- HSQC: written in **magnitude mode**. The edited (phase-sensitive) result could not be phased
  reliably with 128 increments over a wide carbon range, so the edited signs are not retained;
  multiplicities (CH, CH2, CH3) come from DEPT.

## Tests that use the processed data

Tests that need the processed dataset read the environment variable `AILSA_EXAMPLE_TERPINEOL`
(path of the processed dataset folder, the `--out` folder above) and skip when it is unset or the
folder is missing:

```bash
export AILSA_EXAMPLE_TERPINEOL=/path/to/example-dataset
```
