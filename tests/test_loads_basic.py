import pytest

pytestmark = pytest.mark.basic

def test_empty(loads_fn):
    doc = "{}"
    assert loads_fn(doc) == {}

def test_int_scalar(loads_fn):
    doc = "a: 10"
    assert loads_fn(doc) == {"a": 10}

def test_float_scalar(loads_fn):
    doc = "a: 10.3"
    assert loads_fn(doc) == {"a": 10.3}

def test_bool_true(loads_fn):
    # bool must be wrapped in backticks
    doc = "a: `true`"
    assert loads_fn(doc) == {"a": True}

def test_bool_false(loads_fn):
    doc = "a: `false`"
    assert loads_fn(doc) == {"a": False}

@pytest.mark.errors
def test_bool_without_backticks_is_invalid(loads_fn):
    doc = "a: true"
    with pytest.raises(Exception):
        loads_fn(doc)

@pytest.mark.strings
def test_minimal_empty_string_block(loads_fn, make_fence):
    doc = make_fence("", key="a")
    assert loads_fn(doc) == {"a": ""}

@pytest.mark.strings
def test_simple_string_block(loads_fn, make_fence):
    doc = make_fence("hello\nworld", key="a")
    assert loads_fn(doc) == {"a": "hello\nworld"}

@pytest.mark.strings
def test_string_preserves_symbols_and_newlines(loads_fn, make_fence):
    raw = "Multi-line with <tags> & symbols.\n\nTrailing newline? Yes.\n"
    doc = make_fence(raw, key="note")
    assert loads_fn(doc) == {"note": raw}
