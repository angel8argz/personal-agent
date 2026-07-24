#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
if command -v timeout >/dev/null 2>&1; then TIMEOUT=timeout
elif command -v gtimeout >/dev/null 2>&1; then TIMEOUT=gtimeout
else TIMEOUT=""
fi
run_with_timeout() {
  local secs="$1"; shift
  if [ -n "$TIMEOUT" ]; then "$TIMEOUT" "$secs" "$@"; return $?; fi
  "$@" & local pid=$!
  ( sleep "$secs"; kill -TERM "$pid" ) 2>/dev/null & local watcher=$!
  disown "$watcher" 2>/dev/null
  wait "$pid" 2>/dev/null; local status=$?
  kill "$watcher" 2>/dev/null
  return "$status"
}
LEDGER="memory/goal-ledger.tsv"; VIOLATIONS=0
for g in goals/*.md; do
  [ -e "$g" ] || continue
  grep -q '^status: retired' "$g" && continue
  pred=$(grep '^predicate:' "$g" | cut -d' ' -f2-); name=$(basename "$g" .md)
  start=$(( $(date +%s%N) / 1000000 ))
  if run_with_timeout 60 bash -c "$pred" >/dev/null 2>&1; then r=pass
    sed -i.bak "s/^status:.*/status: satisfied/; s/^last-pass:.*/last-pass: $(date +%F)/" "$g" && rm -f "$g.bak"
  else r=FAIL; VIOLATIONS=$((VIOLATIONS+1)); sed -i.bak "s/^status:.*/status: VIOLATED/" "$g" && rm -f "$g.bak"; fi
  echo -e "$(date -Iseconds)\t$name\t$r\t$(( $(( $(date +%s%N) / 1000000 )) - start ))" >> "$LEDGER"
done
[ "$VIOLATIONS" -gt 0 ] && { grep -l '^status: VIOLATED' goals/*.md; exit 1; }
echo "all standing goals hold"