import sys
from pathlib import Path

CHALLENGE_DIR = Path(__file__).resolve().parent
if str(CHALLENGE_DIR) not in sys.path:
    sys.path.insert(0, str(CHALLENGE_DIR))

import pytest
from lru_cache import LRUCache  # noqa: E402


def test_lru_operations():
    cache = LRUCache(2)
    cache.put(1, 1)
    cache.put(2, 2)
    assert cache.get(1) == 1
    cache.put(3, 3)  # evicts key 2
    assert cache.get(2) == -1
    assert cache.get(3) == 3


def test_invalid_capacity():
    with pytest.raises(ValueError):
        LRUCache(0)
