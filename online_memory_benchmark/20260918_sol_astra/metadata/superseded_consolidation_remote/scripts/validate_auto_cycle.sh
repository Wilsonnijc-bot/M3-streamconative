#!/usr/bin/env bash
set -Eeuo pipefail
source_graph=$1
accepted_version=$2
output=$3
mkdir -p "$output"
set +e
"${M3_PYTHON:-python}" -u -m consolidation.native_fixture \
  --source-graph "$source_graph" --accepted-version "$accepted_version" \
  --output "$output" > "$output/validation.log" 2>&1
status=$?
printf '%s\n' "$status" > "$output/exit_status.txt"
exit "$status"
