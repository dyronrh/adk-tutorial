"""Agente ADK generado por Harness² desde el harness runs/adk_skills_k2_pro/runs/adk_conciliacion-oc-agg2/conciliacion-abril/harnesses/agg2.

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

from .tools.resumir_extracto import resumir_extracto

TOOLS = Path(__file__).parent / "tools"
SKILLS = Path(__file__).parent / "skills"

# ---- c1..c4: system prompt + guardrails + memoria + guía de tools ------------------------
INSTRUCTION = """\
Eres un analista contable. Cuando te pidan conciliar un extracto de tarjeta corporativa, carga la skill `conciliacion-tarjetas` y sigue su procedimiento.

## Guía de herramientas
- `resumir_extracto(ruta_csv, clp_por_usd)`: Suma los cargos del extracto de la tarjeta corporativa, convirtiendo CLP a USD.

## Skills disponibles (cárgalas con la herramienta `load_skill`)
- `conciliacion-tarjetas`: Procedimiento corporativo para conciliar extractos de tarjetas corporativas en CLP y USD.
"""

# ---- c2: bloqueos duros de guardrails.md (líneas `deny: <regex>`) -------------------------
DENY = []


def guardrail(tool, args, tool_context):
    for pat in DENY:
        if re.search(pat, f"{tool.name} {args}"):
            return {"error": f"Bloqueado por guardrail: /{pat}/"}
    return None


root_agent = LlmAgent(
    name='agente_mejorado',
    model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
    instruction=lambda _ctx: INSTRUCTION,  # callable: las {llaves} no se tratan como estado
    tools=[resumir_extracto, SkillToolset(skills=[load_skill_from_dir(d) for d in sorted(SKILLS.iterdir()) if (d / 'SKILL.md').is_file()])],  # + SkillToolset con skills/ (c6) si las hay
    before_tool_callback=guardrail,
)
