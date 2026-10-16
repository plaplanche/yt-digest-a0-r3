"""The command `yt-digest-node transcript <video_id> [--langs] [--request-id]` (spec 5)."""

import argparse
import os
import re
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from yt_digest_node import __version__
from yt_digest_node.cleaning import parse_vtt, to_paragraphs
from yt_digest_node.contracts.log_event import LogEventName
from yt_digest_node.contracts.transcript_result import (
    TranscriptResult,
    TranscriptSource,
    TranscriptStatus,
)
from yt_digest_node.extract import Extractor, Failure, choose_track, extractor_from_env
from yt_digest_node.log import emit
from yt_digest_node.pages import paginate, truncate, words
from yt_digest_node.sponsorblock import fetch_segments, sponsor_ratio

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


@dataclass(frozen=True)
class Config:
    """The environment of spec 5.1."""

    langs: tuple[str, ...]
    max_words: int
    page_words: int
    sponsorblock_url: str
    extractor: Extractor


def parse_langs(value: str) -> tuple[str, ...]:
    """A comma-separated language list; ValueError when it holds no language."""
    langs = tuple(lang.strip() for lang in value.split(",") if lang.strip())
    if not langs:
        raise ValueError(f"no language in {value!r}")
    return langs


def _positive(env: Mapping[str, str], name: str, default: int) -> int:
    value = env.get(name, str(default))
    try:
        number = int(value)
    except ValueError:
        number = 0
    if number < 1:
        raise ValueError(f"{name} must be a positive integer, not {value!r}")
    return number


def config_from_env(env: Mapping[str, str]) -> Config:
    """Read spec 5.1's variables, with their defaults; ValueError on an invalid value."""
    return Config(
        langs=parse_langs(env.get("TRANSCRIPT_LANGS", "fr,en")),
        max_words=_positive(env, "MAX_WORDS", 60000),
        page_words=_positive(env, "PAGE_WORDS", 12000),
        sponsorblock_url=env.get("SPONSORBLOCK_URL", "https://sponsor.ajay.app"),
        extractor=extractor_from_env(env),
    )


def _failed(video_id: str, status: TranscriptStatus) -> TranscriptResult:
    return TranscriptResult(
        video_id=video_id,
        status=status,
        lang=None,
        source=None,
        word_count=0,
        truncated=False,
        sponsor_ratio=None,
        pages=[],
    )


def transcript(
    config: Config, video_id: str, langs: Sequence[str], request_id: str | None
) -> TranscriptResult:
    """Run the pipeline for `video_id` and log `fetch.transcript`."""
    started = time.monotonic()
    sponsorblock: str | None = None
    extracted = config.extractor.extract(video_id, langs)
    track = None if isinstance(extracted, Failure) else choose_track(extracted.tracks, langs)
    if isinstance(extracted, Failure):
        result = _failed(video_id, TranscriptStatus(extracted.status))
    elif track is None:
        result = _failed(video_id, TranscriptStatus.no_transcript)
    else:
        segments = fetch_segments(config.sponsorblock_url, video_id, request_id=request_id)
        sponsorblock = segments.state
        paragraphs = to_paragraphs(parse_vtt(track.vtt), segments.segments)
        kept, truncated = truncate(paragraphs, config.max_words)
        pages = paginate(kept, config.page_words)
        result = TranscriptResult(
            video_id=video_id,
            status=TranscriptStatus.ok,
            lang=track.lang,
            source=TranscriptSource(track.source),
            word_count=sum(len(words(page)) for page in pages),
            truncated=truncated,
            sponsor_ratio=(
                None
                if segments.state == "error"
                else sponsor_ratio(segments.segments, extracted.duration)
            ),
            pages=pages,
        )
    emit(
        LogEventName.fetch_transcript,
        request_id=request_id,
        video_id=video_id,
        attrs={
            "outcome": result.status.value,
            "source": result.source.value if result.source else None,
            "words": result.word_count,
            "pages": len(result.pages),
            "sponsor_ratio": result.sponsor_ratio,
            "sponsorblock": sponsorblock,
            "duration_ms": round((time.monotonic() - started) * 1000),
        },
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yt-digest-node")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("transcript", help="print the transcript result of a video")
    command.add_argument("video_id")
    command.add_argument(
        "--langs", help="comma-separated language order (default: TRANSCRIPT_LANGS)"
    )
    command.add_argument("--request-id")
    return parser


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    """Print one transcript result on standard output; exit 2 on a bad argument or variable."""
    parser = _parser()
    args = parser.parse_args(argv)
    if not VIDEO_ID.match(args.video_id):
        parser.error(f"invalid video id: {args.video_id!r}")
    try:
        config = config_from_env(os.environ if env is None else env)
        langs = config.langs if args.langs is None else parse_langs(args.langs)
    except ValueError as error:
        parser.error(str(error))
    emit(LogEventName.service_started, attrs={"version": __version__})
    result = transcript(config, args.video_id, langs, args.request_id)
    sys.stdout.write(result.model_dump_json() + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
