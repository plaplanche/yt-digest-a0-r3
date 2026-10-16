"""End-to-end tests: the command as a subprocess, the fake extractor and a local SponsorBlock."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeSponsorBlock

from yt_digest_node.contracts.log_event import LogEvent
from yt_digest_node.contracts.transcript_result import TranscriptResult
from yt_digest_node.pages import words

FIXTURES = Path(__file__).parent / "fixtures" / "ytdlp"
NO_SPONSORBLOCK = "http://127.0.0.1:9"
# The console script installed next to the interpreter by `uv sync`.
COMMAND = str(Path(sys.executable).parent / "yt-digest-node")


def run(
    *args: str, sponsorblock: str = NO_SPONSORBLOCK, **env: str
) -> subprocess.CompletedProcess[str]:
    environ = {
        key: value
        for key, value in os.environ.items()
        if key.lower() not in ("http_proxy", "https_proxy", "all_proxy")
    }
    environ.update(
        FETCHER_FAKE_YTDLP="1",
        FAKE_YTDLP_DIR=str(FIXTURES),
        SPONSORBLOCK_URL=sponsorblock,
        NO_PROXY="127.0.0.1",
        **env,
    )
    return subprocess.run(
        [COMMAND, "transcript", *args],
        env=environ,
        capture_output=True,
        text=True,
        timeout=60,
    )


def result(process: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert process.returncode == 0, process.stderr
    output: dict[str, Any] = json.loads(process.stdout)
    TranscriptResult.model_validate(output)
    return output


def logs(process: subprocess.CompletedProcess[str]) -> list[dict[str, Any]]:
    lines = [json.loads(line) for line in process.stderr.splitlines()]
    for line in lines:
        LogEvent.model_validate(line)
    return lines


def failed(video_id: str, status: str) -> dict[str, Any]:
    return {
        "video_id": video_id,
        "status": status,
        "lang": None,
        "source": None,
        "word_count": 0,
        "truncated": False,
        "sponsor_ratio": None,
        "pages": [],
    }


def test_ok_with_sponsor_cuts(server: FakeSponsorBlock) -> None:
    server.body = json.dumps([{"segment": [9, 15], "category": "sponsor"}]).encode()
    process = run("sponsor0001", "--request-id", "req-42", sponsorblock=server.url)
    assert result(process) == {
        "video_id": "sponsor0001",
        "status": "ok",
        "lang": "en",
        "source": "manual",
        "word_count": 13,
        "truncated": False,
        "sponsor_ratio": 0.06,
        "pages": [
            "Quokkas gather marmalade beside the lighthouse.\n\n"
            "Pelicans & walruses debate quietly at dawn."
        ],
    }
    assert "videoID=sponsor0001" in server.paths[0]
    started, call, fetch = logs(process)
    assert started["event"] == "service.started"
    assert started["attrs"] == {"version": "0.1.0"}
    assert call["event"] == "sponsorblock.call"
    assert call["request_id"] == "req-42"
    assert fetch["event"] == "fetch.transcript"
    assert fetch["video_id"] == "sponsor0001"
    assert fetch["request_id"] == "req-42"
    assert isinstance(fetch["attrs"].pop("duration_ms"), int)
    assert fetch["attrs"] == {
        "outcome": "ok",
        "source": "manual",
        "words": 13,
        "pages": 1,
        "sponsor_ratio": 0.06,
        "sponsorblock": "ok",
    }


def test_log_lines_hold_no_transcript_text(server: FakeSponsorBlock) -> None:
    process = run("sponsor0001", sponsorblock=server.url)
    text = " ".join(result(process)["pages"])
    # Short words such as "at" occur inside field names; the fixture's long words are distinctive.
    distinctive = [word.strip(".").lower() for word in words(text) if len(word) >= 6]
    assert "zephyrcorp" in distinctive
    for word in distinctive:
        assert word not in process.stderr.lower()


def test_langs_and_paging_and_truncation_from_the_environment(server: FakeSponsorBlock) -> None:
    process = run("sponsor0001", sponsorblock=server.url, MAX_WORDS="6", PAGE_WORDS="2")
    output = result(process)
    assert output["truncated"] is True
    assert output["word_count"] == 6
    assert output["pages"] == ["Quokkas gather", "marmalade\n\n[…]", "quietly at", "dawn."]
    assert all(0 < len(words(page)) <= 2 for page in output["pages"])
    french = result(run("sponsor0001", "--langs", "fr", sponsorblock=server.url))
    assert (french["lang"], french["source"]) == ("fr", "auto")


def test_sponsorblock_404_gives_a_zero_ratio(server: FakeSponsorBlock) -> None:
    server.status = 404
    process = run("sponsor0001", sponsorblock=server.url)
    assert result(process)["sponsor_ratio"] == 0
    assert logs(process)[-1]["attrs"]["sponsorblock"] == "none"


def test_sponsorblock_failure_gives_a_null_ratio_and_the_full_text() -> None:
    process = run("sponsor0001")
    output = result(process)
    assert output["status"] == "ok"
    assert output["sponsor_ratio"] is None
    assert "Zephyrcorp." in output["pages"][0]
    assert logs(process)[-1]["attrs"]["sponsorblock"] == "error"


@pytest.mark.parametrize(
    ("video_id", "status", "args"),
    [
        ("german00001", "no_transcript", ()),
        ("choice00001", "no_transcript", ("--langs", "de")),
        ("unavail0001", "unavailable", ()),
        ("missing0001", "unavailable", ()),
        ("blocked0001", "blocked", ()),
    ],
)
def test_failures_exit_0_with_an_empty_result(
    video_id: str, status: str, args: tuple[str, ...]
) -> None:
    process = run(video_id, *args, "--request-id", "r")
    assert result(process) == failed(video_id, status)
    started, fetch = logs(process)
    assert started["event"] == "service.started"
    assert fetch["event"] == "fetch.transcript"
    assert fetch["request_id"] == "r"
    assert fetch["attrs"]["outcome"] == status
    assert fetch["attrs"]["sponsorblock"] is None


@pytest.mark.parametrize(
    ("args", "env"),
    [
        (("too-short",), {}),
        (("dQw4w9WgXc!",), {}),
        (("dQw4w9WgXcQ", "--langs", ","), {}),
        (("dQw4w9WgXcQ",), {"MAX_WORDS": "0"}),
        (("dQw4w9WgXcQ",), {"PAGE_WORDS": "many"}),
    ],
)
def test_bad_arguments_exit_2_without_a_result(args: tuple[str, ...], env: dict[str, str]) -> None:
    process = run(*args, **env)
    assert process.returncode == 2
    assert process.stdout == ""
