#!/bin/bash
# Runs every frontend and the analyzer, each time-boxed and memory-limited.
set -u
cd "$(dirname "$0")" || exit
W=work
export UV_PROJECT_ENVIRONMENT="$PWD/$W/.venv"
limit() { timeout -s KILL 120 prlimit --as=4294967296 "$@"; }
mkdir -p "$W/ir" results
(cd go_frontend && go build -o "../$W/go_frontend" .)
uv sync --frozen -q
front() {
  local name=$1 lang=$2 root=$3; shift 3
  local start=$SECONDS
  if [ "$lang" = py ]; then
    limit "$UV_PROJECT_ENVIRONMENT/bin/python" -I py_frontend.py "$root" "$W/ir/$name.jsonl" "$@"
  else
    limit "$W/go_frontend" "$root" "$W/ir/$name.jsonl" "$@"
  fi
  echo "$name frontend exit=$? seconds=$((SECONDS - start))"
  start=$SECONDS
  limit "$UV_PROJECT_ENVIRONMENT/bin/python" -I analyze.py "$name" "$W/ir/$name.jsonl" "results/$name.json"
  echo "$name analyze exit=$? seconds=$((SECONDS - start))"
}
for spec in "$@"; do
  case $spec in
    cpython) front cpython py $W/cpython/Lib ;;
    django) front django py $W/django django ;;
    mypy) front mypy py $W/mypy mypy mypyc ;;
    saleor) front saleor py $W/saleor saleor ;;
    go) front go go $W/go/src ;;
    cockroach) front cockroach go $W/cockroach pkg ;;
    kubernetes) front kubernetes go $W/kubernetes pkg cmd staging plugin ;;
    gitea) front gitea go $W/gitea models modules routers services cmd ;;
    odoo) front odoo py $W/odoo odoo addons ;;
    homeassistant) front homeassistant py $W/homeassistant homeassistant ;;
    tidb) front tidb go $W/tidb pkg br cmd dumpling lightning ;;
  esac
done
