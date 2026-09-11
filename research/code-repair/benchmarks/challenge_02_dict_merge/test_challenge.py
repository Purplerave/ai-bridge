import pytest
from .solution import deep_merge


def test_deep_merge_flat():
    a = {"x": 1, "y": 2}
    b = {"y": 3, "z": 4}
    merged = deep_merge(a, b)
    assert merged == {"x": 1, "y": 3, "z": 4}


def test_deep_merge_nested():
    a = {"a": {"b": 1, "c": 2}}
    b = {"a": {"c": 3, "d": 4}}
    merged = deep_merge(a, b)
    assert merged == {"a": {"b": 1, "c": 3, "d": 4}}


def test_deep_merge_original_unmodified():
    a = {"a": {"b": 1}}
    b = {"a": {"b": 2}}
    deep_merge(a, b)
    assert a == {"a": {"b": 1}}
