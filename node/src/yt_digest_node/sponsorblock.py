"""SponsorBlock (spec 5.3): the skipped segments of a video and the share of it they cover."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from yt_digest_node.contracts.log_event import LogEventName
from yt_digest_node.log import emit

CATEGORIES = ("sponsor", "selfpromo", "interaction")
TIMEOUT_SECONDS = 10.0

Segment = tuple[float, float]


@dataclass(frozen=True)
class SponsorBlockResult:
    """The outcome of one call: `ok` (200), `none` (404) or `error`, and the segments in seconds."""

    state: Literal["ok", "none", "error"]
    segments: tuple[Segment, ...]


def _parse_segments(body: bytes) -> tuple[Segment, ...]:
    """Read the `segment: [start, end]` of each item of a 200 body; ValueError if malformed."""
    items = json.loads(body)
    if not isinstance(items, list):
        raise ValueError("not a JSON array")
    segments: list[Segment] = []
    for item in items:
        segment = item.get("segment") if isinstance(item, dict) else None
        if not (
            isinstance(segment, list)
            and len(segment) == 2
            and all(isinstance(t, int | float) and not isinstance(t, bool) for t in segment)
        ):
            raise ValueError("item without a [start, end] segment")
        segments.append((float(segment[0]), float(segment[1])))
    return tuple(segments)


def fetch_segments(
    base_url: str,
    video_id: str,
    *,
    request_id: str | None = None,
    timeout: float = TIMEOUT_SECONDS,
) -> SponsorBlockResult:
    """Call `{base_url}/api/skipSegments` for `video_id` and log `sponsorblock.call`.

    Never raises for an HTTP or network failure: anything but a 200 with a valid body or a 404
    gives the `error` state and no segments.
    """
    query = urllib.parse.urlencode(
        {"videoID": video_id, "categories": json.dumps(list(CATEGORIES), separators=(",", ":"))}
    )
    url = f"{base_url.rstrip('/')}/api/skipSegments?{query}"
    started = time.monotonic()
    status = 0
    result = SponsorBlockResult("error", ())
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            status = response.status
            body = response.read()
        if status == 200:
            result = SponsorBlockResult("ok", _parse_segments(body))
    except urllib.error.HTTPError as error:
        status = error.code
        if status == 404:
            result = SponsorBlockResult("none", ())
    except (OSError, ValueError):
        pass
    emit(
        LogEventName.sponsorblock_call,
        request_id=request_id,
        video_id=video_id,
        attrs={
            "status": status,
            "segments": len(result.segments),
            "duration_ms": round((time.monotonic() - started) * 1000),
        },
    )
    return result


def sponsor_ratio(segments: Sequence[Segment], duration: float) -> float:
    """Length of the union of `segments` clipped to [0, duration], over `duration`, to 3 decimals.

    0 when there is no segment, or when the duration is not positive.
    """
    if duration <= 0:
        return 0.0
    clipped = sorted(
        (max(start, 0.0), min(end, duration))
        for start, end in segments
        if min(end, duration) > max(start, 0.0)
    )
    covered = reached = 0.0
    for start, end in clipped:
        # Sorted by start: only the part beyond what is already covered adds to the union.
        start = max(start, reached)
        if end > start:
            covered += end - start
            reached = end
    return round(covered / duration, 3)
