---
description: "Remove compound identifiers from NMR datasets for blind CASE evaluation. Use when: prepare blind test, remove names, anonymise dataset, sanitise for CASE, blind testing"
argument-hint: "<dataset_path>"
allowed-tools:
  - Read
  - Write
  - Glob
  - Bash
---

<objective>
AI-driven sanitisation of Bruker NMR datasets for blind CASE evaluation. Removes all compound identifiers (names, database IDs, structure files, audit logs) from metadata and text files while preserving spectroscopic data integrity.

There is no CLI command for sanitisation. This is a pure AI task requiring semantic reasoning to identify compound identifiers that reveal chemical identity. Unlike other ailsa commands that call thin CLI wrappers, sanitisation depends entirely on Claude's ability to distinguish revealing information (compound names, CAS numbers, InChI strings) from generic metadata (experiment types, solvents, instrument parameters).
</objective>

## Contents

The steps in run order, then the background notes.

- validate_input: parse the argument, confirm a Bruker dataset
- discover_text_files: classify every file (skip, delete, read)
- dry_run_scan: find the identifiers without changing anything
- present_dry_run_report: show the findings, wait for "proceed"
- delete_structure_and_audit_files: remove structure files and audit logs
- scan_and_redact: redact identifiers in place (with the identifier categories and the false positives)
- present_report: the sanitisation report
- verify_completeness: full re-scan plus the mechanical grep backstop
- handoff_instructions: blind CASE in a fresh session
- Implementation Notes

## Process

<process>

<step name="validate_input">
**Parse user argument and verify dataset structure.**

User provides dataset path:
```
/ailsa:sanitise <dataset_path>
```

**If no argument given**, show usage:
```
Usage: /ailsa:sanitise <dataset_path>

Example:
  /ailsa:sanitise data/compound/<compound name>
  /ailsa:sanitise data/nmrXiv/Classics_<compound name>
```

**Verify path exists:**
```bash
ls <dataset_path> 2>/dev/null
```

**Verify Bruker NMR structure:**
Look for numbered experiment directories (1, 2, 3, ...) containing acqus files. This confirms it's a Bruker dataset.

```bash
ls <dataset_path>/*/acqus 2>/dev/null
```

If no acqus files found, warn: "Path does not appear to be a Bruker NMR dataset (no experiment directories with acqus files found)."
</step>

<step name="discover_text_files">
**Find all files in the dataset and classify for processing.**

Use Glob tool to discover all files:
```
Glob:
  pattern: "**/*"
  path: "<dataset_path>"
```

**Classify each file into categories:**

**SKIP (binary NMR data). Do not read or modify these:**
- fid, ser (raw FID data)
- 1r, 1i (processed 1D real/imaginary)
- 2rr, 2ri, 2ir, 2ii (processed 2D data)
- 3rrr, 3rri, 3rir, 3rii, 3irr, 3iri, 3iir, 3iii (3D data - 8 variants)

**SKIP (binary extensions). Do not read or modify these:**
- .pdf, .png, .jpg, .jpeg, .gif, .tiff, .bmp

**DELETE (structure files). They contain the compound structure; delete them entirely:**
- *.mol, *.sdf, *.cdx, *.cml

**DELETE (audit logs) — contain user activity and possibly compound names:**
- audita.txt, auditp.txt

**READ (text files) — scan for compound identifiers and redact:**
- title (experiment titles, often contains compound names!)
- acqus, acqu, acqu2s, acqu2 (acquisition parameters; `$$` path comments embed the original dataset directory which is often the compound name)
- procs, proc, proc2s, proc2 (processing parameters; `$$` path comments embed names)
- **curdat, curdat2, orig (high risk: these carry the explicit `##$NAME=`/`##$NAME2=` dataset-name field, whose angle-bracket value is usually the compound name). Scan them in every dataset: a sanitisation that skipped them left the name in place.**
- scon, meta, parm.txt, clevels, dsp.hdr, eretic, cag_par (Bruker auxiliary text files — may embed path comments with names)
- *.xml (peak lists, metadata, may contain annotations)
- *.txt (except audita.txt, auditp.txt which are deleted)
- pulseprogram (pulse sequence code, typically safe)
- **Any other non-binary file. Do not skip a file just because it is not in the list above: the list is illustrative, not exhaustive. Scan every non-binary file in the dataset.**

**Bruker patterns to scan in every dataset (the most common real-world leaks):**
- `##$NAME= <...>` and `##$NAME2= <...>` — the dataset-name field; the angle-bracket value is almost always the compound name. Redact the value, keep the field key: `##$NAME2= <[REDACTED]>`.
- `$$ <path>` comment lines — Bruker writes the original acquisition/processing path here (e.g. `$$ /disk2/data/<user>/nmr/<truncated name>/7/acqus`, `$$ Z:/.../nmr/<compound name>/...`). The directory component is frequently the compound name. Redact only the name component, preserve the rest of the path.

