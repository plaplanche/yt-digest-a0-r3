import json
import re

import pytest

from yt_digest_node.contracts.log_event import LogEventName
from yt_digest_node.log import emit


def test_emit_writes_one_json_line_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    emit(
        LogEventName.fetch_transcript,
        video_id="dQw4w9WgXcQ",
        request_id="req-1",
        attrs={"outcome": "ok", "sponsor_ratio": None, "words": 3},
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    lines = captured.err.splitlines()
    assert len(lines) == 1
    line = json.loads(lines[0])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", line.pop("ts"))
    assert line == {
        "level": "info",
        "service": "node",
        "event": "fetch.transcript",
        "request_id": "req-1",
        "video_id": "dQw4w9WgXcQ",
        "attrs": {"outcome": "ok", "sponsor_ratio": None, "words": 3},
    }


def test_emit_defaults_attrs_and_leaves_out_none_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    emit("service.started", level="debug", request_id=None)
    line = json.loads(capsys.readouterr().err)
    assert line["level"] == "debug"
    assert line["attrs"] == {}
    assert "request_id" not in line


def test_event_outside_the_catalogue_raises(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(ValueError):
        emit("transcript.leaked")
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("field", ["text", "ts", "service"])
def test_unknown_field_raises(field: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(ValueError):
        emit("service.started", **{field: "x"})
    assert capsys.readouterr().err == ""


def test_unknown_level_raises() -> None:
    with pytest.raises(ValueError):
        emit("service.started", level="fatal")
