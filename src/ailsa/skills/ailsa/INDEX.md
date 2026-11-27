---
name: ailsa
description: The AILSA frontier skill for Claude Code, made of the /ailsa:* commands and the ailsa-* specialist agents. It determines the structure of an unknown organic compound from NMR data, using the ailsa command line and the LSD solver. Use when asked to elucidate, solve or identify a structure from Bruker NMR data, to dereplicate a 13C peak list, to predict 13C shifts, to sanitise a dataset, or to check the setup.
metadata:
  version: "0.2.0"
  requires: "ailsa CLI of the same version; LSD and outlsd on PATH; the reference database; Claude Code"
---

# AILSA frontier skill

AILSA is a team of Claude Code agents that elucidates structures from NMR data with the LSD solver.
A coordinator command runs the workflow and hands the chemistry to four specialist agents.

## Commands

- [case](commands/case.md): the full structure elucidation workflow, `/ailsa:case`
- [dereplicate](commands/dereplicate.md): match a 13C peak list against the reference database
- [predict](commands/predict.md): predict 13C shifts for a SMILES
- [sanitise](commands/sanitise.md): remove identifying metadata from a dataset copy
- [status](commands/status.md): check that CLI, LSD and database are ready
- [help](commands/help.md): which command fits

## Agents

- [ailsa-nmr-chemist](agents/ailsa-nmr-chemist.md): reads the spectra, picks peaks, derives constraints
- [ailsa-lsd-engineer](agents/ailsa-lsd-engineer.md): writes and runs the LSD input
- [ailsa-solution-analyst](agents/ailsa-solution-analyst.md): ranks and reports candidate structures
- [ailsa-devils-advocate](agents/ailsa-devils-advocate.md): challenges constraints and results
- [ailsa-diagnostic](agents/ailsa-diagnostic.md): diagnoses LSD failures, spawned only on escalation

## References

- [advisory-templates](references/advisory-templates.md): message templates between agents
- [constraint-inventory](references/constraint-inventory.md): the constraint record at the top of every LSD file, how it is built and carried forward
- [coordinator-gates](references/coordinator-gates.md): the coordinator's two gates before the results: multiplicity coverage and the G-IDENT name review
- [diagnose-solution-explosion](references/diagnose-solution-explosion.md): the diagnostic specialist's five checks when LSD returns 1000+ solutions
- [diagnose-zero-solutions](references/diagnose-zero-solutions.md): the diagnostic specialist's five checks when LSD returns no solution
- [diagnostic-report](references/diagnostic-report.md): template and file name of `DIAGNOSTIC-REPORT.md`
- [intervention](references/intervention.md): the coordinator's advisories per loop pattern, intervention counting, delegation and escalation
- [inventory-validation](references/inventory-validation.md): the devil's advocate's inventory checks: extraction, reconciliation with the file and the previous iteration, ELIM budget, the gates G7 and G-PROP-EVIDENCE
- [loop-patterns](references/loop-patterns.md): iteration and stopping patterns
- [lsd-reference](references/lsd-reference.md): LSD commands, filter block, running LSD and the checklist before every run
- [lsd-search](references/lsd-search.md): what LSD searches: DUPL/MAXS, fragment goodlist, per-family multiplicity search
- [monitoring](references/monitoring.md): how the coordinator drives a run: reacting to replies, iterating, ranking, stall recovery, loop detection and diagnosis
- [multiplicity-ambiguity](references/multiplicity-ambiguity.md): searching every aliphatic multiplicity family when the spectra leave it open
- [nmr-basics](references/nmr-basics.md): NMR facts the agents rely on
- [run-record](references/run-record.md): what the coordinator notes, how it reads the generated progress log, how it declares or closes the run
- [smoke-test](references/smoke-test.md): the pass/fail report of the coordinator's smoke-test mode
- [validation-checks](references/validation-checks.md): the devil's advocate's pre-solver checks on every LSD file, each with its severity

## Install

`ailsa skill install ailsa --target claude` copies the skill into `~/.claude`.
Maintainers add `--link` to link it to the checkout instead.