**Store lists for next steps:**
- files_to_delete: structure files + audit logs
- files_to_read: all text files for identifier scanning
</step>

<step name="dry_run_scan">
**Scan all text files and report findings without modifying anything.**

For each file in the files_to_read list:

1. **Read file content** using Read tool
2. **Apply semantic reasoning to identify compound identifiers** (same categories as scan_and_redact)
3. **Record each finding**; do not write any files

Build a findings manifest:
- Files that would be deleted (structure files, audit logs) — list with reasons
- Identifiers that would be redacted — list with file path, identifier text, and type
- Total counts: files to delete, identifiers to redact, files to modify

This step only reads. Do not use the Write tool or rm commands, and do not modify any files: nothing changes before the user has confirmed the dry-run report.
</step>

<step name="present_dry_run_report">
**Present findings and require explicit user confirmation before proceeding.**

Present the dry-run report:

```markdown
## Sanitisation Dry Run — [dataset_path]

### Files to Delete
[List structure files and audit logs that will be removed, with reasons]

### Identifiers to Redact
| File | Identifier | Type | Action |
|------|-----------|------|--------|
| ... | ... | ... | Replace with [REDACTED] |

### Summary
- Files to delete: N
- Identifiers to redact: N across M files
- Files unchanged: N

**No changes have been made yet.**

Type "proceed" to apply these changes, or "cancel" to abort.
```

**Stop and wait for the user's response.** Do not continue to the delete and redact steps until the user explicitly types "proceed".

If user types "cancel" (or any response other than "proceed"), acknowledge and stop: "Sanitisation cancelled. No files were modified."
</step>

<step name="delete_structure_and_audit_files">
**This step runs only after user confirmation of the dry-run report.**

**Delete structure files and audit logs.**

For each file in files_to_delete list:

```bash
rm -f <filepath>
```

**Track deletions for the report.** Include relative paths from dataset root.

Example deletions:
- 1/<name>.mol
- audita.txt
- auditp.txt
- 3/compound.sdf
</step>

<step name="scan_and_redact">
**This step runs only after user confirmation. The dry_run_scan step has already identified all targets — apply the recorded changes.**

**Read each text file, identify compound identifiers, and redact in-place.**

For each file in files_to_read list:

1. **Read file content** using Read tool (automatically handles UTF-8, Latin-1, CP1252 encoding)

2. **Apply semantic reasoning to identify compound identifiers** (see categories below)

3. **If identifiers found:**
   - Replace each identifier with `[REDACTED]`
   - Write the redacted content back using Write tool
   - Track change (file path, original identifier, type) for report

4. **If no identifiers found:**
   - Skip writing (file unchanged)

---

## Identifier Categories to Detect

**Category A: Chemical Names** (requires semantic understanding)

- IUPAC systematic names: locants, brackets and substituent prefixes around a parent name, such as `<n>-(<substituent>)<parent> acid` or `<n>,<n'>-di<substituent><parent>`
- Trivial/common names: `<compound name>`
- Trade names: `<trade name>`
- All case variants: `<Name>`, `<name>`, `<NAME>`

**Category B: Database Identifiers** (structured patterns)

- CAS numbers (format: xxxxxx-xx-x): "`<CAS number>`", "CAS `<CAS number>`"
- InChI strings (starts with "InChI=1S/"): "InChI=1S/`<formula>`/c..." (the connection, hydrogen and charge layers follow the formula)
- InChIKey (exactly 27 characters, format XXXXXXXXXXXXXX-YYYYYYYYYY-Z): "`<InChIKey>`"
- PubChem/ChEBI IDs: "CID 12345", "CHEBI:12345", "PubChem CID `<number>`"

**Category C: SMILES Strings** (best-effort, low priority)

SMILES notation patterns: element symbols with ring-closure digits, `=` and `#` for multiple bonds, parentheses for branches, lowercase letters for aromatic atoms, for example "`<smiles>`".

**Note:** SMILES detection is low priority. If some SMILES strings are missed, this is acceptable — exploiting SMILES for CASE cheating requires significant effort.

**Category D: File Paths Containing Compound Names**

File content often contains full file paths with compound names embedded:

Example:
```
##TITLE= Parameter file, TopSpin 4.1.0
$$  Z:/<user>/NMR/data/<project>/nmr/<compound name>/1/pdata/1/procs
```

