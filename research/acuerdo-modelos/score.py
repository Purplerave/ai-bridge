"""Puntuación mecánica del estudio acuerdo-modelos (pista code-review).

Solo stdlib, sin red, sin IA. Lee `rubric.json` + `respuestas/*.json` y calcula:

- acuerdo entre IAs (Jaccard por pares sobre hallazgos normalizados),
- recall por IA contra la rúbrica (global y por clase),
- hallazgos sin rúbrica (para adjudicación humana, no penalizan).

Un hallazgo acredita un defecto si es del mismo item e intersecta en ≥1 línea.
Un defecto cuenta una vez por IA aunque varios hallazgos lo toquen.

Uso:
    python research/acuerdo-modelos/score.py [--json] [--check] [--exclude IA ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_response(data: dict, rubric: dict) -> list[str]:
    """Devuelve la lista de errores (vacía = válida). Espejo manual de schema.json."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["la respuesta debe ser un objeto JSON"]
    for field in ("ia", "date", "track", "findings"):
        if field not in data:
            errors.append(f"falta el campo obligatorio: {field}")
    if errors:
        return errors
    if not isinstance(data["ia"], str) or not data["ia"].strip():
        errors.append("`ia` debe ser texto no vacío")
    if data.get("track") != "code-review":
        errors.append(f"`track` debe ser 'code-review' (vino {data.get('track')!r})")
    try:
        datetime.fromisoformat(str(data["date"]))
    except ValueError:
        errors.append(f"`date` no es ISO 8601: {data.get('date')!r}")
    findings = data.get("findings")
    if not isinstance(findings, list) or not findings:
        return errors + ["`findings` debe ser una lista no vacía"]
    items = set(rubric.get("items", []))
    classes = set(rubric.get("classes", []))
    seen: set[tuple] = set()
    for i, f in enumerate(findings):
        where = f"findings[{i}]"
        if not isinstance(f, dict):
            errors.append(f"{where}: debe ser un objeto")
            continue
        for field in ("item", "lines", "class", "note"):
            if field not in f:
                errors.append(f"{where}: falta `{field}`")
        if f.get("item") not in items:
            errors.append(f"{where}: item desconocido: {f.get('item')!r}")
        lines = f.get("lines")
        if (
            not isinstance(lines, list)
            or not lines
            or any(not isinstance(n, int) or isinstance(n, bool) or n < 1 for n in lines)
        ):
            errors.append(f"{where}: `lines` debe ser lista no vacía de enteros ≥ 1")
        if f.get("class") not in classes:
            errors.append(f"{where}: clase desconocida: {f.get('class')!r}")
        note = f.get("note")
        if not isinstance(note, str) or len(note.strip()) < 10:
            errors.append(f"{where}: `note` debe explicar el defecto (≥10 caracteres)")
        key = (f.get("item"), tuple(sorted(lines)) if isinstance(lines, list) else None)
        if key in seen:
            errors.append(f"{where}: hallazgo duplicado en {key[0]} líneas {list(key[1] or [])}")
        seen.add(key)
    return errors


def norm_key(finding: dict) -> tuple:
    return (finding["item"], tuple(sorted(finding["lines"])), finding["class"])


