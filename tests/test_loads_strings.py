import re
import pytest

pytestmark = pytest.mark.strings

def _max_backtick_only_line(s: str) -> int:
    """Return the max length of any line that consists solely of backticks."""
    longest = 0
    for line in s.splitlines():
        if re.fullmatch(r"`+", line):
            longest = max(longest, len(line))
    return longest

def test_fence_must_exceed_backtick_only_lines(loads_fn):
    # There is a line that's exactly four backticks.
    content = "alpha\n````\nbeta"
    assert _max_backtick_only_line(content) == 4

    # Using a fence of 4 (equal) is invalid per the new rule (must be strictly longer).
    bad_fence = "`" * 4
    doc_bad = f"a: {bad_fence}\n{content}\n{bad_fence}"
    with pytest.raises(Exception):
        loads_fn(doc_bad)

    # Using a fence of 5 is valid.
    good_fence = "`" * 5
    doc_good = f"a: {good_fence}\n{content}\n{good_fence}"
    assert loads_fn(doc_good) == {"a": content}

def test_inline_backticks_do_not_force_longer_fence(loads_fn):
    # Inline runs of backticks are fine as long as there's no *line* that's only backticks.
    content = "abc ```` def ``` ghi"  # inline runs only
    assert _max_backtick_only_line(content) == 0

    # A minimal fence of 3 is acceptable here.
    fence = "```"
    doc = f"a: {fence}\n{content}\n{fence}"
    assert loads_fn(doc) == {"a": content}

def test_min_fence_is_3_even_without_backtick_only_lines(loads_fn):
    content = "plain text\nwith stuff"
    # Using 2 backticks is invalid per spec (minimum is 3).
    bad = "``"
    doc = f"a: {bad}\n{content}\n{bad}"
    with pytest.raises(Exception):
        loads_fn(doc)

def test_empty_string_requires_blank_line_between_fences(loads_fn):
    # "key: ```\n\n```" is required; "key: ```\n```" is invalid
    doc = "a: ```\n```"
    with pytest.raises(Exception):
        loads_fn(doc)