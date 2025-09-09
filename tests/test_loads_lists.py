import pytest

pytestmark = pytest.mark.lists

def test_empty_list(loads_fn):
    doc = "a: []"
    assert loads_fn(doc) == {"a": []}

def test_multi_item_list_numbers_and_bools(loads_fn):
    doc = "\n".join([
        "a.$0: 1",
        "a.$1: 2",
        "a.$2: `true`",
        "a.$3: 3.14",
    ])
    assert loads_fn(doc) == {"a": [1, 2, True, 3.14]}

def test_list_items_can_be_scattered_out_of_order(loads_fn):
    # Order in the source doesn't matter; indices define positions
    doc = "\n".join([
        "a.$2: `false`",
        "a.$0: 10",
        "a.$1: 20",
    ])
    assert loads_fn(doc) == {"a": [10, 20, False]}

def test_list_item_can_be_string_block(loads_fn):
    doc = "a.$0: ```\nhello\n```"
    assert loads_fn(doc) == {"a": ["hello"]}

@pytest.mark.errors
def test_list_index_must_be_non_negative_integer(loads_fn):
    for bad in ["a.$-1: 1", "a.$x: 1", "a.$1.2: 1"]:
        with pytest.raises(Exception):
            loads_fn(bad)

@pytest.mark.errors
def test_list_gaps_or_duplicates_should_error(loads_fn):
    # Behavior not specified; this test enforces no gaps/dupes
    with pytest.raises(Exception):
        loads_fn("a.$1: 1")  # gap at $0
    with pytest.raises(Exception):
        loads_fn("a.$0: 1\na.$0: 2")  # duplicate index
