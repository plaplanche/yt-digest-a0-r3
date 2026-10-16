"""Extractors and track choice (spec 5.2): a video's duration and subtitle tracks."""

import json
import random
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, cast

import yt_dlp
from yt_dlp.networking.exceptions import RequestError
from yt_dlp.utils import YoutubeDLError

Source = Literal["manual", "auto"]
SOURCES: tuple[Source, ...] = ("manual", "auto")

YDL_OPTIONS: dict[str, Any] = {
    "skip_download": True,
    "writesubtitles": True,
    "writeautomaticsub": True,
    "subtitlesformat": "vtt",
}

# The keys of yt-dlp's info dict holding each source's tracks: {lang: [{"ext", "url"}, ...]}.
TRACK_KEYS: tuple[tuple[Source, str], ...] = (
    ("manual", "subtitles"),
    ("auto", "automatic_captions"),
)


@dataclass(frozen=True)
class Track:
    lang: str
    source: Source
    vtt: str


@dataclass(frozen=True)
class Video:
    """A successful extraction: the duration in seconds and the subtitle tracks."""

    duration: float
    tracks: tuple[Track, ...]


@dataclass(frozen=True)
class Failure:
    status: Literal["unavailable", "blocked"]


class Extractor(Protocol):
    def extract(self, video_id: str, langs: Sequence[str]) -> Video | Failure:
        """Extract `video_id`; tracks in other languages than `langs` may be left out."""
        ...


def choose_track(tracks: Sequence[Track], langs: Sequence[str]) -> Track | None:
    """The first `manual` track in the order of `langs`, then the first `auto` one; else None."""
    for source in SOURCES:
        for lang in langs:
            for track in tracks:
                if track.source == source and track.lang == lang:
                    return track
    return None


class FakeExtractor:
    """Reads `<root>/<video_id>/`: `meta.json` and one `<lang>.<manual|auto>.vtt` file per track."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def extract(self, video_id: str, langs: Sequence[str]) -> Video | Failure:
        directory = self.root / video_id
        if not directory.is_dir():
            return Failure("unavailable")
        meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
        status = meta.get("status")
        if status in ("unavailable", "blocked"):
            return Failure(status)
        tracks: list[Track] = []
        for path in sorted(directory.glob("*.vtt")):
            lang, _, source = path.stem.rpartition(".")
            if lang and source in SOURCES:
                tracks.append(Track(lang, source, path.read_text(encoding="utf-8")))
        return Video(float(meta["duration"]), tuple(tracks))


class Response(Protocol):
    def read(self) -> bytes: ...


class YoutubeDL(Protocol):
    """The part of `yt_dlp.YoutubeDL` the extractor uses."""

    def extract_info(self, url: str, download: bool = ...) -> dict[str, Any]: ...

    def urlopen(self, req: str) -> Response: ...


class _SilentLogger:
    """Keeps yt-dlp off standard output and standard error, which carry the result and the logs."""

    def debug(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        pass


def _default_factory(options: dict[str, Any]) -> YoutubeDL:
    return cast(YoutubeDL, yt_dlp.YoutubeDL(cast(Any, options)))


def map_error(error: Exception) -> Failure:
    """A bot check is `blocked`; any other yt-dlp error (private, age-restricted, removed) is
    `unavailable`."""
    return Failure("blocked" if "not a bot" in str(error).lower() else "unavailable")


class YtDlpExtractor:
    """yt-dlp as a library, without cookies; waits a random delay before each YouTube request."""

    def __init__(
        self,
        delay: tuple[float, float],
        *,
        factory: Callable[[dict[str, Any]], YoutubeDL] = _default_factory,
        sleep: Callable[[float], None] = time.sleep,
        uniform: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self.delay = delay
        self.factory = factory
        self.sleep = sleep
        self.uniform = uniform

    def _wait(self) -> None:
        self.sleep(self.uniform(*self.delay))

    def extract(self, video_id: str, langs: Sequence[str]) -> Video | Failure:
        ydl = self.factory({**YDL_OPTIONS, "quiet": True, "logger": _SilentLogger()})
        try:
            self._wait()
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            tracks: list[Track] = []
            for source, key in TRACK_KEYS:
                available: dict[str, list[dict[str, Any]]] = info.get(key) or {}
                for lang in langs:
                    url = next(
                        (f["url"] for f in available.get(lang, []) if f.get("ext") == "vtt"), None
                    )
                    if url is not None:
                        self._wait()
                        vtt = ydl.urlopen(url).read().decode("utf-8")
                        tracks.append(Track(lang, source, vtt))
        except (YoutubeDLError, RequestError) as error:
            return map_error(error)
        return Video(float(info.get("duration") or 0), tuple(tracks))


def parse_delay(value: str) -> tuple[float, float]:
    """`YT_DELAY_SECONDS`: `<min>-<max>` or a single number of seconds."""
    low, _, high = value.partition("-")
    bounds = (float(low), float(high or low))
    if not 0 <= bounds[0] <= bounds[1]:
        raise ValueError(f"invalid YT_DELAY_SECONDS: {value!r}")
    return bounds


def extractor_from_env(env: Mapping[str, str]) -> Extractor:
    """The fake extractor when `FETCHER_FAKE_YTDLP=1` (no delay), else the yt-dlp extractor."""
    if env.get("FETCHER_FAKE_YTDLP") == "1":
        root = env.get("FAKE_YTDLP_DIR")
        if not root:
            raise ValueError("FAKE_YTDLP_DIR is required when FETCHER_FAKE_YTDLP=1")
        return FakeExtractor(Path(root))
    return YtDlpExtractor(parse_delay(env.get("YT_DELAY_SECONDS", "2-5")))
