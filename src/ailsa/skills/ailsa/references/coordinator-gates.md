# Coordinator gates before the results

Two gates run after the ranking, once `analysis/final_results.md` exists, and before the results
are presented: the multiplicity coverage gate, only when the multiplicity was ambiguous, and the
identity gate. The coverage gate runs first, because it can reopen the run. Both involve the
devil's advocate (DA): its multiplicity gate (G-MULT) feeds the coverage gate, and its name and
structure cross-check (G-IDENT) is the identity gate's review.

## Contents

- Coverage gate
- Identity gate

## Coverage gate

The pre-accept multiplicity coverage gate is deterministic and independent of MAE.

**When it runs:** only when a `[MULTIPLICITY-AMBIGUOUS]` record exists for this run, that is when a
`## Multiplicity Coverage` ledger is present in CASE-PROGRESS.md. Without that record, skip this
step and go straight to identity_gate; the single-family flow is unaffected.

**Lifecycle position:** the same pre-accept point as identity_gate, after the union has been ranked
and `analysis/final_results.md` exists, before accept and present_results. It runs before
identity_gate, because it may reopen the run and has to resolve first. It is the
coverage-triggered analogue of the Quality Convergence Failure loop pattern, which reopens on MAE;
coverage_gate reopens on missing-family coverage, not on MAE.

**Deterministic and independent of MAE.** The gate does not look at MAE, plausibility or rank. A
structure from the wrong multiplicity class can score a low MAE and be judged plausible while the
MAE-based quality loop stays silent; that is why this gate does not key off MAE. Read the
`## Multiplicity Coverage` ledger and evaluate two set-containment conditions:

1. `viable_families ⊆ searched_families`: every family the NMR chemist enumerated has its own
   `iteration_NN_<family>/` run and `[ITERATION-COMPLETE]`. Count by searched, not ranked: a family
   whose `solutions.smi` conversion was skipped for size still counts as searched; do not require a
   ranked `solutions.smi`.
2. Every DA-mandated model (each `[MULT-EVIDENCE-FOR] model=X` from G-MULT) is in
   `searched_families`.

**Verdict:**

- **PASS**: both conditions hold. Write `gate verdict: PASS` to the `## Multiplicity Coverage`
  ledger and proceed to identity_gate.
- **FAIL**: a viable family or a DA-mandated model is not in searched_families. The run does not
  accept. Write `gate verdict: FAIL — missing: <family/model list>` to the ledger, then reopen:
  push the LSD engineer to run the missing families or models, with the multiplicity-coverage
  reopen advisory (what, not how: name the missing family or model and say that it has to be
  searched in its own `iteration_NN_<family>/` directory). When their `[ITERATION-COMPLETE]`
  messages arrive, re-run the deduplicated union rank (per the LSD engineer's union-ranking
  contract), update searched_families in the ledger, and re-enter coverage_gate. Do not advance to
  identity_gate until the gate passes.

This gate triggers on coverage, never on MAE. A converged, plausible-looking, low-MAE run is still
rejected if a viable family or a DA-mandated model was never searched. The reopen follows the
Multiplicity Coverage Gap loop pattern.

After the gate passes, proceed to identity_gate.

## Identity gate

The post-solution G-IDENT review is the independent advisory layer, and it runs before
present_results.

This step runs once, after [RANKING-COMPLETE] (that is when `analysis/final_results.md` exists) and
before deliver_advisory_and_results and terminate_team. It is the independent second opinion on
the reported mapping of name to structure. The solution analyst's own run of the deterministic
`ailsa identify` is the binding check; this G-IDENT pass is the separate LLM cross-check, and it
does not re-run `ailsa identify`.

The DA is idle and does not act on its own, so push the trigger:

```
SendMessage(
  type="message",
  recipient="devils-advocate",
  content="[BEGIN] G-IDENT — post-solution name↔structure review. analysis/final_results.md is written. Run only your G-IDENT gate (name and structure cross-check, post-solution): read the reported trivial name + the top SMILES, reason independently about whether the name plausibly matches the drawn structure — do not call ailsa identify / derive_identity (that is the analyst's binding layer). Apply the two G-IDENT triggers: a specific isomer name asserted where the data do not resolve the regiochemistry, and a recalled trivial name whose ring linkage or symmetry does not match the drawn structure. Reply [G-IDENT-PASSED] or [G-IDENT-FLAGGED] with a one-line rationale.",
  summary="Post-solution G-IDENT review"
)
```

Then wait for the DA's reply (it arrives as a turn and wakes you). On the reply:
- Write a `### Devils-Advocate (G-IDENT post-solution)` entry into CASE-PROGRESS.md with the
  verdict and the rationale.
- [G-IDENT-FLAGGED] is advisory and never blocks the report. If flagged, make sure the reported
  trivial name in `final_results.md` is rendered `(tentative, unverified)` and carry the DA's
  concern into the results presentation. Then proceed.
- [G-IDENT-PASSED]: proceed.

If the DA errors or does not reply within a reasonable window, note "G-IDENT review unavailable"
in CASE-PROGRESS.md and proceed: the review is advisory and non-blocking, so do not hang the run
waiting for it.

After recording the G-IDENT outcome, proceed to deliver_advisory_and_results.
