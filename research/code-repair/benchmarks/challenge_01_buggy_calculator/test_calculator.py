import sys
from pathlib import Path

CHALLENGE_DIR = Path(__file__).resolve().parent
if str(CHALLENGE_DIR) not in sys.path:
    sys.path.insert(0, str(CHALLENGE_DIR))

import pytest
from calculator import add, subtract, multiply, divide, power  # noqa: E402


def test_basic_ops():
    assert add(2, 3) == 5
    assert subtract(10, 4) == 6
    assert multiply(3, 7) == 21
    assert divide(10, 2) == 5.0
    assert power(2, 3) == 8


def test_divide_by_zero():
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(5, 0)
