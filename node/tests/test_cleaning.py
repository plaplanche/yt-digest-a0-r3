from pathlib import Path

from yt_digest_node.cleaning import Cue, parse_vtt, to_paragraphs

FIXTURES = Path(__file__).parent / "fixtures" / "vtt"


def load(name: str) -> list[Cue]:
    return parse_vtt((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_ignores_header_blocks_identifiers_and_settings() -> None:
    assert load("manual.vtt") == [
        Cue(1.0, 3.1, ("<v Alice>Welcome to the show.</v>",)),
        Cue(5.1, 7.0, ("<v.loud Bob>Today we talk about</v>", "<i>caching</i> and <b>queues</b>.")),
        Cue(8.9, 10.0, ("<u>First</u>, caching.",)),
        Cue(3723.5, 3725.0, ("That is all for today.",)),
    ]


def test_parse_keeps_raw_lines_of_auto_track() -> None:
    cues = load("auto.vtt")
    assert len(cues) == 7
    assert cues[0] == Cue(
        0.0, 2.31, (" ", "bonjour<00:00:00.480><c> à</c><00:00:00.960><c> tous</c>")
    )


def test_parse_accepts_crlf_and_bom() -> None:
    text = "﻿WEBVTT\r\n\r\n00:01.000 --> 00:02.500\r\nHello\r\n"
    assert parse_vtt(text) == [Cue(1.0, 2.5, ("Hello",))]


def test_manual_track_paragraphs() -> None:
    assert to_paragraphs(load("manual.vtt"), []) == [
        "Welcome to the show.",
        "Today we talk about caching and queues. First, caching.",
        "That is all for today.",
    ]


def test_gap_of_2_0_s_starts_a_new_paragraph() -> None:
    # 3.100 -> 5.100: a 2.0 s gap, which float subtraction would make 1.9999999999999996.
    paragraphs = to_paragraphs(load("manual.vtt"), [])
    assert paragraphs[0] == "Welcome to the show."
    assert paragraphs[1].startswith("Today we talk about")


def test_gap_of_1_9_s_does_not_start_a_new_paragraph() -> None:
    # 7.000 -> 8.900: a 1.9 s gap.
    paragraphs = to_paragraphs(load("manual.vtt"), [])
    assert paragraphs[1].endswith("queues. First, caching.")


def test_inline_tags_and_timestamps_are_removed() -> None:
    joined = "\n\n".join(to_paragraphs(load("auto.vtt"), []))
    assert "<" not in joined
    assert "bonjour à tous" in joined


def test_rolling_duplicates_are_removed() -> None:
    assert to_paragraphs(load("auto.vtt"), []) == [
        "bonjour à tous aujourd'hui on parle",
        "de vidéo",
    ]


def test_only_a_line_equal_to_the_previous_kept_line_is_dropped() -> None:
    cues = [
        Cue(0, 1, ("yes",)),
        Cue(1, 2, ("no", "yes")),
        Cue(2, 3, ("[Music]",)),
        Cue(3, 4, ("yes",)),
    ]
    assert to_paragraphs(cues, []) == ["yes no yes"]


def test_annotations_removed_entities_decoded_whitespace_collapsed() -> None:
    assert to_paragraphs(load("annotations.vtt"), []) == [
        "Tom & Jerry are back again <not a tag> \"quoted\" 'single'",
        "- Encore !",
    ]


def test_cue_left_empty_by_cleaning_does_not_count_for_the_gap() -> None:
    # The [Musique] cue ends at 7.0, 1.0 s before the last cue; the last kept cue ends at 5.0.
    paragraphs = to_paragraphs(load("annotations.vtt"), [])
    assert "[Musique]" not in paragraphs[0]
    assert "[Applause]" not in paragraphs[0]
    assert paragraphs[1] == "- Encore !"


def test_sponsor_segment_drops_cue_by_midpoint() -> None:
    cues = load("manual.vtt")  # first cue: 1.0 -> 3.1, midpoint 2.05
    assert to_paragraphs(cues, [(2.05, 3.0)])[0].startswith("Today")
    assert to_paragraphs(cues, [(0.0, 2.05)])[0] == "Welcome to the show."


def test_empty_track_gives_no_paragraph() -> None:
    assert to_paragraphs(parse_vtt("WEBVTT\n"), []) == []
