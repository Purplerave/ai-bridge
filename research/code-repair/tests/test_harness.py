import sys
from pathlib import Path

CODE_REPAIR_DIR = Path(__file__).resolve().parent.parent
if str(CODE_REPAIR_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_REPAIR_DIR))

from harness import list_challenges, run_challenge, load_results  # noqa: E402


def test_list_challenges():
    challenges = list_challenges()
    assert "challenge_01_buggy_calculator" in challenges
    assert "challenge_02_json_parser" in challenges
    assert "challenge_03_lru_cache" in challenges


def test_run_challenge():
    res = run_challenge("jules", "challenge_01_buggy_calculator")
    assert res["agent"] == "jules"
    assert res["challenge"] == "challenge_01_buggy_calculator"
    assert res["success"] is True

    results_data = load_results()
    assert len(results_data["runs"]) > 0
    last_run = results_data["runs"][-1]
    assert last_run["agent"] == "jules"
