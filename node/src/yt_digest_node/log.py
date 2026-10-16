"""Structured logs: one JSON line per event on standard error, validated against the contract."""

import sys
from datetime import UTC, datetime

from yt_digest_node.contracts.log_event import LogEvent

_RESERVED = {"ts", "service"}


def emit(event: str, level: str = "info", **fields: object) -> None:
    """Write one log line for `event`.

    `fields` are the optional `request_id`, `video_id` and `attrs` of the contract; a field set to
    None is left out. Raises ValueError for an event outside the catalogue or an unknown field.
    """
    reserved = _RESERVED & fields.keys()
    if reserved:
        raise ValueError(f"fields set by the logger: {', '.join(sorted(reserved))}")
    now = datetime.now(UTC)
    line = LogEvent.model_validate(
        {
            "ts": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z",
            "level": level,
            "service": "node",
            "event": event,
            "attrs": {},
            **{key: value for key, value in fields.items() if value is not None},
        }
    )
    sys.stderr.write(line.model_dump_json(exclude_unset=True) + "\n")