**Redact only the compound name portion:**
```
##TITLE= Parameter file, TopSpin 4.1.0
$$  Z:/<user>/NMR/data/<project>/nmr/[REDACTED]/1/pdata/1/procs
```

A title line works the same way: `TITLE= <compound name> in CDCl3` becomes `TITLE= [REDACTED] in CDCl3`.

**Category E: Dataset Naming Patterns**

nmrXiv patterns:
- "Classics_`<compound name>`" → contains the compound name
- "nmrXiv_`<compound name>`_01" → contains the compound name

Lab naming patterns:
- "`<initials>`_`<compound name>`_01" → contains the compound name
- "`<prefix>`_`<compound name>`_`<date>`" → contains the compound name

Coded patterns (typically safe unless pattern is obvious):
- "AB012_3" → likely a lab code, not revealing
- "Compound_42" → generic

---

## Do Not Redact (False Positive Avoidance)

**Experiment types:**
- 1H, 13C, HSQC, HMBC, COSY, DEPT, NOESY, ROESY, TOCSY, etc.

**Solvents:**
- CDCl3, DMSO-d6, D2O, MeOD, acetone-d6, benzene-d6

**Software names:**
- TopSpin, nmrPipe, MestReNova, Bruker, Varian, Agilent

**Instrument parameters:**
- Frequency values (e.g., "499.870017809999 MHz")
- Sweep widths, acquisition times
- Temperature values (e.g., "298.15 K")
- Dates, timestamps

**Generic placeholders:**
- "Unknown", "Test", "Compound", and other generic labels for samples
- "Standard", "Reference"

**Chemical formulas:**
- "`<formula>`" (molecular formulas are data, not identifiers)

---

**For each redaction:**
Track the change for the report:
- File path (relative to dataset root)
- Original identifier text
- Identifier type (Chemical name - trivial, CAS number, InChI, etc.)
</step>

<step name="present_report">
**After redaction, present a structured report.**

```markdown
## Sanitisation Report

Dataset: <absolute path>
Dataset name: <directory name>

### Files Deleted

[If files were deleted:]
- <relative path 1> (structure file)
- <relative path 2> (audit log)
...

[If no files deleted:]
None (no structure files or audit logs found)

### Identifiers Redacted

[If identifiers were redacted:]
| File | Original Identifier | Type |
|------|-------------------|------|
| 1/pdata/1/title | <compound name> | Chemical name (trivial) |
| 1/acqus | <compound name> | File path component |
| 2/pdata/1/procs | <CAS number> | CAS number |
| peaklist.xml | Classics_<compound name> | Dataset naming pattern |
...

Total: <N> identifiers redacted across <M> files

[If no identifiers found:]
None (no compound identifiers detected)

### Directory Name Warning

[If dataset directory name contains recognisable compound name:]
⚠️  Dataset directory name '<name>' may contain a compound identifier. Consider renaming the directory manually after sanitisation if needed for complete blinding.

[If directory name appears generic:]
Directory name appears generic (no manual renaming needed)
```

**Include summary:**
- "Sanitisation complete. Proceeding to verification..."
</step>

<step name="verify_completeness">
**Full re-scan verification — confirm no identifiers remain.**

Re-read all text files from the files_to_read list (same files scanned in scan_and_redact step).

For each file:
1. Read current content (after redaction)
2. Apply the same semantic identifier detection as in scan_and_redact step
3. Track any identifiers found

**Report verification results:**

**If 0 identifiers found:**
```
## Verification PASSED ✓

Re-scanned all text files in dataset.
No compound identifiers detected in second pass.
Dataset is ready for blind CASE evaluation.
```

**If identifiers found:**
```
## Verification WARNING ⚠️

Found <N> identifiers missed in first pass:

| File | Identifier | Type |
|------|-----------|------|
| <path> | <text> | <type> |
...

Redacting missed identifiers and re-verifying...
```

**If identifiers were found:**
- Redact them immediately (same process as scan_and_redact)
- Re-run verification (third pass)
- Continue until verification passes (0 identifiers found)

**Note:** Verification is a full re-scan, not just a check that specific strings from the manifest were replaced. This catches identifiers missed in the first pass due to variants, context changes, or oversight.

### Mechanical grep backstop (required; catches what the AI re-scan misses)

The AI re-scan above shares the first pass's blind spots: a name overlooked semantically once tends to be overlooked again. Add a deterministic safety net that does not rely on AI re-reading. A sanitisation once passed its AI verification but left dozens of copies of the compound name and of a truncated form of it in `curdat2`/`acqus` `$$` comments; this backstop is the defence against exactly that.

