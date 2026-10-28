"""Arma runs/adk/EVIDENCIA.md: qué propuso Harness² en cada candidato, cómo cambió el agente
ADK (instrucción y tools) y qué entregó cada variante.

  python report.py            # después de python run.py ...
"""

from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path

from adk_adapter import TASKS, reference_answer
from harness_compiler import describe_agent

ORDER = {"base": 0, "inv": 1, "dom": 2, "c": 3, "agg": 4}


def _files(d: Path) -> dict[str, str]:
    skip = ("README.md",)
    return {p.relative_to(d).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted(d.rglob("*")) if p.is_file() and p.name not in skip}


def _diff(a: str, b: str, name: str) -> str:
    return "".join(difflib.unified_diff(a.splitlines(True), b.splitlines(True),
                                        f"base/{name}", f"candidato/{name}"))


def _answer(executions: Path, label: str) -> str:
    f = executions / label / "workspace/output/answer.md"
    return f.read_text(encoding="utf-8").strip() if f.is_file() else "(sin entregable)"


def _tools_md(tools: dict[str, str]) -> str:
    return "\n".join(f"- `{n}` — {d.splitlines()[0] if d else ''}" for n, d in tools.items())


def task_section(root: Path, run_dir: Path, task_dir: Path, detail: bool) -> list[str]:
    task = task_dir.name
    executions = root / "executions" / run_dir.name / task
    ref = reference_answer(root / "sources" / task)
    harnesses = sorted((task_dir / "harnesses").iterdir(),
                       key=lambda p: (ORDER.get(p.name.rstrip("0123456789"), 9), p.name))
    base = _files(task_dir / "harnesses/base")
    base_agent = describe_agent(task_dir / "harnesses/base")
    out = [f"## Tarea `{task}` — corrida `{run_dir.name}`", "",
           "Respuesta correcta (solo para este reporte; Harness² **no** la ve):", "",
           "```", ref, "```", "",
           "| Candidato | Archivos que cambió | Tools ADK resultantes | Entregable | ¿Correcto? |",
           "|---|---|---|---|---|"]
    details = []
    for h in harnesses:
        label = "base1" if h.name == "base" else h.name
        files = _files(h)
        changed = [f for f in sorted(set(base) | set(files)) if base.get(f) != files.get(f)]
        tag = lambda f: f"`{f}`" + (" (nuevo)" if f not in base else " (borrado)" if f not in files else "")
        agent = describe_agent(h)
        tools = [t.split("(")[0] for t in agent["tools"] if t.split("(")[0] not in ("skill", "load_skill", "task")]
        ans = _answer(executions, label)
        out.append(f"| **{h.name}** | {', '.join(map(tag, changed)) or '—'} | {', '.join(tools)} | "
                   f"`{ans.replace(chr(10), ' / ')}` | {'✅' if ans == ref else '❌'} |")
        if not changed or not detail:
            continue
        details += [f"### {task} · {h.name}: cambios propuestos", ""]
        decision = next(task_dir.glob(f"reflection/*/decisions/{h.name}.md"), None)
        if decision and decision.read_text().strip():
            details += [f"> Nota del editor: {decision.read_text().strip()}", ""]
        for f in changed:
            details += [f"**{tag(f)}**", "", "```diff",
                        _diff(base.get(f, ""), files.get(f, ""), f).rstrip(), "```", ""]
        details += ["**Lo que recibe ADK** (instrucción compuesta, diff contra la base):", "", "```diff",
                    _diff(base_agent["instruction"] + "\n", agent["instruction"] + "\n",
                          "instruction").rstrip(), "```", "",
                    "**Tools del `LlmAgent`:**", "", _tools_md(agent["tools"]), ""]
    out += [""] + details
    for sel in sorted(task_dir.glob("selection/*/selection.json")):
        s = json.loads(sel.read_text())
        out += [f"### {task}: selección", "",
                f"- elegido: **{s['chosen_label']}** (¿es la base? {s['chosen_is_base']})",
                f"- por qué: {s['why']}", ""]
    return out


def main(root: Path = Path("runs/adk_real")) -> Path:
    root = root.resolve()
    lines = ["# Evidencia: Harness² mejorando un agente de Google ADK", "",
             "Cada candidato es un árbol de archivos (prompt, guardrails, memoria, tools). "
             "`harness_compiler.build_agent` lo convierte en un `LlmAgent`. Abajo, por tarea: "
             "qué cambió cada candidato, cómo quedó la instrucción y las tools de ADK, y qué entregó.", ""]
    failed = [(f.name.split(".")[0], json.loads(f.read_text()).get("error", ""))
              for f in sorted((root / "audit").glob("*.meta.json"))
              if not json.loads(f.read_text()).get("ok", True)]
    if failed:
        lines += ["> ⚠️ **Sesiones del editor fallidas** (esos candidatos quedaron iguales a la base):", ""]
        lines += [f"> - `{n}`: {e[:200]}" for n, e in failed] + [""]
    for run_dir in sorted((root / "runs").iterdir()):
        tasks = [run_dir / t for t in TASKS if (run_dir / t / "harnesses").is_dir()]
        for i, task_dir in enumerate(tasks):
            lines += task_section(root, run_dir, task_dir, detail=i == 0)
            if i == 0 and len(tasks) > 1:
                lines += ["> Las tareas siguientes repiten el mismo patrón de diffs; abajo va solo "
                          "su tabla. Los árboles completos están en `runs/<corrida>/<tarea>/harnesses/`.", ""]
    for exp in sorted(root.glob("library/*/*/*/harnesses/*/EXPERIENCE.md"))[-1:]:
        lines += [f"## Biblioteca de experiencia: `{exp.relative_to(root)}`", "",
                  exp.read_text(encoding="utf-8").replace("\n# ", "\n### "), ""]
    project = root.parent.parent
    agents = project / ("agents/offline" if root.name.endswith("offline") else "agents")
    start, best = project / "mi_agente/agent.py", agents / "agente_mejorado"
    if start.is_file() and (best / "agent.py").is_file():
        lines += ["## Código ADK: agente de partida vs. agente mejorado", "",
                  "### `mi_agente/agent.py` (escrito a mano, entrada de Harness²)", "",
                  "```python", start.read_text().rstrip(), "```", "",
                  f"### `{best.relative_to(project)}/agent.py` (generado desde el harness adoptado)", "",
                  "```python", (best / "agent.py").read_text().rstrip(), "```", ""]
        for t in sorted((best / "tools").glob("*.py")):
            if t.name != "__init__.py":
                lines += [f"### `{best.relative_to(project)}/tools/{t.name}`", "",
                          "```python", t.read_text().rstrip(), "```", ""]
    out = root / "EVIDENCIA.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("runs/adk_real")))
