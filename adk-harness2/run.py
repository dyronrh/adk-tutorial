"""Ejecuta Harness² sobre TU agente ADK (mi_agente/) y exporta el agente mejorado.

  mi_agente/agent.py -> import_agent -> harness base -> Harness² -> export_agent -> agents/agente_mejorado/

  python run.py --offline            # sin credenciales: modelo y editor guionados
  python run.py --k 3 --mode parallel  # real: agente ADK con Gemini + editor LLM de Harness²

Modo real: el agente usa GEMINI_MODEL (p. ej. gemini-2.5-flash) vía ADK, y el editor de
Harness² usa HARNESS2_IMPROVER_MODEL a través del CLI de OpenCode (ver docs/SETUP.md del repo).
"""

from __future__ import annotations

import cargar_env  # noqa: F401  (.env del proyecto: GOOGLE_API_KEY, ...)
import argparse
import json
import os
from pathlib import Path

from harness2.core.proposer import Proposer
from harness2.core.schedule import mode_token, run_domain
from harness2.core.spec import ChannelSpec

from adk_adapter import AdkAdapter


def main() -> None:
    import logging
    logging.getLogger("google_adk").setLevel(logging.ERROR)
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=None,
                    help="por defecto runs/adk_offline o runs/adk_real (si existe, Harness² reanuda)")
    ap.add_argument("--k", type=int, default=1, help="presupuesto de recursión por tarea")
    ap.add_argument("--mode", choices=("parallel", "sequential", "both"), default="both")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    root = (args.output or Path("runs/adk_offline" if args.offline else "runs/adk_real")).resolve()

    if args.offline:
        from offline import OfflineEditor, ScriptedLlm

        channel = ChannelSpec("opencode", "local/deterministic")
        adapter = AdkAdapter(root, model=ScriptedLlm(), improver=channel)
        editor = OfflineEditor(channel)
    else:
        channel = ChannelSpec("opencode", os.environ["HARNESS2_IMPROVER_MODEL"])
        adapter = AdkAdapter(root, model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                             improver=channel)
        editor = Proposer(channel, audit_dir=root / "audit")
        from harness2.core.proposer import _opencode_dir
        _opencode_dir()  # falla ya si falta el checkout de OpenCode (si no, todo cae a la base)

    modes = ("agg", "seq") if args.mode == "both" else (mode_token(args.mode),)
    result = run_domain(
        "contabilidad", adapter.tasks(), args.k,
        adapter=adapter, prop=editor,
        runs_root=adapter.spec.runs_root,
        library_root=root / "library" / f"k{args.k}",
        modes=modes,
    )
    result["ejecuciones_adk"] = adapter.execution_count
    (root / "result.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    # Evidencia: agente ADK base vs. el adoptado en la última tarea, y el reporte por candidato.
    from export_agent import export
    from report import main as report

    agents = Path("agents") if not args.offline else Path("agents/offline")
    adopted = sorted((root / "library").glob(f"k{args.k}/*/contabilidad/harnesses/*/harness"),
                     key=lambda p: p.stat().st_mtime)
    if adopted:
        export(adopted[-1], agents / "agente_mejorado")
    failed = [f.name.split(".")[0] for f in sorted((root / "audit").glob("*.meta.json"))
              if not json.loads(f.read_text()).get("ok", True)]
    if failed:
        print(f"⚠️  {len(failed)} sesiones del editor FALLARON ({', '.join(failed)}): esos "
              f"candidatos son copias de la base. Detalle en {root / 'audit'}/*.meta.json")
    print(f"Evidencia: {report(root)}  |  agentes ADK: {agents.resolve()}")
    print(f"{result['done']} tareas ok, {result['failed']} fallidas, "
          f"{adapter.execution_count} ejecuciones del agente ADK -> {root}")


if __name__ == "__main__":
    main()
