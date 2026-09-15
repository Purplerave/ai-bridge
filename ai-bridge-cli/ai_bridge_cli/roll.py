"""`ai-bridge-cli roll` — bitácora de tiradas de la partida de rol.

Cada tirada se registra en un ledger JSON con fecha ISO y la IA que la hizo:

    ai-bridge-cli roll --ia grok --resultado 12 --dados 1d20 --motivo "Persuasion"
    ai-bridge-cli roll --ia kilo --dados 4d6            # tira el script (RNG)

Sin ``--resultado`` el propio script tira: así el master no puede inventarse
el número y la suerte queda a la vista. Con ``--list`` se ve el historial.
"""

from __future__ import annotations

import json
import os
import random
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

DICE_RE = re.compile(r"^(\d+)d(\d+)(?:l(\d*))?$")

ALLOWED_IAS = {"grok", "jules", "kilo", "arena", "openclaw", "muse-spark", "muse", "tecnotron"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _default_ledger() -> Path:
    return _repo_root() / "state" / "rolls-ledger.json"


def _load(ledger: Path) -> list[dict]:
    if not ledger.exists():
        return []
    try:
        data = json.loads(ledger.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _save(ledger: Path, rows: list[dict]) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    tmp = ledger.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(ledger)


def _roll(dados: str) -> int:
    """Interpreta 'NdM' y devuelve la suma. Usa secrets (RNG no predecible).

    Con el sufijo 'l' (p. ej. ``4d6l``) se descarta el resultado más bajo,
    la regla de D&D para características: 4d6 y te quedas con los 3 mejores
    (máximo 18).
    """
    m = DICE_RE.match(dados.strip().lower())
    if not m:
        raise ValueError(f"dados inválido (esperaba NdM o NdMl, p. ej. 1d20 o 4d6l): {dados!r}")
    n, faces = int(m.group(1)), int(m.group(2))
    has_l = "l" in m.group(0)
    drop = int(m.group(3)) if has_l and m.group(3) else (1 if has_l else 0)
    if n < 1 or faces < 1 or drop < 0 or drop >= n:
        raise ValueError(f"dados inválido: {dados!r}")
    tiros = sorted(secrets.randbelow(faces) + 1 for _ in range(n))
    if drop:
        tiros = tiros[drop:]
    return sum(tiros)


def run_roll(
    *,
    ia: str,
    resultado: int | None = None,
    dados: str = "1d20",
    motivo: str | None = None,
    ledger: Path | None = None,
    roll_default: bool = True,
) -> int:
    ledger = ledger or _default_ledger()
    nombre = (ia or "").strip().lower()
    if not nombre:
        print("error: falta la IA que tira (--ia grok, kilo, arena...)", file=sys.stderr)
        return 2
    if nombre not in ALLOWED_IAS:
        print(f"error: IA no reconocida: {nombre!r} (esperadas: {', '.join(sorted(ALLOWED_IAS))})", file=sys.stderr)
        return 2

    DICE_RE.match(dados.strip().lower())

    if resultado is None:
        try:
            resultado = _roll(dados)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        origen = "tirada_script"
    else:
        origen = "declarada"

    fila = {
        "date": datetime.now(timezone.utc).isoformat(),
        "ia": nombre,
        "dados": dados.strip().lower() or "1d20",
        "resultado": int(resultado),
        "origen": origen,
        "motivo": (motivo or "").strip() or None,
    }

    rows = _load(ledger)
    rows.append(fila)
    _save(ledger, rows)

    if origen == "declarada":
        print(f"tirada registrada: {nombre} {fila['dados']} = {resultado} (declarada)")
    else:
        print(f"tirada: {nombre} {fila['dados']} = {resultado}")
    print(f"  ledger: {ledger}" if roll_default else f"  ledger: {ledger}")
    return 0


def run_list(ledger: Path | None = None) -> int:
    ledger = ledger or _default_ledger()
    rows = _load(ledger)
    if not rows:
        print("ledger de tiradas vacío (state/rolls-ledger.json)", file=sys.stderr)
        return 1
    for fila in rows:
        extra = f" | {fila['motivo']}" if fila.get("motivo") else ""
        print(f"{fila['date']}  {fila['ia']:<12} {fila['dados']:<8} -> {fila['resultado']:<4} ({fila['origen']}){extra}")
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="ai-bridge-cli roll", description="Bitácora de tiradas de rol")
    sub = parser.add_subparsers(dest="command", required=True)

    p_tira = sub.add_parser("tira", help="Registrar una tirada")
    p_tira.add_argument("--ia", required=True, help="qué IA tira")
    p_tira.add_argument("--resultado", type=int, default=None, help="resultado (si no, lo tira el script)")
    p_tira.add_argument("--dados", default="1d20", help="qué dados, p. ej. 1d20, 4d6")
    p_tira.add_argument("--motivo", default=None, help="para qué, p. ej. Persuasión")
    p_tira.add_argument("--ledger", default=None, help="ruta alternativa del ledger")

    p_lista = sub.add_parser("list", help="Ver el historial de tiradas")
    p_lista.add_argument("--ledger", default=None, help="ruta alternativa del ledger")

    args = parser.parse_args(argv)

    if args.command == "tira":
        return run_roll(ia=args.ia, resultado=args.resultado, dados=args.dados,
                        motivo=args.motivo, ledger=Path(args.ledger) if args.ledger else None)
    if args.command == "list":
        return run_list(Path(args.ledger) if args.ledger else None)
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())