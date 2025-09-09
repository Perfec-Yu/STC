import pytest

pytestmark = pytest.mark.errors

def test_single_line_string_is_invalid(loads_fn):
    doc = "a: hello"
    with pytest.raises(Exception):
        loads_fn(doc)

def test_number_with_backticks_is_invalid(loads_fn):
    doc = "a: `123`"
    with pytest.raises(Exception):
        loads_fn(doc)

def test_bool_wrong_spelling_is_invalid(loads_fn):
    doc = "a: `True`"  # spec requires lower-case true/false in backticks
    with pytest.raises(Exception):
        loads_fn(doc)

def test_malformed_key_path_is_invalid(loads_fn):
    for d in [
        "a..b: 1",     # empty segment
        "a.$: 1",      # missing index
        "a.$1b: 1",    # junk after index
        ".a: 1",       # leading dot
        "a.: 1",       # trailing dot before colon
    ]:
        with pytest.raises(Exception):
            loads_fn(d)
