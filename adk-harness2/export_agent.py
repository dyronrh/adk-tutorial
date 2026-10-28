"""Convierte un árbol de harness en un agente ADK normal: agent.py + tools/*.py.

  python export_agent.py <harness_dir> agents/agente_mejorado

Es el camino inverso de import_agent.py. El resultado tiene la misma forma que mi_agente/
(funciones Python como tools, instrucción como texto) y no depende de Harness²:
`adk run agents/agente_mejorado`. Compara con `diff -ru mi_agente agents/agente_mejorado`.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from harness_compiler import _catalog, _deny_patterns, _read, compose_instruction, script_tools

TEMPLATE = '''"""Agente ADK generado por Harness² desde el harness {source}.

No lo edites a mano: re-genéralo con export_agent.py después de cada corrida.
"""

import os
import re
import shlex
import subprocess
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

{imports}

TOOLS = Path(__file__).parent / "tools"
SKILLS = Path(__file__).parent / "skills"

# ---- c1..c4: system prompt + guardrails + memoria + guía de tools ------------------------
INSTRUCTION = """\\
{instruction}
"""

# ---- c2: bloqueos duros de guardrails.md (líneas `deny: <regex>`) -------------------------
DENY = {deny!r}
{cli_defs}

def guardrail(tool, args, tool_context):
    for pat in DENY:
        if re.search(pat, f"{{tool.name}} {{args}}"):
            return {{"error": f"Bloqueado por guardrail: /{{pat}}/"}}
    return None


root_agent = LlmAgent(
    name={name!r},
    model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
    instruction=lambda _ctx: INSTRUCTION,  # callable: las {{llaves}} no se tratan como estado
    tools=[{tool_list}],  # + SkillToolset con skills/ (c6) si las hay
    before_tool_callback=guardrail,
)
'''

CLI_TOOL = '''

def {name}(args: str = "") -> dict:
    """{doc}

    Args:
      args: argumentos de línea de comandos del script.
    """
    r = subprocess.run(["python3", str(TOOLS / "{name}.py"), *shlex.split(args)],
                       capture_output=True, text=True, timeout=120)
    return {{"resultado": r.stdout.strip(), "error": r.stderr.strip()}}
'''


def _rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(Path.cwd()).as_posix()
    except ValueError:
        return p.as_posix()


def export(harness: Path, out: Path) -> Path:
    harness, out = Path(harness), Path(out)
    skills = _catalog(harness / "skills", "*/SKILL.md")
    subagents = _catalog(harness / "sub_agents", "*/AGENT.md")
    if subagents:
        print(f"aviso: {out.name} no exporta subagentes (solo c1..c4, skills y tools)")
    tools = script_tools(harness)
    if out.exists():
        shutil.rmtree(out)
    (out / "tools").mkdir(parents=True)
    (out / "tools/__init__.py").write_text("", encoding="utf-8")
    for f in (harness / "scripts").glob("*.py"):
        shutil.copy(f, out / "tools" / f.name)
    if (harness / "skills").is_dir():
        shutil.copytree(harness / "skills", out / "skills",
                        ignore=shutil.ignore_patterns("README.md", "__pycache__"))
    typed = [n for n, (_, sig) in tools.items() if sig is not None]
    code = TEMPLATE.format(
        source=_rel(harness),
        imports="\n".join(f"from .tools.{n} import {n}" for n in typed),
        instruction=compose_instruction(harness, skills, subagents)
        .replace("\\", "\\\\").replace('"""', '\\"""'),
        deny=[p.pattern for p in _deny_patterns(_read(harness / "guardrails.md"))],
        cli_defs="".join(CLI_TOOL.format(name=n, doc=d.replace('"""', "'''"))
                         for n, (d, sig) in tools.items() if sig is None),
        tool_list=", ".join([*tools] + (
            ["SkillToolset(skills=[load_skill_from_dir(d) for d in sorted(SKILLS.iterdir()) "
             "if (d / 'SKILL.md').is_file()])"] if skills else [])),
        name=out.name,
    )
    (out / "agent.py").write_text(code, encoding="utf-8")
    (out / "__init__.py").write_text("from . import agent\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(export(Path(sys.argv[1]), Path(sys.argv[2])) / "agent.py")
