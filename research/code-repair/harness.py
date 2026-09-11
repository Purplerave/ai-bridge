"""
Harness para Benchmark Multi-IA de Reparación Secuencial de Código (Code Repair).

Este módulo gestiona la ejecución de desafíos de depuración y reparación de código,
registrando métricas estandarizadas de éxito, tasa de paso de tests unitarios,
y tiempo de ejecución por agente.
"""

import json
import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, List


class CodeRepairHarness:
    def __init__(self, benchmark_dir: str = None, results_dir: str = None):
        base_dir = Path(__file__).parent.resolve()
        self.benchmark_dir = Path(benchmark_dir) if benchmark_dir else base_dir / "benchmarks"
        self.results_dir = Path(results_dir) if results_dir else base_dir / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def list_benchmarks(self) -> List[str]:
        """Devuelve la lista de nombres de desafíos disponibles en benchmark_dir."""
        if not self.benchmark_dir.exists():
            return []
        benchmarks = []
        for p in self.benchmark_dir.iterdir():
            if p.is_dir() and (p / "test_challenge.py").exists():
                benchmarks.append(p.name)
        return sorted(benchmarks)

    def run_benchmark(self, benchmark_name: str, agent_name: str = "unknown") -> Dict[str, Any]:
        """
        Ejecuta el test de un desafío específico y registra el resultado.
        """
        target_path = self.benchmark_dir / benchmark_name / "test_challenge.py"
        if not target_path.exists():
            raise FileNotFoundError(f"No se encontró el desafío {benchmark_name} en {target_path}")

        start_time = time.time()
        cmd = [sys.executable, "-m", "pytest", str(target_path), "-v", "--tb=short"]

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        duration = time.time() - start_time

        success = (proc.returncode == 0)

        result_data = {
            "benchmark": benchmark_name,
            "agent": agent_name,
            "timestamp": time.time(),
            "passed": success,
            "duration_seconds": round(duration, 4),
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }

        # Guardar en JSON
        result_file = self.results_dir / f"{benchmark_name}_{agent_name}_{int(time.time())}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2)

        return result_data


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Code Repair Benchmark Harness")
    parser.add_argument("action", choices=["list", "run"], help="Acción a realizar")
    parser.add_argument("--benchmark", type=str, help="Nombre del desafío (para 'run')")
    parser.add_argument("--agent", type=str, default="jules", help="Nombre del agente/modelo")

    args = parser.parse_args()
    harness = CodeRepairHarness()

    if args.action == "list":
        benchmarks = harness.list_benchmarks()
        print(f"Desafíos disponibles ({len(benchmarks)}):")
        for b in benchmarks:
            print(f" - {b}")
    elif args.action == "run":
        if not args.benchmark:
            print("Error: debe especificar --benchmark para ejecutar.")
            sys.exit(1)
        res = harness.run_benchmark(args.benchmark, agent_name=args.agent)
        status = "PASÓ" if res["passed"] else "FALLÓ"
        print(f"Resultado para {args.benchmark} ({args.agent}): {status} en {res['duration_seconds']}s")
        sys.exit(0 if res["passed"] else 1)


if __name__ == "__main__":
    main()
