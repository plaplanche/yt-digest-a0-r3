import json
from typing import Any

import pytest
from pydantic import ValidationError

from yt_digest_node.contracts.log_event import LogEvent, LogEventName
from yt_digest_node.contracts.transcript_result import TranscriptResult


def valid_result() -> dict[str, Any]:
    return {
        "video_id": "dQw4w9WgXcQ",
        "status": "ok",
        "lang": "fr",
        "source": "manual",
        "word_count": 3,
        "truncated": False,
        "sponsor_ratio": 0.125,
        "pages": ["un deux trois"],
    }


def valid_log_line() -> dict[str, Any]:
    return {
        "ts": "2026-10-16T08:30:00.123Z",
        "level": "info",
        "service": "node",
        "event": "sponsorblock.call",
        "video_id": "dQw4w9WgXcQ",
        "attrs": {"status": 200, "segments": 2, "duration_ms": 41},
    }


def test_valid_transcript_result_is_accepted() -> None:
    result = TranscriptResult.model_validate_json(json.dumps(valid_result()))
    assert result.model_dump(mode="json") == valid_result()


def test_transcript_result_without_transcript_is_accepted() -> None:
    data = valid_result() | {
        "status": "no_transcript",
        "lang": None,
        "source": None,
        "word_count": 0,
        "sponsor_ratio": None,
        "pages": [],
    }
    assert TranscriptResult.model_validate(data).model_dump(mode="json") == data


@pytest.mark.parametrize(
    "change",
    [
        {"extra": 1},
        {"video_id": "too-short"},
        {"video_id": "dQw4w9WgXc!"},
        {"status": "done"},
        {"source": "robot"},
        {"word_count": -1},
        {"sponsor_ratio": 1.5},
    ],
)
def test_invalid_transcript_result_is_rejected(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        TranscriptResult.model_validate_json(json.dumps(valid_result() | change))


def test_transcript_result_with_a_missing_field_is_rejected() -> None:
    data = valid_result()
    del data["lang"]
    with pytest.raises(ValidationError):
        TranscriptResult.model_validate(data)


def test_valid_log_line_is_accepted() -> None:
    line = LogEvent.model_validate_json(json.dumps(valid_log_line()))
    assert line.event is LogEventName.sponsorblock_call


@pytest.mark.parametrize(
    "change",
    [
        {"event": "transcript.leaked"},
        {"extra": "x"},
        {"level": "fatal"},
        {"service": "browser"},
        {"ts": "2026-10-16T08:30:00Z"},
    ],
)
def test_invalid_log_line_is_rejected(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        LogEvent.model_validate_json(json.dumps(valid_log_line() | change))


def test_catalogue_is_a_str_enum() -> None:
    assert [str(e) for e in LogEventName] == [
        "service.started",
        "fetch.transcript",
        "sponsorblock.call",
    ]
