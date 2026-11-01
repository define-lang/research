#!/bin/sh
# Rebuilds beq, checks the methods against each other, and reruns every
# experiment, appending to results/. Every check is limited to 30 seconds
# and a few GB, except the final whole-program study. The whole-program
# runs of Experiment 5, which take minutes per graph, aren't repeated.
# Uses a private environment in work/venv, so it never touches the shared
# .venv of the research repository.
set -eu
cd "$(dirname "$0")"
src/build.sh
export UV_PROJECT_ENVIRONMENT="$PWD/work/venv"
PY="uv run --frozen --python 3.14 python"
mkdir -p work/tmp
$PY check_methods.py --count 300 > results/check_methods.txt
$PY experiments.py operations --jobs 6
$PY experiments.py adversarial --jobs 6
$PY experiments.py adversarial --jobs 4 --only auto_kissat --timeout 1800
$PY experiments.py library --jobs 6
$PY experiments.py limits --jobs 6
$PY dispatch_budget.py > results/dispatch_budget.txt
$PY abc_compare.py --part operations
$PY abc_compare.py --part adversarial
$PY abc_compare.py --part library
$PY native_solvers.py --jobs 4 --timeout 300
$PY sdd_compare.py
$PY matching_experiment.py
$PY hierarchy_experiment.py
$PY steady_state_experiment.py
$PY caller_redundancy_experiment.py
$PY final_program_experiment.py
