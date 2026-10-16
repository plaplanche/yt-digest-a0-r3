#!/usr/bin/env bash
# Worker tests: Vitest on worker/.
set -euo pipefail
cd "$(dirname "$0")/../.."

cd worker
npm ci --no-audit --no-fund
npx vitest run