1. **Derive candidate leak tokens** from two sources:
   - The original dataset directory name (the path argument's basename) and any obvious chemical substring of it.
   - Every value seen inside `##$NAME=`/`##$NAME2=` fields and `$$` path comments during discovery — including substrings (e.g. `<compound name>` → also its truncated form, as directory names often shorten it).

2. **Grep the entire tree (text files only) for each token, case-insensitively:**
   ```bash
   # For each candidate token TOK (compound name + lowercase/substring variants):
   grep -rliI "TOK" <dataset_path> 2>/dev/null
   ```
   Use a python3 walk if shell quoting/word-splitting is unreliable (BSD `xargs -0`/zsh `read -d ''` are error-prone here — a python `pathlib.rglob` + `.read_text()` loop is the robust path; skip the binary file set fid/ser/1r/1i/2rr/... and image extensions).

3. **If the grep finds any residual token:** redact it (preserving Bruker field keys and path structure), then re-run both the AI re-scan and this grep backstop. Loop until the grep returns zero hits across all text files.

4. **Final gate:** verification passes only when the mechanical grep returns zero residual-token hits. Report the exact grep command used and its empty result as evidence.
</step>

<step name="handoff_instructions">
**Provide instructions for CASE analysis after sanitisation.**

```markdown
## Next Steps for Blind CASE Evaluation

### A Fresh AI Session Is Required

This AI session has seen the compound identity during sanitisation. To perform valid blind CASE evaluation:

1. **Start a new AI session** (do not continue in this session)

2. **In the new session**, run:
   ```
   /ailsa:case <sanitised_dataset_path> <molecular_formula>
   ```

3. **Provide the molecular formula** (simulating HRMS data), but do not mention the compound name or identity

4. **Do not reference this sanitisation session** and do not share this report with the CASE AI

### Why This Matters

For valid CASE evaluation, the AI must:
- Determine structure from NMR correlations alone (HSQC, HMBC, symmetry)
- Generate and rank candidate structures objectively
- Handle ambiguity without prior knowledge

Using compound identity from metadata invalidates the evaluation — the AI would be confirming a known answer rather than solving the structure from spectroscopic data.

### Dataset Ready

The sanitised dataset at `<dataset_path>` is now ready for blind CASE evaluation.
```
</step>

</process>

## Implementation Notes

**1. Semantic reasoning is required**

This cannot be solved with regex patterns. Chemical names vary enormously:
- IUPAC systematic vs. trivial vs. trade names
- Case variants (`<Name>`, `<name>`, `<NAME>`)
- Embedded in paths, dataset names, descriptors
- Context-dependent (is "Unknown" generic or specific?)

AI semantic understanding is the only reliable approach.

**2. Encoding is handled automatically**

The Read tool automatically detects and handles UTF-8, Latin-1, and CP1252 encodings. Bruker parameter files often use legacy encodings (Latin-1, Windows CP1252) for special characters (degree symbol °, mu μ). Trust the tool — no manual encoding logic needed.

**3. Do not read binary files**

Classify each file before reading it. Attempting to Read binary NMR data (fid, ser, 1r, 2rr, etc.) will fail or return garbage. Use filename patterns to filter before attempting Read.

**4. Redaction is in-place**

The Write tool overwrites files with redacted content. The tool architecture enforces Read-before-Write (you cannot Write a file you haven't Read first), which prevents accidental overwrites.

**5. Verification is a full second pass**

Do not just check that specific manifest strings were replaced. Re-scan all files with the same semantic identifier detection. This catches:
- Variants missed in first pass (different case, partial matches)
- Identifiers in files not initially scanned
- New identifiers exposed by path changes after redaction

**6. Directory renaming is manual**

Claude cannot safely rename a directory while working inside it. If the dataset directory itself is named after the compound (e.g., "`<compound name>`/"), detect this and warn the user to rename manually after sanitisation.

**7. Structure files are deleted, not redacted**

MOL, SDF, CDX, CML files contain the compound structure directly. These must be deleted entirely, not redacted. Same for audit logs (audita.txt, auditp.txt) which contain user activity and timestamps.

**8. Replacement string: [REDACTED]**

Use `[REDACTED]` as the replacement for all identifiers. This is:
- Clear and unambiguous
- Easy to search for during verification
- Standard redaction practice

**9. SMILES detection is best-effort, low priority**

Detecting SMILES notation is not critical. While SMILES strings do reveal structure, they:
- Require significant effort to exploit for CASE (must parse, generate structure, compare)
- Are relatively rare in NMR metadata compared to names and CAS numbers
- Are harder to detect reliably (overlap with generic chemistry notation)

If some SMILES strings are missed, this is acceptable. Focus effort on names and database IDs.
