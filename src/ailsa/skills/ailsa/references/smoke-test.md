# Smoke-test report

The pass/fail report the coordinator prints in smoke-test mode (SMOKE_TEST true), once the three
checkpoints of the smoke test early exit have arrived or one of them has failed.

**Result for each checkpoint:**
- PASS: message received, with all required fields validated.
- FAIL: message not received, or validate_message rejected it, or agent error or timeout (more
  than 5 minutes).

**Print the report:**
```
========================================
SMOKE TEST RESULTS
========================================

| Checkpoint               | Status    | Details                    |
|--------------------------|-----------|----------------------------|
| Team spawned             | PASS/FAIL | 4 agents created           |
| NMR chemist peak pick    | PASS/FAIL | [SETUP-COMPLETE] received  |
| LSD engineer build file  | PASS/FAIL | [ITERATION-COMPLETE] received |
| Devil's advocate validate | PASS/FAIL | [VALIDATION-PASSED/BLOCKED] |

Overall: PASS / FAIL (N/4 checkpoints passed)
```

**After the report:** proceed to the terminate_team step (normal team cleanup).
