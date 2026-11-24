# NMR analysis: from spectra to the atom list

## When to read this

Read this before you build the atom list. It turns the output of `ailsa pick`, `ailsa analyze`
and `ailsa detect` into carbons with H counts, hybridisation, equivalences and assigned HSQC/HMBC
correlations. The pick commands return raw peaks with solvent lines, artefacts and noise still in
them; removing those is your job. "Record" means: write it into `setup.md`.

## 1. Experiments and shift regions

| Experiment | Tells you |
|---|---|
| 13C | every carbon, including quaternary carbons (C) |
| DEPT-135 | protonated carbons only: CH and CH3 positive, **CH2 negative** |
| DEPT-90 | CH only |
| APT (pulse program `jmod`) | C and CH2 one sign, CH and CH3 the other |
| HSQC | which proton sits on which carbon |
| HMBC | proton to carbon over 2-3 bonds (sometimes 4) |
| COSY | protons on neighbouring carbons |

| 13C (ppm) | Typical carbon |
|---|---|
| 0-50 | carbon bonded only to C and H |
| 40-65 | C-N; OCH3 at 50-62 |
| 50-90 | C-O |
| 90-120 | acetal or anomeric carbon (sp3), alkene |
| 120-160 | aromatic or alkene; 145-165 can be a ring C-O or C-N |
| 160-175 | ester, lactone or amide C=O |
| 170-185 | carboxylic acid |
| 190-220 | aldehyde or ketone |

## 2. Pick the peaks

```
ailsa pick 1d C13_PATH --format json
ailsa pick 1d DEPT_OR_APT_PATH --format json
ailsa pick hsqc HSQC_PATH --format json
ailsa pick hmbc HMBC_PATH --format json
ailsa analyze symmetry FORMULA C13_PATH --format json
```

- `pick 1d` and `pick hmbc` keep peaks with SNR >= 5 (field `snr`). Below 5 is noise in every
  spectrum, whatever its quality. `--snr-floor 3` is for an exploratory look only.
- `pick 1d` gives negative lines (DEPT-135 CH2, APT) a negative `intensity`.
- `pick hsqc` cuts at a fraction of the strongest peak (`-t`, default 0.05) and reports
  `multiplicity_edited`. In an edited HSQC (`multiplicity_edited: true`) it also lists the
  negative cross-peaks, with negative `intensity`: these are the CH2 groups, minus artefacts
  (section 4).
- `analyze symmetry` counts every picked line, solvent and satellites included, so its
  `overcount_alarm` is often false. Compare the formula with your cleaned list (section 3).

Quality, from the typical SNR of the real 13C lines:

| SNR | Quality | What to do |
|---|---|---|
| > 30 | good | defaults |
| 10-30 | moderate | HSQC at `-t 0.10`; trust the strongest half of the HMBC correlations |
| < 10 | poor | expect missing lines; trust the strongest quarter of the HMBC correlations |

HMBC carbon spacing d: the smallest step between distinct `f1_position` values in the HMBC pick
(peaks sit on the data grid). Carbon tolerance: d up to 0.2 ppm: +/-1.5 ppm; 0.2-0.5 ppm:
+/-2.0 ppm; above 0.5 ppm: +/-3.0 ppm.

## 3. Clean the 13C list

Remove, in this order:

1. **Solvent.** `acqus` names it (`##$SOLVENT=`); confirm it in the data: a group of evenly spaced
   lines (0.15-0.45 ppm apart) within 2.5 ppm of the shift below (referencing is not always exact).
   Remove the whole multiplet. An HSQC cross-peak at the residual C-H is solvent too. A line at
   0 +/- 1 ppm is the reference.

| Solvent | 13C multiplet (ppm) | Residual C-H in HSQC (13C / 1H) |
|---|---|---|
| CDCl3 | 77.16, 3 lines | 77.16 / 7.26 |
| DMSO-d6 | 39.52, 7 lines | 39.52 / 2.50 |
| CD3OD | 49.00, 7 lines | 49.00 / 3.31 |
| acetone-d6 | 29.84, 7 lines; also 206.3 | 29.84 / 2.05 |
| C6D6 | 128.06, 3 lines | 128.06 / 7.16 |
| CD2Cl2 | 53.84, 5 lines | 53.84 / 5.32 |
| CD3CN | 1.32, 7 lines; also 118.3 | 1.32 / 1.94 |
| pyridine-d5 | 123.5, 135.5, 149.9 | same carbons / 7.22, 7.58, 8.74 |

