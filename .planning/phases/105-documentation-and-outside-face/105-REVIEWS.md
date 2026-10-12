---
phase: 105
reviewers: [user-decision]
reviewed_at: 2026-10-12T12:00:00Z
plans_reviewed: [105-01-PLAN.md, 105-03-PLAN.md, 105-04-PLAN.md, 105-06-PLAN.md, 105-09-PLAN.md]
---

# Plan Review — Phase 105

## User decision 2026-10-12: D-13 superseded by D-13a

**Severity:** BLOCKER for the five plans listed above; the other four plans (105-02, 105-05,
105-07, 105-08) are unaffected and must not change.

**What changed.** The plans implement D-13: describe the CASE method as hub-and-spoke (the
coordinator spawns one specialist at a time). The user superseded that with **D-13a**
(105-CONTEXT.md):

- The agent team — specialists that coordinate with each other — is the **design**. That
  includes the direct channels: LSD engineer ↔ devil's advocate review loop, and requests to the
  NMR chemist.
- The user's interactive test runs in June/July 2026 ran exactly that, with working statistical
  detection.
- The benchmark ran a **restricted configuration**:
  - no team, because Claude Code forms no teammates in `claude -p`, so the specialists ran one
    at a time under the coordinator;
  - no statistical detection, because the compute host's reference DB had the outdated schema.
- The docs say so explicitly wherever the 69 % appear. They do not claim the full system is
  better; Phase 110 measures that.
- Hub-and-spoke appears only as the description of how benchmark runs executed.

**Required changes per plan**

- **105-01 (README):**
  - "The CASE Agent Team" describes the team as the design, with the direct channels.
  - The diagram shows the team, not a hub-and-spoke star.
  - The Evaluation section states that the 69 % were measured without the team and without
    statistical detection.
  - Replace the `hub-and-spoke` acceptance grep with checks for the team description and for
    the restricted-configuration sentence.
- **105-03 (ARCHITECTURE + BENCHMARK):**
  - ARCHITECTURE's agent layer describes the team design.
  - BENCHMARK's new "How a benchmark run executes" section says the runs were headless, so
    there was no team and specialists ran one at a time, and the compute host lacked the
    statistics tables.
  - Adjust the must_haves, acceptance criteria and threat mitigation T-105-06 accordingly.
- **105-04 (INSTALLATION / SERVER_BOOTSTRAP / NUS-PORTABILITY):**
  - The setup docs keep the agent-team flag as a requirement of the team design.
  - Note that unattended (`-p`) runs do not form a team.
  - Note that the full reference DB, with the current schema, is needed for statistical
    detection.
  - Remove hub-and-spoke as the method description.
- **105-06 (deck):**
  - The agent-team slide shows the team with its direct channels.
  - The benchmark slide states the restricted configuration in one line.
  - Adjust the must_haves.
- **105-09 (phase gate):** replace the hub-and-spoke check with checks for D-13a:
  - team described as the design;
  - restricted configuration stated where the 69 % appear;
  - no claim that the full system performs better.

**Facts to use** (verified 2026-10-09..12; sources: the quick-task research in
`.planning/quick/261006-iob-*` and `ailsa-paper/scripts/blindness/`, `scripts/toolstatus/`):

- In 173 headless benchmark run folders there was no team: 0 `TeamCreate`, a median of 6
  specialist spawns per run, and 7 specialist-to-specialist messages in total.
- The detection commands returned no usable data in any September run, because the host DB is
  schema 3.
- Prediction, ranking and identity derivation worked normally.
