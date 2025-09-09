import pytest

pytestmark = pytest.mark.dicts

def test_empty_dict(loads_fn):
    doc = "a: {}"
    assert loads_fn(doc) == {"a": {}}

def test_multi_item_dict_scalars(loads_fn):
    doc = "\n".join([
        "a.b: 1",
        "a.c: 2.5",
        "a.d: `true`",
    ])
    assert loads_fn(doc) == {"a": {"b": 1, "c": 2.5, "d": True}}

def test_dict_items_may_be_scattered(loads_fn):
    doc = "\n".join([
        "a.c: 3",
        "a.a: 1",
        "a.b: 2",
    ])
    assert loads_fn(doc) == {"a": {"a": 1, "b": 2, "c": 3}}

def test_dict_value_can_be_string(loads_fn):
    doc = "meta.note: ```\nhello\n```"
    assert loads_fn(doc) == {"meta": {"note": "hello"}}

def test_dict_list_nested(loads_fn):
    doc = "\n".join([
        "a.b: 1",
        "a.c.$0: 2",
        "a.c.$1.d: 3.5",
        "a.c.$1.e: `true`"
    ])
    assert loads_fn(doc) == {"a": {"b": 1, "c": [2, {"d": 3.5, "e": True}]}}

@pytest.mark.errors
def test_duplicate_leaf_path_is_invalid(loads_fn):
    doc = "a.b: 1\na.b: 2"
    with pytest.raises(Exception):
        loads_fn(doc)
