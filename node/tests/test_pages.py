from yt_digest_node.pages import MARKER, paginate, truncate, words


def numbered(start: int, stop: int) -> str:
    return " ".join(f"w{i}" for i in range(start, stop))


def test_text_within_max_words_is_kept() -> None:
    paragraphs = [numbered(0, 6), numbered(6, 10)]
    assert truncate(paragraphs, 10) == (paragraphs, False)


def test_truncation_keeps_first_and_last_halves_around_the_marker() -> None:
    kept, truncated = truncate([numbered(0, 25)], 10)
    assert truncated
    assert kept == [numbered(0, 5), MARKER, numbered(20, 25)]
    pages = paginate(kept, 12000)
    assert sum(len(words(page)) for page in pages) == 10


def test_truncation_keeps_the_paragraph_breaks_inside_both_parts() -> None:
    paragraphs = [numbered(0, 3), numbered(3, 12), numbered(12, 22), numbered(22, 25)]
    kept, truncated = truncate(paragraphs, 10)
    assert truncated
    assert kept == [numbered(0, 3), numbered(3, 5), MARKER, numbered(20, 22), numbered(22, 25)]


def test_truncation_with_an_odd_max_words_keeps_twice_its_half() -> None:
    kept, _ = truncate([numbered(0, 25)], 11)
    assert kept == [numbered(0, 5), MARKER, numbered(20, 25)]


def test_the_marker_is_not_a_word() -> None:
    assert words(f"a b\n\n{MARKER}\n\nc") == ["a", "b", "c"]


def test_whole_paragraphs_are_grouped_within_page_words() -> None:
    paragraphs = [numbered(0, 2), numbered(2, 5), numbered(5, 9), numbered(9, 10)]
    assert paginate(paragraphs, 5) == [
        f"{numbered(0, 2)}\n\n{numbered(2, 5)}",
        f"{numbered(5, 9)}\n\n{numbered(9, 10)}",
    ]


def test_a_paragraph_longer_than_page_words_is_cut() -> None:
    paragraphs = [numbered(0, 3), numbered(3, 15), numbered(15, 17)]
    pages = paginate(paragraphs, 5)
    assert pages == [
        numbered(0, 3),
        numbered(3, 8),
        numbered(8, 13),
        f"{numbered(13, 15)}\n\n{numbered(15, 17)}",
    ]
    assert all(0 < len(words(page)) <= 5 for page in pages)
    assert [w for page in pages for w in words(page)] == words(" ".join(paragraphs))


def test_pages_joined_give_back_the_text_when_nothing_is_cut() -> None:
    paragraphs = [numbered(0, 4), numbered(4, 5), numbered(5, 8), numbered(8, 13)]
    pages = paginate(paragraphs, 5)
    assert all(len(words(page)) <= 5 for page in pages)
    assert "\n\n".join(pages) == "\n\n".join(paragraphs)


def test_the_marker_counts_no_word_in_a_page() -> None:
    kept, _ = truncate([numbered(0, 25)], 10)
    assert paginate(kept, 5) == [numbered(0, 5) + f"\n\n{MARKER}", numbered(20, 25)]


def test_no_paragraph_gives_no_page() -> None:
    assert paginate([], 5) == []
