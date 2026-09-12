#!/usr/bin/env python3
"""
Harness CLI para el Benchmark Multi-IA de Reparación Secuencial de Código.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BENCHMARKS_DIR = BASE_DIR / "benchmarks"
RESULTS_DIR = BASE_DIR / "results"
RESULTS_FILE = RESULTS_DIR / "results.json"


def ensure_dirs():
    BENCHMARKS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if not RESULTS_FILE.exists():
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump({"runs": []}, f, indent=2)


def load_results():
    ensure_dirs()
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"runs": []}


def save_results(data):
    ensure_dirs()
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def list_challenges():
    ensure_dirs()
    challenges = []
    if BENCHMARKS_DIR.exists():
        for item in sorted(BENCHMARKS_DIR.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                challenges.append(item.name)
    return challenges


def run_challenge(agent_name: str, challenge_id: str) -> dict:
    ensure_dirs()
    target_dir = BENCHMARKS_DIR / challenge_id
    if not target_dir.exists() or not target_dir.is_dir():
        raise ValueError(f"Desafío '{challenge_id}' no encontrado.")

    start_time = time.time()
    # Ejecutar pytest sobre el directorio del desafío
    cmd = [sys.executable, "-m", "pytest", str(target_dir)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - start_time

    success = res.returncode == 0
    run_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "agent": agent_name,
        "challenge": challenge_id,
        "success": success,
        "returncode": res.returncode,
        "duration_seconds": round(duration, 3),
        "stdout": res.stdout,
        "stderr": res.stderr,
    }

    results_data = load_results()
    results_data["runs"].append(run_entry)
    save_results(results_data)

    return run_entry


def main():
    parser = argparse.ArgumentParser(description="Test Harness para Benchmark de Code Repair")
    subparsers = parser.add_subparsers(dest="command")

    # Command: list
    subparsers.add_parser("list", help="Listar desafíos disponibles")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Ejecutar prueba de desafío")
    run_parser.add_argument("--agent", required=True, help="Nombre del agente IA (p.ej. jules, grok, arena)")
    run_parser.add_argument("--challenge", required=True, help="ID o nombre de la carpeta del desafío")

    # Command: status
    subparsers.add_parser("status", help="Mostrar resumen de resultados registrados")

    args = parser.parse_args()

    if args.command == "list":
        challs = list_challenges()
        print("Desafíos disponibles:")
        for c in challs:
            print(f" - {c}")
    elif args.command == "run":
        try:
            res = run_challenge(args.agent, args.challenge)
            status_str = "EXITO" if res["success"] else "FALLO"
            print(f"Prueba ejecutada para agente [{args.agent}] en [{args.challenge}]: {status_str} (tiempo: {res['duration_seconds']}s)")
            if not res["success"]:
                sys.exit(1)
        except Exception as e:
            print(f"Error al ejecutar el desafío: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "status":
        data = load_results()
        runs = data.get("runs", [])
        print(f"Total de ejecuciones registradas: {len(runs)}")
        for r in runs[-10:]:  # Ultimos 10
            st = "OK" if r["success"] else "FAIL"
            print(f"[{r['timestamp']}] Agente: {r['agent']} | Desafío: {r['challenge']} | Resultado: {st}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