2. **Satellites.** A line within 0.05 ppm of a line at least 5 times stronger, or within 0.35 ppm
   of one at least 15 times stronger, is an artefact. A quaternary carbon beside a protonated one
   is typically only 3-10 times weaker; keep it.
3. **Weak lines.** A line below 4 % of the median SNR of the stronger half of the lines is noise
   or an impurity.

Never remove a line at 160-220 ppm with SNR >= 5 (unless solvent or satellite): carbonyls are
weak but real, and losing one miscounts the DBE and excludes the right structure. Never remove a
line only to make the count fit the formula.

- **More lines than carbons:** the excess is noise, never symmetry. Re-pick with
  `--snr-floor 8`, then 10, and see which weak lines vanish.
- **Fewer lines than carbons:** usually equivalent carbons (section 7). Also look for an HSQC
  cross-peak with no 13C line (a carbon under the solvent or too weak) and add it.

## 4. H count per carbon

Match DEPT and APT lines to 13C lines within 0.3 ppm.

| Evidence | H count |
|---|---|
| negative in DEPT-135 | CH2 (never override) |
| positive in DEPT-135, present in DEPT-90 | CH |
| positive in DEPT-135, absent in DEPT-90 | CH3 |
| in 13C, absent in DEPT-135 and HSQC | C |
| APT | sign separates {C, CH2} from {CH, CH3}; an HSQC cross-peak separates C from CH2 |

- Quaternary carbons = 13C lines minus DEPT-135 lines. HMBC is their only connection.
- Sign check: a protonated carbon above 100 ppm with its proton above 4.5 ppm is almost always CH
  and must be positive in DEPT-135. If all such lines are negative, flip every sign.
- A DEPT line below 8 % of the median SNR of the stronger half of the DEPT lines is leakage (a
  quaternary carbon in DEPT-135, a CH3 or CH2 in DEPT-90).
- No DEPT-90: CH3 is mostly below 30 ppm (OCH3 50-62 ppm, H 3.3-4.0) and gives the strongest
  HSQC cross-peaks; CH lies at 100-160 ppm.
- Conflicts: resolve to ONE H count by DEPT-135 sign, then DEPT-90, intensity, shift. Record it.

**Edited HSQC.** Negative cross-peaks are CH2, positive ones CH or CH3. A weak negative peak
about 1-2 ppm (13C) beside a much stronger positive peak at the same 1H shift is a phase
artefact, not a CH2: a real CH2 cross-peak is of similar size to the CH cross-peaks and matches a
negative DEPT-135 or APT line where one exists. A carbon line with no cross-peak of either sign
is quaternary.

**Ambiguous aliphatic H counts.** Declare them ambiguous when there is no usable DEPT-135 or APT
(missing, or phase unreliable: signs vary across the spectrum or contradict the shift regions)
and the HSQC does not settle them (`multiplicity_edited: false`, or the hydrogen budget leaves C
versus CH2 open). A clean DEPT-135 settles the counts; then do not enumerate.

When ambiguous, list the viable families: whole-molecule splits of the ambiguous carbons into
CH3, CH2 and CH that fit the formula H count and the DBE, not carbon-by-carbon combinations.
Example: four aliphatic carbons with 10 H give 3 CH3 + 1 CH (isopropyl type) and 2 CH3 + 2 CH2
(two methyls plus an ethyl); list both. Keep at most 3, ranked by plausibility, and record any
you drop. The LSD step runs one solver run per family.

## 5. HSQC

- Assign each cross-peak (`f1_position` = carbon, `f2_position` = proton) to the carbon line
  within 1.0 ppm. If all HSQC carbons are offset from the 13C lines by the same amount, subtract
  it first.
