"""Valida ANTES vs DESPUÉS: corre mi_agente y el agente mejorado con el mismo modelo, sobre
las tareas que Harness² usó para mejorar y sobre tareas NUEVAS que nunca vio (holdout).

  python validar.py                          # Gemini real (GEMINI_MODEL), 3 repeticiones
  python validar.py --repeticiones 5
  python validar.py --despues agents/offline/agente_mejorado --offline   # prueba de humo

Cada ejecución se compara con `reference_answer` (que Harness² nunca vio). Las repeticiones
importan porque un LLM no es determinista: lo que vale es la tasa de acierto, no una corrida.
Escribe el detalle en runs/validacion.md.
"""

from __future__ import annotations

import cargar_env  # noqa: F401  (.env del proyecto: GOOGLE_API_KEY, ...)
import argparse
import asyncio
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

from adk_adapter import TASKS, AdkAdapter, reference_answer

_HDR = "date,description,amount,currency\n"
# Tareas que Harness² NO vio: otro tipo de cambio, sin abonos, solo USD, muchos abonos.
HOLDOUT = {
    "holdout-mayo-fx910": {
        "ledger.csv": _HDR + "2026-05-02,Hotel Lima,455000,CLP\n2026-05-06,Reembolso,-91000,CLP\n"
                             "2026-05-10,Taxi,12.40,USD\n",
        "fx.txt": "CLP_PER_USD=910\n",
    },
    "holdout-junio-sin-abonos": {
        "ledger.csv": _HDR + "2026-06-01,Cena,38000,CLP\n2026-06-15,Software,99.99,USD\n",
        "fx.txt": "CLP_PER_USD=950\n",
    },
    "holdout-julio-solo-usd": {
        "ledger.csv": _HDR + "2026-07-03,Vuelo,410.00,USD\n2026-07-09,Abono,-60.00,USD\n"
                             "2026-07-20,Hotel,220.50,USD\n2026-07-28,Nota de credito,-20.50,USD\n",
        "fx.txt": "CLP_PER_USD=950\n",
    },
}

# Un solo event loop: los clientes HTTP de genai sobreviven entre ejecuciones.
_LOOP = asyncio.new_event_loop()


def load_agent(pkg_dir: Path):
    """Importa <pkg_dir>/agent.py como paquete (soporta imports relativos de tools/)."""
    pkg_dir = pkg_dir.resolve()
    name = f"_val_{pkg_dir.name}"
    spec = importlib.util.spec_from_file_location(name, pkg_dir / "__init__.py",
                                                  submodule_search_locations=[str(pkg_dir)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod.agent.root_agent


def run_once(agent, files: dict[str, str], prompt: str) -> str:
    ws = Path(tempfile.mkdtemp(prefix="val_"))
    for n, t in files.items():
        (ws / n).write_text(t, encoding="utf-8")
    cwd = os.getcwd()
    os.chdir(ws)  # las tools abren rutas relativas, como en producción
    try:
        return _LOOP.run_until_complete(AdkAdapter._run(agent, prompt)).strip()
    except Exception as exc:  # noqa: BLE001 - una ejecución fallida cuenta como fallo
        return f"(error: {exc})"
    finally:
        os.chdir(cwd)
        shutil.rmtree(ws, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--antes", type=Path, default=Path("mi_agente"))
    ap.add_argument("--despues", type=Path, default=Path("agents/agente_mejorado"))
    ap.add_argument("--repeticiones", type=int, default=3)
    ap.add_argument("--offline", action="store_true", help="ScriptedLlm en vez de Gemini")
    args = ap.parse_args()

    agents = {"ANTES": load_agent(args.antes), "DESPUÉS": load_agent(args.despues)}
    if args.offline:
        from offline import ScriptedLlm
        for a in agents.values():
            a.model = ScriptedLlm()
    prompt = AdkAdapter.task_prompt(None, "")
    tasks = {**{f"vista-{k}": v for k, v in TASKS.items()}, **HOLDOUT}

    rows, detail = [], []
    for tid, files in tasks.items():
        with tempfile.TemporaryDirectory() as d:
            for n, t in files.items():
                (Path(d) / n).write_text(t, encoding="utf-8")
            ref = reference_answer(Path(d))
        hits = {}
        for label, agent in agents.items():
            outs = [run_once(agent, files, prompt) for _ in range(args.repeticiones)]
            hits[label] = sum(o == ref for o in outs)
            detail += [f"### {tid} · {label}", "", "```", f"esperado: {ref!r}",
                       *[f"run {i + 1}: {o!r} {'✅' if o == ref else '❌'}" for i, o in enumerate(outs)],
                       "```", ""]
        rows.append((tid, hits["ANTES"], hits["DESPUÉS"]))
        print(f"{tid:28} ANTES {hits['ANTES']}/{args.repeticiones}   "
              f"DESPUÉS {hits['DESPUÉS']}/{args.repeticiones}", flush=True)

    n = args.repeticiones
    total = lambda i, pre: sum(r[i] for r in rows if r[0].startswith(pre))
    summary = [
        "# Validación antes / después", "",
        f"Modelo: `{'scripted-offline' if args.offline else os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')}`"
        f" · {n} repeticiones por tarea · antes=`{args.antes}` · después=`{args.despues}`", "",
        "| Tarea | Antes | Después |", "|---|---|---|",
        *[f"| {t} | {a}/{n} | {b}/{n} |" for t, a, b in rows], "",
        f"- Tareas vistas por Harness²: antes {total(1, 'vista')} → después {total(2, 'vista')} "
        f"de {n * len(TASKS)}",
        f"- Tareas nuevas (holdout):   antes {total(1, 'holdout')} → después {total(2, 'holdout')} "
        f"de {n * len(HOLDOUT)}", "",
        "Si mejora en las vistas pero no en el holdout, el harness se sobreajustó a esas tareas.", "",
    ]
    out = Path("runs/validacion.md")
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(summary + ["## Detalle", ""] + detail), encoding="utf-8")
    print("\n".join(summary[-5:-2]))
    print(f"Detalle: {out.resolve()}")


if __name__ == "__main__":
    main()
