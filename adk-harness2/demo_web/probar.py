"""Prepara las tareas de la demo en adk web y comprueba que las escenas del video se reproducen.

  python demo_web/probar.py            # prepara demo_web/ y corre antes/después con Gemini
  python demo_web/probar.py --solo-preparar

Copia los 2 agentes a demo_web/agentes/ y escribe cada tarea (ledger.csv + fx.txt) desde las
mismas fuentes que validar.py. Para cada
agente imprime lo que se verá en la traza de adk web: las tools que llama, con qué argumentos,
y la respuesta final comparada con la correcta.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import cargar_env  # noqa: E402,F401  (.env del proyecto: GOOGLE_API_KEY, ...)
from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from adk_adapter import TASKS, AdkAdapter, reference_answer  # noqa: E402
from validar import HOLDOUT, load_agent  # noqa: E402

DEMO = Path(__file__).resolve().parent
ESCENAS = {
    "marzo": TASKS["conciliacion-marzo"],    # el fallo y la primera victoria
    "mayo": HOLDOUT["holdout-mayo-fx910"],  # copió el 950, no la regla
}
AGENTES = {"antes": RAIZ / "mi_agente", "despues": RAIZ / "agents" / "agente_mejorado"}
PROMPT = AdkAdapter.task_prompt(None, "")


def preparar() -> None:
    # Copias reales, no symlinks: adk web descubre agentes con os.walk, que no entra en enlaces.
    for nombre, origen in AGENTES.items():
        destino = DEMO / "agentes" / nombre
        shutil.rmtree(destino, ignore_errors=True)
        shutil.copytree(origen, destino, ignore=shutil.ignore_patterns("__pycache__"))
    env = DEMO / "agentes" / ".env"  # adk web busca el .env subiendo desde cada agente
    if not env.exists() and not env.is_symlink():
        env.symlink_to(Path("..") / ".." / ".env")
    for nombre, files in ESCENAS.items():
        d = DEMO / "tareas" / nombre
        d.mkdir(parents=True, exist_ok=True)
        for n, t in files.items():
            (d / n).write_text(t, encoding="utf-8")
    (DEMO / "prompt.txt").write_text(PROMPT + "\n", encoding="utf-8")


async def correr(agent, tarea: Path) -> None:
    runner = InMemoryRunner(agent=agent, app_name="demo")
    session = await runner.session_service.create_session(app_name="demo", user_id="demo")
    msg = types.Content(role="user", parts=[types.Part(text=PROMPT)])
    final = ""
    cwd = os.getcwd()
    os.chdir(tarea)  # como adk web arrancado dentro de la carpeta de la tarea
    try:
        async for ev in runner.run_async(user_id="demo", session_id=session.id, new_message=msg):
            for p in (ev.content.parts if ev.content else None) or []:
                if p.function_call:
                    print(f"    → {p.function_call.name}({dict(p.function_call.args or {})})")
                if p.function_response and p.function_response.name == "resumir_extracto":
                    print(f"    ← {p.function_response.response}")
                if p.text and ev.is_final_response():
                    final = p.text.strip()
    finally:
        os.chdir(cwd)
    ref = reference_answer(tarea)
    print(f"    respuesta: {final!r} {'✅' if final == ref else '❌'}  (correcta: {ref!r})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-preparar", action="store_true")
    args = ap.parse_args()
    preparar()
    print(f"Tareas en {DEMO / 'tareas'} · prompt en {DEMO / 'prompt.txt'}")
    if args.solo_preparar:
        return
    agentes = {n: load_agent(DEMO / "agentes" / n) for n in ("antes", "despues")}
    loop = asyncio.new_event_loop()  # uno solo: los clientes HTTP de genai sobreviven entre corridas
    for nombre in ESCENAS:
        for label, agent in agentes.items():
            print(f"\n## {nombre} · {label}")
            loop.run_until_complete(correr(agent, DEMO / "tareas" / nombre))


if __name__ == "__main__":
    main()