- A protonated carbon without a cross-peak: re-pick with `-t 0.02`, then 0.01 and 0.005. Keep
  only cross-peaks that match a carbon line.
- Artefacts: the solvent residual; a carbon above 100 ppm with a proton below 4 ppm, or below
  50 ppm with a proton above 6 ppm; a cross-peak weaker than 1/8 of the strongest one of the same
  carbon.
- Two strong cross-peaks of one carbon at different proton shifts are the two protons of a CH2.

## 6. HMBC

`pick hmbc` returns hundreds of peaks; most are noise streaks along intense proton columns. Use a
peak only if it passes all four tests:

1. **Proton** within 0.05 ppm of an assigned HSQC proton. If protons of two different carbons lie
   within 0.05 ppm, do not use the peak.
2. **Carbon** within the HMBC carbon tolerance (section 2) of a carbon line. If 2-4 lines qualify,
   record all as candidates; more than 4, do not use it.
3. **Not one-bond leakage:** drop a peak at an HSQC position (carbon within 1.5 ppm, proton
   within 0.3 ppm), that is, on the proton's own carbon.
4. **Above its column noise:** peaks at the same proton shift that hit no carbon line show the
   noise of that column. Keep a peak only if its SNR is at least twice the level of nearly all of
   them.

Then:
- Judge a weak peak against its own column, never by its fraction of the strongest peak in the
  spectrum. Aromatic 3-bond correlations (ring proton to a ring carbon across the ring) are often
  far weaker than 2-bond ones, yet they fix the ring connectivity.
- A peak below 5 % of the strongest peak of the same proton: record it as doubtful.
- Possible 4-bond correlation: carbon at 110-160 ppm (sp2), proton on an aliphatic carbon
  (0-55 ppm). Keep it, flagged; never drop it silently.
- A quaternary carbon's only HMBC correlation: keep it. With none, use its shift (section 1).
- An HMBC proton that matches no HSQC proton may be OH or NH (with an edited HSQC, also CH2).

## 7. Symmetry and close signals

- Typical equivalences: a benzene ring with two substituents opposite each other (two CH lines of
  2 C each), isopropyl or gem-dimethyl (one CH3 line, 2 C), tert-butyl (one CH3 line, 3 C).
- **Intensity check, mandatory when aromatic CH are present** (HSQC carbons at 110-165 ppm): a
  line at 1.6 times the median 13C intensity of the aromatic CH lines or more is a candidate for
  2 equivalent carbons. Record the candidates, or "none".
- For confirmed 2C aromatic CH, pass all 13C shifts in atom order, with each such shift written
  twice, and their H counts in the same order, for example:
  `ailsa detect aromatic-cosy "166.9,129.4,129.4,127.3,127.3,21.6" --multiplicities "C,CH,CH,CH,CH,CH3" --format json`
  `cosy_pairs` are then 1-based atom numbers. Record them as cross-ring COSY pairs.
- Close signals, once on all 13C shifts with H counts in the same order:
  `ailsa analyze grouping "SHIFTS" --multiplicities "C,CH,CH2,..." --format json`
  JSON `indices` are 0-based. Record each group; the LSD step writes grouped atoms as `(N M)`.
- Two carbons closer than 1.5 d (the HMBC carbon spacing, section 2) are not resolved in the
  HMBC: a peak near them is a candidate for both.

## 8. Hybridisation and heteroatoms

Run once per compound, before the first solver run. The results are database frequencies, not
chemical laws.

| Command | Run for |
|---|---|
| `ailsa detect hybridisation SHIFT --format json` | every shift at 120-220 ppm |
| `ailsa detect neighbours SHIFT --format json` | every shift at 50-90 and 160-220 ppm |
| `ailsa detect hhb FORMULA --format json` | formulas with 2 or more heteroatoms |

**Hybridisation** (`distribution`): above 0.8 decides. Otherwise decide with DEPT/HSQC and shift;
if still unclear, record "ambiguous" and fix nothing. With `has_data: false`: 120-220 ppm sp2,
below 50 ppm sp3.

**Neighbours:**
1. Ignore any element the formula lacks, even if "mandatory".
2. Read `dominant_element` and the whole `distribution`. Never rescale the values (for example
   after excluding an element).
