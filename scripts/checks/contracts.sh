#!/usr/bin/env bash
# Contracts check: the committed generated files match the schemas in contracts/, and the check
# itself catches stale files.
set -euo pipefail
cd "$(dirname "$0")/../.."

uv sync --locked --directory node
(cd worker && npm ci --no-audit --no-fund)
./scripts/contracts.sh --check
./scripts/tests/contracts-check.sh
