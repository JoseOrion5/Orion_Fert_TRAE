from __future__ import annotations

import argparse
from pathlib import Path

import motor


def probe_excel() -> int:
    try:
        import pandas as pd
    except Exception:
        print("pandas não disponível neste ambiente.")
        return 2

    base_unica_file = Path("COMPLETAO/DATABASE_MESTRE_ORION.xlsx")
    if not base_unica_file.exists():
        print(f"File not found: {base_unica_file}")
        return 1

    df = pd.read_excel(base_unica_file, sheet_name="Insumos")
    print("Columns:", df.columns.tolist())
    print("\nSample (first 5 rows):")
    print(df.head(5))
    return 0


def regression_mg(*, volume_l: float, temp_c: float, use_optimization: bool) -> int:
    insumos = motor.load_insumos()
    aditivos = motor.load_aditivos()
    if not insumos:
        print("ERRO: load_insumos() retornou vazio.")
        return 2

    mg_tests = [1.0, 5.0, 10.0, 15.0]

    for mg in mg_tests:
        targets = {"Mg": float(mg)}

        outputs = motor.build_top12_outputs(
            float(volume_l),
            targets,
            insumos,
            aditivos,
            float(temp_c),
            use_optimization=bool(use_optimization),
        )

        best = next((o for o in outputs if (o.lines or [])), None)
        if not best:
            print(f"FAIL Mg={mg:.1f}%: nenhuma formulação encontrada")
            return 3

        totals = motor._totals_from_lines(best.lines)
        got = float(totals.get("Mg", 0.0) or 0.0)
        ok = got + 1e-6 >= float(mg)
        print(f"Mg alvo={mg:.1f}% | Mg obtido={got:.3f}% | ok={ok} | linhas={len(best.lines)}")
        if not ok:
            return 4

    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel", action="store_true")
    ap.add_argument("--volume", type=float, default=100.0)
    ap.add_argument("--temp", type=float, default=25.0)
    ap.add_argument("--opt", action="store_true")
    args = ap.parse_args()

    if args.excel:
        return probe_excel()

    return regression_mg(volume_l=args.volume, temp_c=args.temp, use_optimization=args.opt)


if __name__ == "__main__":
    raise SystemExit(main())
