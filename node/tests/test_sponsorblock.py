import json
import socket
import urllib.parse
from typing import Any

import pytest
from conftest import FakeSponsorBlock

from yt_digest_node.sponsorblock import SponsorBlockResult, fetch_segments, sponsor_ratio

VIDEO_ID = "dQw4w9WgXcQ"


def log_line(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 1
    line: dict[str, Any] = json.loads(lines[0])
    assert line["event"] == "sponsorblock.call"
    assert line["video_id"] == VIDEO_ID
    assert isinstance(line["attrs"].pop("duration_ms"), int)
    return line


def test_200_gives_the_segments(
    server: FakeSponsorBlock, capsys: pytest.CaptureFixture[str]
) -> None:
    server.body = json.dumps(
        [
            {"segment": [10, 20.5], "category": "sponsor", "UUID": "a"},
            {"segment": [30.25, 40], "category": "selfpromo", "UUID": "b"},
        ]
    ).encode()
    result = fetch_segments(server.url + "/", VIDEO_ID, request_id="req-1")
    assert result == SponsorBlockResult("ok", ((10.0, 20.5), (30.25, 40.0)))
    line = log_line(capsys)
    assert line["request_id"] == "req-1"
    assert line["attrs"] == {"status": 200, "segments": 2}


def test_request_path_and_categories(server: FakeSponsorBlock) -> None:
    fetch_segments(server.url, VIDEO_ID)
    path, _, query = server.paths[0].partition("?")
    assert path == "/api/skipSegments"
    assert "%5B%22sponsor%22%2C%22selfpromo%22%2C%22interaction%22%5D" in query
    assert urllib.parse.parse_qs(query) == {
        "videoID": [VIDEO_ID],
        "categories": ['["sponsor","selfpromo","interaction"]'],
    }


def test_404_gives_no_segments(
    server: FakeSponsorBlock, capsys: pytest.CaptureFixture[str]
) -> None:
    server.status, server.body = 404, b"Not Found"
    assert fetch_segments(server.url, VIDEO_ID) == SponsorBlockResult("none", ())
    line = log_line(capsys)
    assert "request_id" not in line
    assert line["attrs"] == {"status": 404, "segments": 0}


def test_500_is_an_error(server: FakeSponsorBlock, capsys: pytest.CaptureFixture[str]) -> None:
    server.status, server.body = 500, b"oops"
    assert fetch_segments(server.url, VIDEO_ID) == SponsorBlockResult("error", ())
    assert log_line(capsys)["attrs"] == {"status": 500, "segments": 0}


def test_malformed_200_body_is_an_error(
    server: FakeSponsorBlock, capsys: pytest.CaptureFixture[str]
) -> None:
    server.body = b'[{"segment": [1]}]'
    assert fetch_segments(server.url, VIDEO_ID) == SponsorBlockResult("error", ())
    assert log_line(capsys)["attrs"] == {"status": 200, "segments": 0}


def test_connection_refused_is_an_error_with_status_0(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    assert fetch_segments(f"http://127.0.0.1:{port}", VIDEO_ID) == SponsorBlockResult("error", ())
    assert log_line(capsys)["attrs"] == {"status": 0, "segments": 0}


def test_ratio_is_0_without_segments() -> None:
    assert sponsor_ratio([], 100.0) == 0.0


def test_ratio_counts_overlapping_segments_once() -> None:
    # Union of [10, 30], [20, 40] and [35, 50] is [10, 50]; [60, 70] adds 10.
    assert sponsor_ratio([(35, 50), (10, 30), (60, 70), (20, 40)], 100.0) == 0.5


def test_ratio_clips_to_the_duration() -> None:
    assert sponsor_ratio([(90, 130), (-5, 5), (200, 250)], 100.0) == 0.15


def test_ratio_is_rounded_to_3_decimals() -> None:
    assert sponsor_ratio([(0, 1)], 3.0) == 0.333
    assert sponsor_ratio([(0, 2)], 3.0) == 0.667
