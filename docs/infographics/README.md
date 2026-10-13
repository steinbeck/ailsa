# AILSA infographics

An editable **8-slide 16:9 infographic deck** about AILSA (AI + LSD + Agents), for talking
to scientific colleagues. Light + dark theme, print-to-PDF ready.

The slides are **generated** from a Python build script — that script is the source of
truth, not the HTML. Edit `build.py`, re-run it, and the HTML/PDF regenerate.

## The slides

1. **Overview** — the combination thesis (domain skill-set + thin tools + an agent team),
   spectrum motif, GitHub repo
2. **The idea** — why an agent; spectra in, structure out; emergent (not forced) rings
3. **The pipeline** — Bruker data → pick → detect → build → LSD solve → rank → identity
   gate, plus the input-directory layout
4. **The agent team** — coordinator + 4 specialists that coordinate with each other: the
   direct review loop between the LSD engineer and the devil's advocate, and requests to
   the NMR chemist; a diagnostic specialist on escalation
5. **nmrXiv data source** — `ailsa fetch nmrxiv <DOI>`; where the CASE examples come from
6. **Blind benchmark** — how the method is measured, the headline (69.1 % rank 1 on 256
   public datasets), the one-line restricted configuration, the size limit, and the paired
   comparison against the previous model — figures and configuration from
   `docs/BENCHMARK.md`
7. **CASE1–9 worked examples** — RDKit structures, formula, nmrXiv ID, solved status
8. **By the numbers** — DB / HOSE / fragments / tests / benchmark / CLI command groups;
   credits (Nuzillard/LSD, Bremser/HOSE); Get it (repo, PyPI, database DOI)

## Files

| File | Role |
|------|------|
| `build.py` | **Source of truth.** Assembles `deck.html` from the structure SVGs + slide content (HTML/CSS live inline here). |
| `gen_structures.py` | Regenerates `structures.json` — draws the 9 CASE structures from SMILES via RDKit. Only needed if you change a molecule. |
| `structures.json` | Cached RDKit SVG depictions (so a plain layout edit needs no RDKit). |
| `deck.html` | **Generated** — the rendered deck. Don't hand-edit; `build.py` overwrites it. |
| `ailsa-infographics.pdf` | **Generated** — 16:9 PDF, one slide per page. |

## Rebuild

```bash
cd docs/infographics

# 1. (only if you changed a structure/SMILES) regenerate the depictions — needs rdkit
python gen_structures.py

# 2. regenerate deck.html
python build.py

# 3. (optional) export the 16:9 PDF, one slide per page
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --no-pdf-header-footer \
  --print-to-pdf="ailsa-infographics.pdf" "file://$PWD/deck.html"
```

## Editing tips

- **Text / wording / layout / colours** → edit the inline HTML+CSS strings in `build.py`,
  re-run step 2. All design tokens (palette, type, spacing) are CSS custom properties at
  the top of the `<style>` block, defined for both light and dark themes.
- **A molecule** → edit its SMILES in the `CASES` list in `gen_structures.py`, run step 1
  then step 2. Structures render on deliberately light "paper" cards so they stay legible
  in dark theme too.
- **Slide order / count** → slides are `<section class="slide">` blocks in `build.py`;
  keep the footer counters (`0N / 08`) in sync if you add/remove one.
- **Ground-truth data** (SMILES, formulas, nmrXiv IDs, solved status) came from
  `.planning/CASE-DATASET-IDENTITIES.md` + `PROJECT.md`/`STATE.md` — update there first,
  then mirror here.

## When to update (recurring maintenance)

The deck bakes in **project facts** that drift over time. Refresh it when they change —
most commonly at **milestone close** (`/gsd-complete-milestone`), or when a CASE result
flips solved↔partial, or when the benchmark is re-run. This is also flagged as a
maintenance pointer in the repo `CLAUDE.md`.

Things that go stale, and where they live in the source:

| Fact | Source of truth | In this deck |
|------|-----------------|--------------|
| CASE1–9 identities / structures | `.planning/CASE-DATASET-IDENTITIES.md` | `gen_structures.py` (SMILES) + `build.py` (`CASES`) |
| solved / partial status | blind-UAT log + `STATE.md` | `build.py` `CASES` status field (slide 7) |
| benchmark figures and run configuration | `docs/BENCHMARK.md` | `build.py` slide 6 |
| headline numbers (DB, HOSE, fragments, tests, CLI groups) | `PROJECT.md` / `STATE.md` / `ailsa database info` | `build.py` slide-8 `.stats` |
| agent roster and channels | `.claude/agents/ailsa-*.md` | `build.py` slide 4 |

Update the source first, then mirror into `build.py`, then rebuild (steps above).
