---
description: "Check ailsa environment readiness. Use when: is ailsa installed, check setup, verify environment, is LSD available, database status"
allowed-tools:
  - Bash
---

<objective>
Report the readiness of the ailsa environment by checking three components:
ailsa CLI, LSD solver binaries, and the compound database.

Present a clear status summary showing what is ready and what needs action.
</objective>

<process>

<step name="check_ailsa">
Run `ailsa --version` via Bash.

**MINIMUM_REQUIRED_VERSION = 0.1.0**

- If command not found: record status as MISSING, action: "Run: pip install ailsa"
- If successful: record version string, then compare against minimum required version:
  1. Parse installed version from output format `ailsa, version X.Y.Z` — extract X.Y.Z
  2. Split both versions on `.` into [major, minor, patch] integers
  3. Compare major first, then minor, then patch (semver order)
  4. If installed version >= MINIMUM_REQUIRED_VERSION: record status as OK
  5. If installed version < MINIMUM_REQUIRED_VERSION: record status as INCOMPATIBLE with action:
     ```
     Installed ailsa version X.Y.Z is below minimum required 0.1.0.
     Run: pip install --upgrade ailsa
     ```
</step>

<step name="check_lsd">
Run `ailsa lsd check` via Bash.

- Parse output for LSD and outlsd availability
- If both found: record as OK
- If either missing: record as MISSING, action: "Download from http://eos.univ-reims.fr/LSD/ and add bin/ to PATH"
</step>

<step name="check_database">
Run `ailsa database info data/reference/ailsa-derep.db` via Bash.

- If successful: record compound count and HOSE statistics from output
- If file not found or error: record as MISSING, action: "Run: ailsa database download"
</step>

<step name="report">
Present a combined status summary to the user:

```
# ailsa Environment Status

| Component        | Status               | Details                          |
|------------------|----------------------|----------------------------------|
| ailsa CLI      | OK/MISSING/INCOMPATIBLE | version or install/upgrade cmd |
| LSD solver       | OK/MISSING           | availability or download link    |
| outlsd           | OK/MISSING           | availability or download link    |
| Compound database| OK/MISSING           | stats or download command        |
```

If all OK: "Environment is ready for structure elucidation."
If any MISSING: list required actions.
If any INCOMPATIBLE: "Version mismatch detected. Upgrade before running workflows."
</step>

</process>
