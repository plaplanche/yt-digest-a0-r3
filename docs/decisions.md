# Decisions

Choices the spec leaves open, one dated line each.

- 2026-10-16: `node/` builds with the `uv_build` backend and pins Python to 3.12 (`requires-python = ">=3.12,<3.13"`, `.python-version`).
- 2026-10-16: `worker/` pins TypeScript to `~6.0`, the newest line supported by typescript-eslint; ESLint 10 flat config with `typescript-eslint`'s `strict` preset and `no-explicit-any` as an error.
- 2026-10-16: Vitest runs `worker/tests/**/*.test.ts`; pytest runs `node/tests/`.
- 2026-10-16: The `lint` check runs mypy on `node/src` and `node/tests`, and shellcheck on every `*.sh` file under `scripts/`.
- 2026-10-16: The `contracts` check prints "nothing to check" and passes while `scripts/contracts.sh` does not exist.
- 2026-10-16: Contracts are generated with datamodel-code-generator (Pydantic v2, `StrEnum`s, node dev dependency) and json-schema-to-typescript (worker dev dependency); the Python output is passed through ruff with `node/pyproject.toml`, which ignores E501 in the generated directory.
- 2026-10-16: `scripts/contracts.sh` always generates into a temporary directory, then replaces `worker/src/contracts/` and `node/src/yt_digest_node/contracts/` whole (or, with `--check`, compares them, naming differing, missing and extra files); `CONTRACTS_ROOT` points it at another tree holding `contracts/` and the generated files, for its test.
- 2026-10-16: The `contracts` check installs the node and worker dependencies, runs `./scripts/contracts.sh --check`, then `scripts/tests/contracts-check.sh`, which shows on a copy of the tree that hand edits and schema changes are caught.
- 2026-10-16: The worker validates at runtime with `@cfworker/json-schema` (no `eval`, Workers-compatible) against the schema files in `contracts/`, imported as JSON (`worker/src/validate.ts`).
- 2026-10-16: The log schema keeps `attrs` a free-form object and `request_id`/`video_id` plain strings; the per-event attributes and services of 4.2 are documented in the schema, not enforced. The "null unless `ok`" rules of 4.1 are left to the pipeline, not encoded in the schema.
- 2026-10-16: `emit` leaves out fields set to None, defaults `attrs` to `{}`, sets `ts` and `service` itself (passing them raises `ValueError`); the worker's `log` writes with `console.log`.
- 2026-10-16: Cleaning lives in `yt_digest_node.cleaning`: `parse_vtt(text) -> list[Cue]` (frozen dataclass: `start`, `end` in seconds, raw `lines`) and `to_paragraphs(cues, segments) -> list[str]`; joining with `\n\n` is left to the caller.
- 2026-10-16: VTT blocks are separated by empty lines only (YouTube's single-space lines stay inside their cue); the timing line is the first or second line of a block, and a block without one is skipped.
- 2026-10-16: Step 3 removes every `<…>` tag, then decodes entities with `html.unescape` (so `&lt;` survives as `<`), then removes `[…]` without nesting; whitespace is collapsed with `str.split`.
- 2026-10-16: A kept cue is one that still has a line after step 4; the paragraph gap is rounded to milliseconds before the 2.0 s comparison, since VTT times have millisecond precision.
- 2026-10-16: The SponsorBlock client is `yt_digest_node.sponsorblock.fetch_segments(base_url, video_id, request_id=None)`, built on `urllib` (no new dependency); it returns a `SponsorBlockResult` (`state` `ok`/`none`/`error`, `segments`) and never raises for HTTP or network failures.
- 2026-10-16: A 200 whose body is not a JSON array of items with a numeric `segment: [start, end]` counts as `error` (logged with status 200); `sponsorblock.call` logs `segments` as the number of segments returned and `duration_ms` as an integer.
- 2026-10-16: `sponsor_ratio(segments, duration)` returns 0 when the duration is not positive; the midpoint rule of 5.4 step 2 stays in `cleaning.to_paragraphs`.
