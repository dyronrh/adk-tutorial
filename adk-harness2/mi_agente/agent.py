"""Agente ADK de partida: una tool Python + una skill nativa de ADK (SkillToolset).

  adk run mi_agente            # o: adk web .

Harness² no edita este archivo. `import_agent.py` lo convierte en un harness
(instrucción -> systemprompt.md, tools -> scripts/<tool>.py, skills/ -> skills/), Harness²
mejora ese harness y `export_agent.py` genera el agente mejorado en agents/agente_mejorado/.
"""

import csv
import os
from decimal import Decimal
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset


def resumir_extracto(ruta_csv: str, clp_por_usd: float) -> dict:
    """Suma los cargos del extracto de la tarjeta corporativa, convirtiendo CLP a USD.

    Args:
      ruta_csv: ruta al CSV del extracto (columnas date, description, amount, currency).
      clp_por_usd: pesos chilenos por dólar.
    """
    with open(ruta_csv) as f:
        filas = list(csv.DictReader(f))
    tasa = Decimal(str(clp_por_usd))
    total = sum(
        (Decimal(r["amount"]) / (tasa if r["currency"] == "CLP" else 1)
         for r in filas if Decimal(r["amount"]) > 0),
        Decimal(0),
    )
    return {"total_usd": f"{total:.2f}"}


SKILLS = Path(__file__).parent / "skills"

root_agent = LlmAgent(
    name="conciliador",
    model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
    instruction=(
        "Eres un analista contable. Cuando te pidan conciliar un extracto de tarjeta "
        "corporativa, carga la skill `conciliacion-tarjetas` y sigue su procedimiento."
    ),
    tools=[
        resumir_extracto,
        SkillToolset(skills=[load_skill_from_dir(d) for d in sorted(SKILLS.iterdir()) if d.is_dir()]),
    ],
)
