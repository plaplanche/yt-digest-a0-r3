"""Transcript cleaning (spec 5.4): from VTT text to paragraphs of clean text."""

import html
import re
from collections.abc import Sequence
from dataclasses import dataclass

_TIMESTAMP = r"(?:(\d+):)?(\d{2}):(\d{2})\.(\d{3})"
_TIMING = re.compile(rf"^{_TIMESTAMP}[ \t]+-->[ \t]+{_TIMESTAMP}(?:[ \t].*)?$")
_IGNORED_BLOCK = re.compile(r"^(?:NOTE|STYLE|REGION)(?:[ \t]|$)")
_TAG = re.compile(r"<[^>]*>")
_ANNOTATION = re.compile(r"\[[^\]]*\]")
_PARAGRAPH_GAP = 2.0


@dataclass(frozen=True)
class Cue:
    """One VTT cue: start and end in seconds, and its raw text lines."""

    start: float
    end: float
    lines: tuple[str, ...]


def _seconds(hours: str | None, minutes: str, seconds: str, millis: str) -> float:
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def parse_vtt(text: str) -> list[Cue]:
    """Parse VTT text into cues (5.4 step 1).

    The header, `NOTE`, `STYLE` and `REGION` blocks, cue identifiers and cue settings are ignored;
    a block without a timing line is skipped.
    """
    text = text.removeprefix("﻿").replace("\r\n", "\n").replace("\r", "\n")
    cues: list[Cue] = []
    for index, block in enumerate(re.split(r"\n{2,}", text)):
        lines = block.strip("\n").split("\n")
        if (index == 0 and lines[0].startswith("WEBVTT")) or _IGNORED_BLOCK.match(lines[0]):
            continue
        for position, line in enumerate(lines[:2]):
            timing = _TIMING.match(line)
            if timing:
                g = timing.groups()
                start, end = _seconds(*g[:4]), _seconds(*g[4:])
                cues.append(Cue(start, end, tuple(lines[position + 1 :])))
                break
    return cues


def _clean_line(line: str) -> str:
    line = html.unescape(_TAG.sub("", line))
    return " ".join(_ANNOTATION.sub("", line).split())


def to_paragraphs(cues: Sequence[Cue], segments: Sequence[tuple[float, float]]) -> list[str]:
    """Apply 5.4 steps 2 to 5 to `cues` and return the paragraphs, in order.

    `segments` are the SponsorBlock segments `(start, end)` in seconds; a cue whose midpoint lies
    in one (start inclusive, end exclusive) is dropped.
    """
    paragraphs: list[list[str]] = []
    last_line: str | None = None
    last_end: float | None = None
    for cue in cues:
        midpoint = (cue.start + cue.end) / 2
        if any(start <= midpoint < end for start, end in segments):
            continue
        kept: list[str] = []
        for line in map(_clean_line, cue.lines):
            if line and line != last_line:
                kept.append(line)
                last_line = line
        if not kept:
            continue
        # Timestamps have millisecond precision: rounding keeps 5.1 - 3.1 equal to 2.0.
        if last_end is None or round(cue.start - last_end, 3) >= _PARAGRAPH_GAP:
            paragraphs.append([])
        paragraphs[-1].extend(kept)
        last_end = cue.end
    return [" ".join(lines) for lines in paragraphs]
