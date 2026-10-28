"""BenchmarkAdapter de Harness² que ejecuta TU agente de Google ADK (mi_agente/).

Harness² solo necesita que le digas: qué tareas hay, cómo ejecutar UNA tarea con un
árbol de harness dado, y cómo leer la trayectoria/entregable resultante. Todo lo demás
(proponer ediciones, probarlas, componer el sucesor, extraer EXPERIENCE.md) es del framework.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any

from google.adk.runners import InMemoryRunner
from google.genai import types

from harness2.core import tree
from harness2.core.spec import BenchPrompts, BenchSpec, ChannelSpec
from harness2.substrate.opencode import OpencodeSubstrate

from harness_compiler import build_agent
from import_agent import import_agent

# Lo que el editor de Harness² necesita saber del ejecutor (se inyecta en sus prompts).
EXECUTOR_NOTES = (
    "The executor is a Google ADK LlmAgent compiled from this harness. Each scripts/<n>.py "
    "that defines `def <n>(...)` with type hints and a docstring becomes an ADK tool with "
    "that exact signature (the docstring is the tool description the model sees); the "
    "agent calls tools by name, it has no shell. A script without that function becomes a "
    "tool `<n>(args: str)` run as a CLI. Deleting a script removes the tool. The "
    "deliverable is the agent's final reply. Each skills/<name>/SKILL.md (frontmatter `name:` "
    "equal to the directory, plus `description:`) becomes a NATIVE ADK skill in a SkillToolset: "
    "the agent lists it and loads its instructions with `load_skill`. Skills are knowledge and "
    "procedure only (the agent cannot read files through them); anything that needs data from "
    "the workspace must be done by a scripts/<n>.py tool. The base harness was imported from "
    "the user's agent, so its skills may contain outdated or wrong company rules."
)

# --- Escenario: conciliación de tarjetas corporativas en CLP y USD ----------------------
# El agente de partida (mi_agente/) tiene defectos que nadie le dice a Harness², repartidos
# entre el código y la skill:
#   1. la skill fija un tipo de cambio viejo (900) en vez de leer fx.txt,
#   2. la skill dice "Abonos: 0 siempre" (regla vieja de tesorería),
#   3. la tool descarta los montos negativos (abonos / notas de crédito),
#   4. ninguna tool lee fx.txt.
# Harness² tiene que descubrirlos comparando ejecuciones y corregir el harness.
AGENT_MODULE = "mi_agente"

_HDR = "date,description,amount,currency\n"
TASKS = {
    "conciliacion-marzo": {
        "ledger.csv": _HDR + (
            "2026-03-02,Hotel Santiago,120000,CLP\n"
            "2026-03-05,Vuelo SCL-LIM,350.00,USD\n"
            "2026-03-09,Reembolso hotel,-30000,CLP\n"
            "2026-03-15,Cena cliente,85.50,USD\n"
            "2026-03-20,Abono aerolinea,-50.00,USD\n"
        ),
        "fx.txt": "CLP_PER_USD=950\n",
    },
    "conciliacion-abril": {
        "ledger.csv": _HDR + (
            "2026-04-03,Taxi aeropuerto,19000,CLP\n"
            "2026-04-08,Licencia software,240.00,USD\n"
            "2026-04-12,Devolucion licencia,-40.00,USD\n"
            "2026-04-21,Almuerzo equipo,57000,CLP\n"
            "2026-04-28,Nota de credito taxi,-9500,CLP\n"
        ),
        "fx.txt": "CLP_PER_USD=950\n",
    },
}


def reference_answer(source_dir: Path) -> str:
    """Respuesta correcta. SOLO la usa report.py para marcar ✅/❌: Harness² nunca la ve."""
    import csv
    from decimal import ROUND_HALF_UP, Decimal

    rate = Decimal((source_dir / "fx.txt").read_text().split("=")[1])
    rows = list(csv.DictReader((source_dir / "ledger.csv").open()))
    total = sum((Decimal(r["amount"]) / (rate if r["currency"] == "CLP" else 1) for r in rows),
                Decimal(0)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    refunds = sum(Decimal(r["amount"]) < 0 for r in rows)
    return f"Total USD: {total}\nAbonos: {refunds}"


class AdkAdapter:
    def __init__(self, root: Path, *, model: Any, improver: ChannelSpec):
        self.root = Path(root)
        self.model = model
        # Reutilizamos la superficie c1..c8 de OpenCode: los prompts del editor la conocen.
        self.substrate = OpencodeSubstrate()
        self.spec = BenchSpec(
            name="adk_conciliacion",
            runs_root=self.root / "runs",
            install_mode="workspace_config",
            prompts=BenchPrompts(
                work="conciliar extractos de tarjetas corporativas en CLP y USD",
                deliverable_word="conciliación",
                domain_guidance=EXECUTOR_NOTES,
            ),
            channels={"proposer": improver, "selector": improver},
            leak_globs=("reference_answer.txt",),
            allow_subagents=True,
        )
        self.execution_count = 0
        base = {n: "" for n in self.substrate.surface().always_on} | import_agent(AGENT_MODULE)
        tree.write_tree(self.substrate.surface(), base, self.base_harness(), stubs=False)
        for tid, files in TASKS.items():
            d = self.task_files(tid)
            d.mkdir(parents=True, exist_ok=True)
            for name, text in files.items():
                (d / name).write_text(text, encoding="utf-8")

    # ---------- descripción de las tareas ----------
    def tasks(self, split: str = "all") -> list[str]:
        return list(TASKS)

    def domain_of(self, task_id: str) -> str:
        return "contabilidad"  # la biblioteca de experiencia se comparte por dominio

    def task_prompt(self, task_id: str) -> str:
        return (
            "Concilia el extracto ledger.csv (el tipo de cambio está en fx.txt). Responde "
            "exactamente dos líneas: `Total USD: <neto con 2 decimales>` y "
            "`Abonos: <cantidad de movimientos de abono>`."
        )

    def task_files(self, task_id: str) -> Path:
        return self.root / "sources" / task_id

    def base_harness(self) -> Path:
        return self.root / "base"

    def validate_tree(self, harness: tree.Tree) -> None:
        if "systemprompt.md" not in harness:
            raise ValueError("El agente ADK necesita systemprompt.md")

    # ---------- ejecución: aquí entra ADK ----------
    def execute(self, task_id, harness_dir, run_id, *, timeout=None) -> Path:
        run_dir = self.root / "executions" / run_id
        if self.delivered(run_dir):
            return run_dir  # idempotente por run_id (permite reanudar)
        self.execution_count += 1
        ws = run_dir / "workspace"
        shutil.copytree(self.task_files(task_id), ws, dirs_exist_ok=True)
        log: list[str] = []
        agent = build_agent(harness_dir or self.base_harness(), ws, self.model, log=log.append)
        final = asyncio.run(self._run(agent, self.task_prompt(task_id)))
        log.append(f"[FINAL]\n{final}")
        # El entregable es la respuesta final del agente, como en cualquier agente ADK.
        self._answer(run_dir).parent.mkdir(parents=True, exist_ok=True)
        self._answer(run_dir).write_text(final.strip() + "\n", encoding="utf-8")
        (run_dir / "trajectory.md").write_text("\n".join(log), encoding="utf-8")
        return run_dir

    @staticmethod
    async def _run(agent, prompt: str) -> str:
        runner = InMemoryRunner(agent=agent, app_name="h2_adk")
        s = await runner.session_service.create_session(app_name="h2_adk", user_id="h2")
        final = ""
        msg = types.Content(role="user", parts=[types.Part(text=prompt)])
        async for ev in runner.run_async(user_id="h2", session_id=s.id, new_message=msg):
            if ev.is_final_response() and ev.content and ev.content.parts:
                final = "".join(p.text or "" for p in ev.content.parts)
        return final

    # ---------- lo que Harness² lee de cada ejecución ----------
    def _answer(self, run_dir: Path) -> Path:
        return Path(run_dir) / "workspace" / "output" / "answer.md"

    def delivered(self, run_dir: Path) -> bool:
        return self._answer(run_dir).is_file()

    def trajectory(self, run_dir: Path, *, obs_trunc: int) -> str:
        return (Path(run_dir) / "trajectory.md").read_text(encoding="utf-8")

    def deliverable_text(self, run_dir: Path) -> str:
        return self._answer(run_dir).read_text(encoding="utf-8")

    def deliverable_files(self, run_dir: Path) -> dict[str, str]:
        return {"answer.md": self.deliverable_text(run_dir)}
