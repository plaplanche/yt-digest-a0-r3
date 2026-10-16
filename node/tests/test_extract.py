import io
from pathlib import Path
from typing import Any

import pytest
from yt_dlp.networking.common import Response
from yt_dlp.networking.exceptions import HTTPError
from yt_dlp.utils import DownloadError

from yt_digest_node.extract import (
    Failure,
    FakeExtractor,
    Track,
    Video,
    YtDlpExtractor,
    choose_track,
    extractor_from_env,
    parse_delay,
)

FIXTURES = Path(__file__).parent / "fixtures" / "ytdlp"
LANGS = ("fr", "en")
VIDEO_ID = "dQw4w9WgXcQ"


def fake(video_id: str) -> Video | Failure:
    return FakeExtractor(FIXTURES).extract(video_id, LANGS)


# Fake extractor


def test_fake_missing_directory_is_unavailable() -> None:
    assert fake("missing0001") == Failure("unavailable")


def test_fake_meta_status_is_returned_as_is() -> None:
    assert fake("blocked0001") == Failure("blocked")
    assert fake("unavail0001") == Failure("unavailable")


def test_fake_reads_duration_and_one_track_per_file() -> None:
    video = fake("choice00001")
    assert isinstance(video, Video)
    assert video.duration == 120.0
    assert {(t.lang, t.source) for t in video.tracks} == {("en", "manual"), ("fr", "auto")}
    english = next(t for t in video.tracks if t.lang == "en")
    assert "Hello." in english.vtt


# Track choice


def test_manual_track_in_any_language_beats_auto_tracks() -> None:
    video = fake("choice00001")
    assert isinstance(video, Video)
    chosen = choose_track(video.tracks, LANGS)
    assert chosen is not None
    assert (chosen.lang, chosen.source) == ("en", "manual")


def test_tracks_are_tried_in_language_order_within_a_source() -> None:
    tracks = [Track("en", "auto", ""), Track("fr", "auto", ""), Track("en", "manual", "")]
    assert choose_track(tracks, ["fr", "en"]) == Track("en", "manual", "")
    assert choose_track(tracks[:2], ["fr", "en"]) == Track("fr", "auto", "")
    assert choose_track(tracks[:2], ["en", "fr"]) == Track("en", "auto", "")


def test_no_track_in_the_languages_is_no_transcript() -> None:
    video = fake("german00001")
    assert isinstance(video, Video)
    assert choose_track(video.tracks, LANGS) is None


# yt-dlp extractor, with yt-dlp replaced by a stub


class StubResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self) -> bytes:
        return self.body


class StubYoutubeDL:
    def __init__(self, info: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.info = info or {}
        self.error = error
        self.options: dict[str, Any] = {}
        self.calls: list[str] = []

    def __call__(self, options: dict[str, Any]) -> "StubYoutubeDL":
        self.options = options
        return self

    def extract_info(self, url: str, download: bool = True) -> dict[str, Any]:
        assert download is False
        self.calls.append(url)
        if self.error is not None:
            raise self.error
        return self.info

    def urlopen(self, req: str) -> StubResponse:
        self.calls.append(req)
        return StubResponse(f"WEBVTT from {req}".encode())


def run(stub: StubYoutubeDL, sleeps: list[float] | None = None) -> Video | Failure:
    extractor = YtDlpExtractor(
        (2.0, 5.0),
        factory=stub,
        sleep=(sleeps if sleeps is not None else []).append,
        uniform=lambda low, high: (low + high) / 2,
    )
    return extractor.extract(VIDEO_ID, LANGS)


def test_ytdlp_options() -> None:
    stub = StubYoutubeDL({"duration": 10})
    run(stub)
    options = dict(stub.options)
    assert options.pop("logger") is not None
    assert options == {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitlesformat": "vtt",
        "quiet": True,
    }
    assert not {"cookiefile", "cookiesfrombrowser"} & stub.options.keys()
    assert stub.calls == [f"https://www.youtube.com/watch?v={VIDEO_ID}"]


def test_ytdlp_returns_vtt_tracks_in_the_languages_with_a_delay_before_each_request() -> None:
    stub = StubYoutubeDL(
        {
            "duration": 212,
            "subtitles": {
                "en": [{"ext": "json3", "url": "u:en.json3"}, {"ext": "vtt", "url": "u:en"}],
                "de": [{"ext": "vtt", "url": "u:de"}],
            },
            "automatic_captions": {"fr": [{"ext": "vtt", "url": "u:fr.auto"}]},
        }
    )
    sleeps: list[float] = []
    assert run(stub, sleeps) == Video(
        212.0,
        (Track("en", "manual", "WEBVTT from u:en"), Track("fr", "auto", "WEBVTT from u:fr.auto")),
    )
    assert stub.calls[1:] == ["u:en", "u:fr.auto"]
    assert sleeps == [3.5, 3.5, 3.5]


def test_ytdlp_private_video_is_unavailable() -> None:
    error = DownloadError(
        f"ERROR: [youtube] {VIDEO_ID}: Private video. "
        "Sign in if you've been granted access to this video"
    )
    assert run(StubYoutubeDL(error=error)) == Failure("unavailable")


def test_ytdlp_age_restricted_and_removed_videos_are_unavailable() -> None:
    for message in ("Sign in to confirm your age", "This video has been removed by the uploader"):
        error = DownloadError(f"ERROR: [youtube] {VIDEO_ID}: {message}")
        assert run(StubYoutubeDL(error=error)) == Failure("unavailable")


def test_ytdlp_bot_check_is_blocked() -> None:
    error = DownloadError(
        f"ERROR: [youtube] {VIDEO_ID}: Sign in to confirm you’re not a bot. "
        "Use --cookies-from-browser or --cookies for the authentication."
    )
    assert run(StubYoutubeDL(error=error)) == Failure("blocked")


def test_ytdlp_subtitle_download_error_is_mapped() -> None:
    class FailingSubtitles(StubYoutubeDL):
        def urlopen(self, req: str) -> StubResponse:
            raise HTTPError(Response(io.BytesIO(), url=req, headers={}, status=403))

    stub = FailingSubtitles({"duration": 1, "subtitles": {"fr": [{"ext": "vtt", "url": "u"}]}})
    assert run(stub) == Failure("unavailable")


# Configuration


def test_delay_parsing() -> None:
    assert parse_delay("2-5") == (2.0, 5.0)
    assert parse_delay("0") == (0.0, 0.0)
    with pytest.raises(ValueError):
        parse_delay("5-2")


def test_extractor_selection() -> None:
    selected = extractor_from_env({"FETCHER_FAKE_YTDLP": "1", "FAKE_YTDLP_DIR": str(FIXTURES)})
    assert isinstance(selected, FakeExtractor)
    with pytest.raises(ValueError):
        extractor_from_env({"FETCHER_FAKE_YTDLP": "1"})
    default = extractor_from_env({})
    assert isinstance(default, YtDlpExtractor)
    assert default.delay == (2.0, 5.0)
