"""Tool ADK `resumir_extracto` importada de mi_agente."""
import csv
import os
from decimal import Decimal
from pathlib import Path


def resumir_extracto(ruta_csv: str, clp_por_usd: float) -> dict:
    """Calcula el total neto en USD y cuenta la cantidad de abonos en el extracto.

    Args:
      ruta_csv: ruta al CSV del extracto (columnas date, description, amount, currency).
      clp_por_usd: pesos chilenos por dólar.
    """
    with open(ruta_csv) as f:
        filas = list(csv.DictReader(f))
    tasa = Decimal(str(clp_por_usd))
    total = sum(
        (Decimal(r["amount"]) / (tasa if r["currency"] == "CLP" else 1)
         for r in filas),
        Decimal(0),
    )
    abonos = sum(1 for r in filas if Decimal(r["amount"]) < 0)
    return {"total_usd": f"{total:.2f}", "abonos": abonos}


if __name__ == "__main__":  # CLI del harness: python3 scripts/resumir_extracto.py '{"arg": "valor"}'
    import json, sys
    out = resumir_extracto(**json.loads(sys.argv[1] if len(sys.argv) > 1 else "{}"))
    print(json.dumps(out, ensure_ascii=False, default=str))