def matched_defects(findings: list[dict], rubric: dict) -> tuple[set[str], list[dict]]:
    """(ids de defectos acreditados, hallazgos sin rúbrica)."""
    matched: set[str] = set()
    unmatched: list[dict] = []
    for f in findings:
        flines = set(f["lines"])
        hit = False
        for d in rubric["defects"]:
            if d["item"] == f["item"] and flines & set(d["lines"]):
                matched.add(d["id"])
                hit = True
        if not hit:
            unmatched.append(f)
    return matched, unmatched


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def compute(rubric: dict, responses: list[dict]) -> dict:
    """Todo el cómputo, puro y testeable. `responses` ya validadas."""
    by_ia: dict[str, dict] = {}
    for r in responses:
        matched, unmatched = matched_defects(r["findings"], rubric)
        keys = {norm_key(f) for f in r["findings"]}
        by_ia[r["ia"]] = {"matched": matched, "unmatched": unmatched, "keys": keys,
                          "n": len(r["findings"]), "piloto": bool(r.get("piloto"))}
    total = len(rubric["defects"])
    per_class_total: dict[str, int] = {}
    for d in rubric["defects"]:
        per_class_total[d["class"]] = per_class_total.get(d["class"], 0) + 1
    ias = sorted(by_ia)
    per_ia = {}
    for ia in ias:
        info = by_ia[ia]
        per_class_hit: dict[str, int] = {}
        for did in info["matched"]:
            cls = next(d["class"] for d in rubric["defects"] if d["id"] == did)
            per_class_hit[cls] = per_class_hit.get(cls, 0) + 1
        per_ia[ia] = {
            "hallazgos": info["n"],
            "defectos_acreditados": sorted(info["matched"]),
            "recall": round(len(info["matched"]) / total, 3) if total else 0.0,
            "recall_por_clase": {
                c: round(per_class_hit.get(c, 0) / per_class_total[c], 3)
                for c in sorted(per_class_total)
            },
            "sin_rubrica": len(info["unmatched"]),
            "piloto": info["piloto"],
        }
    pairs = [
        {"a": a, "b": b, "jaccard": round(jaccard(by_ia[a]["keys"], by_ia[b]["keys"]), 3)}
        for a, b in combinations(ias, 2)
    ]
    return {
        "n_respondentes": len(ias),
        "n_defectos_rubrica": total,
        "por_ia": per_ia,
        "acuerdo_pares": pairs,
        "jaccard_medio": round(sum(p["jaccard"] for p in pairs) / len(pairs), 3) if pairs else None,
    }


def report_text(result: dict, responses: list[dict]) -> str:
    lines = [
        f"acuerdo-modelos · pista code-review · n={result['n_respondentes']} "
        f"· defectos en rúbrica: {result['n_defectos_rubrica']}",
        "",
        "Recall contra rúbrica (métrica secundaria):",
    ]
    for ia, p in result["por_ia"].items():
        tag = " [PILOTO]" if p["piloto"] else ""
        lines.append(
            f"  {ia}{tag}: recall {p['recall']:.0%} "
            f"({len(p['defectos_acreditados'])}/{result['n_defectos_rubrica']}) · "
            f"hallazgos {p['hallazgos']} · sin rúbrica {p['sin_rubrica']}"
        )
        lines.append("    por clase: " + ", ".join(
            f"{c} {v:.0%}" for c, v in p["recall_por_clase"].items()))
    lines.append("")
    lines.append("Acuerdo entre IAs, Jaccard por pares (métrica principal):")
    if result["acuerdo_pares"]:
        for pr in result["acuerdo_pares"]:
            lines.append(f"  {pr['a']} ↔ {pr['b']}: {pr['jaccard']:.2f}")
        lines.append(f"  medio: {result['jaccard_medio']:.2f}")
    else:
        lines.append("  (se necesita n≥2; con una sola respuesta no hay pares)")
    pilot = [r["ia"] for r in responses if r.get("piloto")]
    if pilot:
        lines.append("")
        lines.append(f"Nota: {', '.join(pilot)} es/son piloto (validan el tubo; "
                     "excluir del cómputo definitivo con --exclude).")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="score.py", description=__doc__)
    parser.add_argument("--json", action="store_true", help="volcado máquina en JSON")
    parser.add_argument("--check", action="store_true", help="solo validar respuestas")
    parser.add_argument("--exclude", nargs="*", default=[], help="IAs a excluir del cómputo")
    args = parser.parse_args(argv)

    rubric = load_json(HERE / "rubric.json")
    files = sorted((HERE / "respuestas").glob("*.json"))
    responses: list[dict] = []
    failures = 0
    for path in files:
        try:
            data = load_json(path)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"ERROR {path.name}: JSON inválido ({exc})")
            failures += 1
            continue
        errs = validate_response(data, rubric)
        if errs:
            print(f"ERROR {path.name}:")
            for e in errs:
                print(f"  - {e}")
            failures += 1
            continue
        if data["ia"] in args.exclude:
            continue
        responses.append(data)
    if failures:
        return 1
    if args.check:
        print(f"OK: {len(files)} respuesta(s) válida(s)"
              + (f" ({len(responses)} tras --exclude)" if args.exclude else ""))
        return 0
    if not responses:
        print("sin respuestas que puntuar (¿todo excluido?)")
        return 0
    result = compute(rubric, responses)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(report_text(result, responses))
    return 0


if __name__ == "__main__":
    sys.exit(main())
