"""Truncation (spec 5.5) and pages (spec 5.6) of the cleaned paragraphs."""

from collections.abc import Sequence

MARKER = "[…]"
"""The paragraph put between the two kept parts of a truncated text; it is not a word."""


def words(text: str) -> list[str]:
    """The words of `text`: its whitespace-separated tokens, the `[…]` marker excluded.

    Cleaning removes every bracketed annotation, so the marker is never a word of the text.
    """
    return [word for word in text.split() if word != MARKER]


def _take(paragraphs: Sequence[list[str]], count: int) -> list[list[str]]:
    """The paragraphs of the first `count` words of `paragraphs`, the last one possibly cut."""
    kept: list[list[str]] = []
    for paragraph in paragraphs:
        if count <= 0:
            break
        kept.append(paragraph[:count])
        count -= len(kept[-1])
    return kept


def truncate(paragraphs: Sequence[str], max_words: int) -> tuple[list[str], bool]:
    """Keep the first and last `max_words // 2` words around a `[…]` paragraph when the text has
    more than `max_words` words, keeping the paragraph breaks inside both parts.

    Returns the paragraphs and whether the text was truncated.
    """
    split = [words(paragraph) for paragraph in paragraphs]
    if sum(map(len, split)) <= max_words:
        return list(paragraphs), False
    half = max_words // 2
    head = _take(split, half)
    tail = [paragraph[::-1] for paragraph in _take([p[::-1] for p in reversed(split)], half)]
    kept = [*head, [MARKER], *reversed(tail)]
    return [" ".join(paragraph) for paragraph in kept], True


def paginate(paragraphs: Sequence[str], page_words: int) -> list[str]:
    """Group whole paragraphs into pages of at most `page_words` words, joined by `\\n\\n`.

    A paragraph longer than `page_words` starts a new page and is cut into pieces of `page_words`
    words; its last piece is the current page that the next paragraphs may join. No page is empty.
    """
    pages: list[list[str]] = []
    count = 0
    for paragraph in paragraphs:
        tokens = paragraph.split()
        if not tokens:
            continue
        size = len(words(paragraph))
        if pages and count + size <= page_words:
            pages[-1].append(paragraph)
            count += size
        elif size <= page_words:
            pages.append([paragraph])
            count = size
        else:
            for start in range(0, size, page_words):
                pages.append([" ".join(tokens[start : start + page_words])])
            count = len(words(pages[-1][0]))
    return ["\n\n".join(page) for page in pages]
