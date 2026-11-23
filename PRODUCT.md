# Product

<!-- impeccable:product-schema 1 -->

> Written 2026-11-23 without an interview: the owner asked for the prototype to be finished without
> questions. Every fact below is inferred from `.planning/research/webview-redesign/SPEC.md`
> (draft 2.2) and the owner's statements in that session, and is marked *(inferred)* where the owner
> has not confirmed it in so many words.

## Platform

web

## Stack

Delegated *(inferred)*: the specification recommends a TypeScript single-page app shipped prebuilt
inside the `ailsa` Python wheel (owner decision D13 still open). The first prototype is a single
static HTML file with inline CSS and JavaScript, no dependencies, so it opens offline.

## Users

- **Bench chemist** (primary): a synthetic or natural-products chemist with an unknown compound, a
  molecular formula and a standard NMR set (1H, 13C, DEPT or edited HSQC, HSQC, HMBC, COSY). Reads
  1H fluently, HMBC with difficulty, does not know LSD. Wants the proposed structure, how sure it is,
  what is open and what to measure next; checks a long run from a phone.
- **NMR expert** (primary): facility scientist, co-author or referee. Must verify in 10 to 20 minutes
  whether the data support the result, on a desktop or tablet.
- **PI, collaborator, editor:** receives a link or an HTML file, reads a one-page summary.

## Product Purpose

AILSA ("AI + LSD + Agents") elucidates the constitution of organic compounds from NMR data: Claude
agents read the spectra, encode correlations as constraints for Jean-Marc Nuzillard's LSD solver,
run it, and rank the candidate structures by 13C shift prediction. The interface lets a chemist
follow a run and understand its result, and lets an expert judge whether the result is right.
Success: the chemist knows the result, its certainty, what is open and the next step from one screen;
the expert finds every piece of evidence without opening a file.

## Positioning

An autonomous agent team does the elucidation; the interface shows its work and its evidence rather
than offering a manual elucidation workbench. Every claim drills down to the measured peak, the
solver constraint and the solver output behind it.

## Operating Context

- Runs take minutes to hours and write their results next to the NMR data; they run on laptops and on
  a shared Linux group server.
- Two separate views, never shown together (owner decision 2026-11-23): a much simpler chemist view
  and the expert view, with one switch and "why?" links between them.
- Spectra must be inspectable during and after the run: every 1D and 2D spectrum zoomable, the 2D
  contour floor raised and lowered, picked peaks marked (owner request 2026-11-23).
- Runs are on unpublished compounds by default: confidential, local first, read-only.

## Capabilities and Constraints

- The result is a proposal, constitution only; stereochemistry is open unless the agents determined
  it. A ranked list always has a first place, so a failed run must look failed.
- The interface reports facts and shows the agents' judgements as theirs; it adds no chemical
  verdicts of its own (owner decision 2026-11-23).
- Names only from the deterministic identity tool; agent-recalled names are never shown.
- LSD atom numbers are the only atom numbering.
- The run record that would feed the interface does not exist yet; the prototype uses data from one
  finished run and labels anything illustrative.

## Brand Commitments

- Name: AILSA ("AI + LSD + Agents"). The former working name must not appear.
- LSD by Jean-Marc Nuzillard is credited up front; the reference database carries its standard
  source credit (see the repository README).
- No visual identity exists yet; the previous web view is an anti-reference.

## Evidence on Hand

- One finished, experimentally confirmed run on an unpublished compound in the private test data
  (JCAMP-DX data, seven solver rounds, a final structure and a named runner-up). Its identity and
  structure must not leave private channels.
- The benchmark figures in `docs/BENCHMARK.md` (constitution only, headless configuration).
- No calibrated confidence figures exist; none may be invented.

## Product Principles

1. The record, not the narrative: show what tools computed, attribute what agents judged.
2. Honest result: proposal, not proof; absence is a visible state.
3. Two audiences, two views: simple for the bench, complete for the expert.
4. Every statement drills down to its evidence.
5. Confidential and blind-safe by default.

## Accessibility & Inclusion

WCAG 2.2 AA as the target *(inferred, D21 open)*; colour never carries meaning alone (edited-HSQC
signs, deviations); full keyboard use; every canvas has an equivalent table.
