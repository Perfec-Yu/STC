import pytest
import re


def _import_loads():
    """
    Flexible importer so the tests work without editing every file.
    Set env DSL_IMPORT to something like: "mypkg.loader:loads"
    Otherwise we default to from yourpkg import loads
    """
    from stc import loads
    return loads


@pytest.fixture(scope="session")
def loads_fn():
    return _import_loads()


@pytest.fixture()
def make_fence():
    """
    Wrap a raw string in a valid backtick fence:

    New rule:
      - fence_len = max(3, longest *line* made only of backticks + 1)
      - (Inline runs of backticks inside content do NOT matter.)
      - Empty string block must include a blank content line.
    """
    # Matches a line consisting ONLY of backticks (no spaces)
    backtick_line_re = re.compile(r"^`+$", re.M)

    def _mk(s: str, key: str = "a"):
        # Find the longest *line* that is only backticks
        longest_line = 0
        for m in backtick_line_re.finditer(s):
            longest_line = max(longest_line, len(m.group(0)))

        fence_len = max(3, longest_line + 1)
        ticks = "`" * fence_len

        return f"{key}: {ticks}\n{s}\n{ticks}"

    return _mk
