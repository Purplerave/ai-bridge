import json
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from harness import CodeRepairHarness


def test_list_benchmarks(tmp_path):
    bench_dir = tmp_path / "benchmarks"
    bench_dir.mkdir()
    c1 = bench_dir / "challenge_01"
    c1.mkdir()
    (c1 / "test_challenge.py").write_text("def test_dummy(): pass")

    harness = CodeRepairHarness(benchmark_dir=str(bench_dir), results_dir=str(tmp_path / "results"))
    b_list = harness.list_benchmarks()
    assert b_list == ["challenge_01"]


def test_run_benchmark_success(tmp_path):
    bench_dir = tmp_path / "benchmarks"
    bench_dir.mkdir()
    c1 = bench_dir / "challenge_01"
    c1.mkdir()
    (c1 / "test_challenge.py").write_text("def test_pass(): assert True")

    results_dir = tmp_path / "results"
    harness = CodeRepairHarness(benchmark_dir=str(bench_dir), results_dir=str(results_dir))

    res = harness.run_benchmark("challenge_01", agent_name="test_agent")
    assert res["passed"] is True
    assert res["agent"] == "test_agent"
    assert res["benchmark"] == "challenge_01"

    json_files = list(results_dir.glob("*.json"))
    assert len(json_files) == 1
    with open(json_files[0], "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["passed"] is True


def test_run_benchmark_failure(tmp_path):
    bench_dir = tmp_path / "benchmarks"
    bench_dir.mkdir()
    c1 = bench_dir / "challenge_failing"
    c1.mkdir()
    (c1 / "test_challenge.py").write_text("def test_fail(): assert False")

    results_dir = tmp_path / "results"
    harness = CodeRepairHarness(benchmark_dir=str(bench_dir), results_dir=str(results_dir))

    res = harness.run_benchmark("challenge_failing", agent_name="test_agent")
    assert res["passed"] is False
