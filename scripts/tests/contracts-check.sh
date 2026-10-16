#!/usr/bin/env bash
# Shows that ./scripts/contracts.sh --check fails and names the file when a generated file is
# edited by hand or a schema changes without regeneration. Runs on a copy of the contracts tree.
set -euo pipefail
cd "$(dirname "$0")/../.."

ts=worker/src/contracts
py=node/src/yt_digest_node/contracts
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

fresh_copy() {
  rm -rf "$work/root"
  mkdir -p "$work/root/worker/src" "$work/root/node/src/yt_digest_node"
  cp -R contracts "$work/root/contracts"
  cp -R "$ts" "$work/root/$ts"
  cp -R "$py" "$work/root/$py"
}

# expect <status> <case> <named file>...: runs the check on the copy and asserts its exit status
# and that its output names each file.
expect() {
  local want="$1" case="$2" got=0 file
  shift 2
  CONTRACTS_ROOT="$work/root" ./scripts/contracts.sh --check >"$work/out" 2>&1 || got=$?
  if [[ "$got" != "$want" ]]; then
    echo "FAIL $case: exit $got, expected $want" >&2
    cat "$work/out" >&2
    exit 1
  fi
  for file in "$@"; do
    if ! grep -qF "$file" "$work/out"; then
      echo "FAIL $case: output does not name $file" >&2
      cat "$work/out" >&2
      exit 1
    fi
  done
  echo "ok   $case"
}

fresh_copy
expect 0 "up-to-date files pass"

fresh_copy
echo "export type Extra = string;" >>"$work/root/$ts/log-event.ts"
expect 1 "hand-edited TypeScript file" "$ts/log-event.ts"

fresh_copy
sed -i 's/    blocked = "blocked"/    blocked = "blocked"\n    gone = "gone"/' "$work/root/$py/transcript_result.py"
expect 1 "hand-edited Python file" "$py/transcript_result.py"

fresh_copy
rm "$work/root/$py/log_event.py"
expect 1 "deleted generated file" "$py/log_event.py"

fresh_copy
sed -i 's/"blocked"\]/"blocked", "gone"]/' "$work/root/contracts/transcript-result.schema.json"
expect 1 "schema changed without regeneration" "$ts/transcript-result.ts" "$py/transcript_result.py"
