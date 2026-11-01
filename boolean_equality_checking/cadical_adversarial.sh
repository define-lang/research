#!/bin/sh
# Times CaDiCaL on every planted pair of the adversarial instances, as an
# independent solver to compare with beq's own. Appends to results/cadical.jsonl.
# Each file gets 600 seconds; a file that runs out gets a "file_timeout" line.
# With file names as arguments, only those files in work/cadical are run.
set -eu
cd "$(dirname "$0")"
OUT=work/cadical
if [ $# -eq 0 ]; then
  G="uv run --frozen --python 3.14 python gen/generate.py"
  for i in 8 12 16 20 24 28 32 40 48 64; do $G parity --out $OUT --inputs $i --copies 3; done
  for b in 3 4 5 6 7 8 9 10 11 12; do for k in commuted kogge; do $G multiplier --out $OUT --bits $b --kind $k; done; done
  for i in 8 12 16 20 24 28 32 40; do $G hwb --out $OUT --inputs $i; done
  set -- $(cd $OUT && ls *.aag)
fi
for f in "$@"; do echo "$OUT/$f"; done | xargs -P 4 -I{} sh -c '
  cd gen && timeout 600 uv run --no-project --python 3.13 --with python-sat --with click python cadical_miter.py ../{} \
    || echo "{\"file\": \"../{}\", \"status\": \"file_timeout\", \"time_s\": 600}"' >> results/cadical.jsonl