3. `constraint_type`: mandatory (0.95 or more), typical (about 0.5-0.9), forbidden (below 0.01).
4. Neighbours alone never justify a fixed heteroatom bond or count. "typical" gives a note only;
   carbon dominant: record "likely C-substituted"; "forbidden": an advisory exclusion only.
5. Aromatic carbon at 145-160 ppm: oxygen scores high for a ring C-O and for a ring carbon
   carrying a carbon substituent (such as a CH-OH at 65-75 ppm). If carbon is dominant, fix
   nothing.
6. **Carbonyl exception:** a carbon at 160-220 ppm with no H (DEPT/HSQC), O in the formula, and an
   unambiguous ester, acid, amide or ketone context from formula and HMBC may be fixed as C=O.
   Record every source.
7. Any other heteroatom placement needs direct evidence (an HMBC correlation establishing the
   attachment, or an OH/NH proton in the HMBC). Otherwise leave it open; the 13C ranking decides
   between acid, ester, ether and carbon substituent.

**Hetero-hetero bonds:** a pair in `forbidden_pairs` (below 1 %): record "no X-Y bond".

## 9. DBE and hydrogen budget

DBE = (2C + 2 + N - H - halogens) / 2. Account for it: benzene ring 4, any other ring 1, each C=C
or C=O 1, each C≡C or C≡N 2. A deficit is a flag, not a gate:

- O in the formula, nothing at 160-220 ppm: look again for a carbonyl (SNR >= 5; real ones are
  usually >= 8).
- N in the formula: check 150-180 ppm (amide) and 100-120 ppm (nitrile).
- Neither: an extra ring or C=C.

**Hydrogen budget:** H on all carbons (counting copies) against the formula. A shortfall with O
or N in the formula is first an OH or NH, invisible in the HSQC. Change a carbon's H count only as
a last resort, with DEPT evidence. A difference of 2 often means a CH and a CH3 are swapped.

**Aromatic expectation:** fewer than 4 carbons at 110-160 ppm: no aromatic ring expected. 4 or
more: sp2 carbons present; a CH2 there (=CH2) points to an alkene, not an aromatic ring.

## 10. Evidence hierarchy

| Rank | Evidence | Trust | Override |
|---|---|---|---|
| 1 | DEPT-135 sign | 100 % | never: negative = CH2 |
| 2 | HSQC | 95 % | only for a weak cross-peak |
| 3 | HMBC | 80 % | may be dropped after diagnosis |
| 4 | shift regions | 70 % | guideline |
| 5 | statistical detection | 60 % | whenever the NMR disagrees |

Detection against DEPT or the formula: trust DEPT or the formula. Against HSQC: trust a clear
cross-peak; use detection only as tiebreaker for a weak one. No data: use shift regions.
Ambiguous (0.4-0.6): no constraint. Record every override, for example "65.3 ppm: detection says
O mandatory, formula has no O, ignored".

## 11. What to record for the LSD step

| Per carbon | Example |
|---|---|
| atom number, shift | 7, 128.4 |
| H count and source | CH (DEPT-135 positive, DEPT-90 present) |
| hybridisation and source | sp2 (detection 0.98) |
| copies | 2 (intensity 1.9 times the median) |
| proton shift(s), needed to assign HMBC | 7.21 |
| confidence | Low: overlapping line, quaternary without HMBC, or unresolved DEPT/HSQC conflict. High: isolated, HSQC and 3+ HMBC. Else Medium |

Also record:
- heteroatoms with their H from the hydrogen budget; C=O only under the carbonyl exception
- HSQC pairs; HMBC list, most reliable first: the proton's carbon, candidate carbon(s), SNR,
  flags (possible 4-bond, doubtful)
- grouping results, aromatic COSY pairs, forbidden hetero-hetero bonds
- DBE balance, hydrogen budget, aromatic expectation, every conflict and override
- the H-count families, if ambiguous
- sp2 atoms come in pairs (each double bond joins two; a C=O makes its O sp2). An odd count means
  a wrong hybridisation.
