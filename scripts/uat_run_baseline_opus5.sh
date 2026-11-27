#!/bin/zsh
# RETIRED. This launcher re-ran the 103 baseline datasets on Opus 5 into
# case-uat-results-opus5-baseline, one of the frozen paper-benchmark result folders. Its job
# is done (the benchmark closed on 2026-10-01), and the watchdog now pins a different model:
# being "safe to re-run", it would have filed runs of the new model under the Opus 5 arm.
# It therefore does nothing and exits 2.
#
# A new series names its own results folder and goes through the watchdog directly:
#
#   python3 -u scripts/uat_watchdog.py --cases ... --results-dir <new folder on Sheldon>
#
# The watchdog refuses the paper folders and any folder that already holds runs of another
# model (see scripts/README.md). The old body, including the heavy-atom ordering, is in git
# history: git show 8060ba3:scripts/uat_run_baseline_opus5.sh

echo "uat_run_baseline_opus5.sh is retired: it wrote into a frozen paper-benchmark folder." >&2
echo "Start a new series with: python3 -u scripts/uat_watchdog.py --cases ... --results-dir <new folder>" >&2
exit 2
