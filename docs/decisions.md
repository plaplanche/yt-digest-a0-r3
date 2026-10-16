# Decisions

Choices the spec leaves open, one dated line each.

- 2026-10-16: `node/` builds with the `uv_build` backend and pins Python to 3.12 (`requires-python = ">=3.12,<3.13"`, `.python-version`).
- 2026-10-16: `worker/` pins TypeScript to `~6.0`, the newest line supported by typescript-eslint; ESLint 10 flat config with `typescript-eslint`'s `strict` preset and `no-explicit-any` as an error.
- 2026-10-16: Vitest runs `worker/tests/**/*.test.ts`; pytest runs `node/tests/`.
- 2026-10-16: The `lint` check runs mypy on `node/src` and `node/tests`, and shellcheck on every `*.sh` file under `scripts/`.
- 2026-10-16: The `contracts` check prints "nothing to check" and passes while `scripts/contracts.sh` does not exist.
