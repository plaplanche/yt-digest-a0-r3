#!/usr/bin/env bash
# Node tests: pytest on node/tests/.
set -euo pipefail
cd "$(dirname "$0")/../.."

uv sync --locked --directory node
uv run --locked --directory node pytest tests
