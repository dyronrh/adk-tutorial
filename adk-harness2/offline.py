"""Piezas para correr el flujo SIN credenciales (prueba de humo, no prueba de mejora real).

- ScriptedLlm: un "modelo" ADK determinista que OBEDECE el system prompt: llama, en el
  orden en que aparecen, a las tools nombradas entre backticks en systemprompt.md (rellena
  los argumentos `ruta_*` con ledger.csv / fx.txt) y responde con sus `resultado`.
- OfflineEditor: reemplaza al editor/selector LLM de Harness² con ediciones GUIONADAS.
  Sirven para ver dónde queda cada evidencia; la mejora real la hace el editor LLM
  (python run.py sin --offline).
    inv<i> -> tools: crea total_neto_usd, borra resumir_extracto, ajusta prompt y guía
    dom<i> -> prompt (paso + formato), guardrails, memoria y tool nueva contar_abonos
    agg<i> -> combina ambos
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import AsyncGenerator

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from harness2.core.proposer import Proposer, Reply


class ScriptedLlm(BaseLlm):
    model: str = "scripted-offline"

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        system = str(llm_request.config.system_instruction or "")
        prompt_only = system.split("\n## ", 1)[0]  # solo c1, no guardrails ni guía
        tools = llm_request.tools_dict
        steps = list(dict.fromkeys(n for n in re.findall(r"`(\w+)`", prompt_only) if n in tools))
        done = [p.function_response for c in llm_request.contents
                for p in (c.parts or []) if p.function_response]

        if len(done) < len(steps):
            name = steps[len(done)]
            args = {}
            for p in inspect.signature(tools[name].func).parameters:
                args[p] = "fx.txt" if ("fx" in p or "cambio" in p) else "ledger.csv"
            part = types.Part(function_call=types.FunctionCall(name=name, args=args))
            yield LlmResponse(content=types.Content(role="model", parts=[part]))
        else:
            text = "\n".join(str((r.response or {}).get("resultado", r.response)) for r in done)
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


# ---------------------------------------------------------------------------------------
# Ediciones guionadas (mismo formato que import_agent.py: función + CLI JSON)
# ---------------------------------------------------------------------------------------
CLI = '''

if __name__ == "__main__":
    import json, sys
    print(json.dumps({name}(**json.loads(sys.argv[1] if len(sys.argv) > 1 else "{{}}"))))
'''

TOTAL_NETO = '''"""Tool ADK `total_neto_usd`."""
import csv
from decimal import ROUND_HALF_UP, Decimal


def total_neto_usd(ruta_csv: str, ruta_fx: str) -> dict:
    """Total neto del extracto en USD: convierte CLP con el tipo de cambio de fx.txt y suma
    CON SIGNO (los abonos restan).

    Args:
      ruta_csv: ruta al CSV del extracto.
      ruta_fx: ruta al archivo con CLP_PER_USD=<tasa>.
    """
    tasa = Decimal(open(ruta_fx).read().split("=")[1])
    total = Decimal(0)
    with open(ruta_csv) as f:
        for r in csv.DictReader(f):
            m = Decimal(r["amount"])
            total += m / tasa if r["currency"] == "CLP" else m
    return {"resultado": f"Total USD: {total.quantize(Decimal('0.01'), ROUND_HALF_UP)}"}
''' + CLI.format(name="total_neto_usd")

CONTAR_ABONOS = '''"""Tool ADK `contar_abonos`."""
import csv
from decimal import Decimal


def contar_abonos(ruta_csv: str) -> dict:
    """Cuenta los movimientos de abono (montos negativos) del extracto.

    Args:
      ruta_csv: ruta al CSV del extracto.
    """
    with open(ruta_csv) as f:
        n = sum(Decimal(r["amount"]) < 0 for r in csv.DictReader(f))
    return {"resultado": f"Abonos: {n}"}
''' + CLI.format(name="contar_abonos")


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    path.write_text(text.replace(old, new) if old else text + new, encoding="utf-8")


def apply_inv(h: Path) -> str:
    (h / "scripts/total_neto_usd.py").write_text(TOTAL_NETO, encoding="utf-8")
    (h / "scripts/resumir_extracto.py").unlink(missing_ok=True)
    _edit(h / "systemprompt.md", "`resumir_extracto` con el archivo ledger.csv",
          "`total_neto_usd` con ledger.csv y fx.txt")
    guide = h / "tool_descriptions/tool_guidance.md"
    guide.write_text(re.sub(r"^- `resumir_extracto.*\n", "", guide.read_text(), flags=re.M)
                     + "- `total_neto_usd(ruta_csv, ruta_fx)`: neto en USD; convierte CLP con "
                       "fx.txt y resta los abonos. Úsala siempre en lugar de sumar a mano.\n",
                     encoding="utf-8")
    return ("En la trayectoria base, resumir_extracto sumó CLP como si fueran USD y descartó los "
            "negativos. Reemplacé la tool por total_neto_usd y actualicé el system prompt.")


def apply_dom(h: Path) -> str:
    (h / "scripts/contar_abonos.py").write_text(CONTAR_ABONOS, encoding="utf-8")
    _edit(h / "systemprompt.md", "",
          "Después usa `contar_abonos` con ledger.csv.\n\n"
          "Formato obligatorio de la respuesta (dos líneas, sin texto extra):\n"
          "Total USD: <neto con 2 decimales>\nAbonos: <n>\n")
    _edit(h / "guardrails.md", "",
          "- Un abono (monto negativo) nunca se descarta: se resta del total y se cuenta.\n"
          "- No sumes montos de monedas distintas sin convertirlos.\n"
          "- deny: \\.\\./\n")
    _edit(h / "LongTermMEMORY.md", "",
          "- Los abonos y notas de crédito aparecen como montos negativos.\n"
          "- Los extractos mezclan CLP y USD; el tipo de cambio viene en fx.txt (CLP_PER_USD).\n")
    _edit(h / "tool_descriptions/tool_guidance.md", "",
          "- `contar_abonos(ruta_csv)`: cuenta los movimientos de abono del extracto.\n")
    return ("La tarea pide `Abonos: <n>` y el agente no lo reporta. Agregué el paso, el formato "
            "de respuesta, la tool contar_abonos, guardrails y memoria del dominio.")


class OfflineEditor(Proposer):
    """Editor/selector guionado: no llama a ningún LLM."""

    def call(self, mission, context_dir, label, **kwargs) -> Reply:
        ctx = Path(context_dir)
        stage = label.split(".", 1)[0]
        workspace = None
        if label.startswith("select."):
            text = self._select(ctx)
        elif label.startswith("experience."):
            text = self._experience(ctx)
        else:
            workspace = ctx / "harness"
            notes = []
            if stage.startswith(("inv", "agg")):
                notes.append(apply_inv(workspace))
            if stage.startswith(("dom", "agg")):
                notes.append(apply_dom(workspace))
            text = "<notes>" + " ".join(notes) + "</notes>"
        reply = Reply(label=label, text=text, ok=True, attempts=1, workspace=workspace)
        self._calls.append(reply)
        return reply

    @staticmethod
    def _select(ctx: Path) -> str:
        # Sin respuesta de referencia: preferimos el candidato que cumple el formato completo.
        cands = sorted((ctx / "candidates").glob("*.md"))
        ok = [c for c in cands if re.search(r"^Total USD: .*\n^Abonos: \d+", c.read_text(), re.M)]
        chosen = (ok or cands)[0].stem
        return f"<why>Es el único que entrega ambas líneas del formato.</why>\n```choice\n{chosen}\n```"

    @staticmethod
    def _experience(ctx: Path) -> str:
        h, b = ctx / "harness", ctx / "base_harness"
        if (h / "systemprompt.md").read_text() == (b / "systemprompt.md").read_text():
            return "<edits>\ncomponent: (ninguno)\nverdict: no observed effect\n</edits>\n\nNO_ENTRY"
        edits = (
            "component: scripts/total_neto_usd.py (tool nueva) + scripts/resumir_extracto.py (borrada)\n"
            "candidates: inv1\nchange: convierte CLP con fx.txt y suma con signo\n"
            "observed: el total dejó de mezclar CLP con USD\nverdict: helped\n\n"
            "component: scripts/contar_abonos.py (tool nueva) + systemprompt.md\n"
            "candidates: dom1\nchange: paso contar_abonos y formato de dos líneas\n"
            "observed: aparece `Abonos: n`, que la base nunca reportaba\nverdict: helped\n\n"
            "component: guardrails.md, LongTermMEMORY.md\ncandidates: dom1\n"
            "change: reglas de abonos y monedas; memoria CLP/USD\n"
            "observed: sin efecto observable en esta tarea\nverdict: no observed effect"
        )
        return (
            f"<edits>\n{edits}\n</edits>\n\n<experience>\n"
            "cue: Cuando un extracto mezcla monedas y trae abonos (montos negativos)\n"
            "lesson: Usa una tool que convierta con fx.txt y sume con signo, y otra que cuente "
            "abonos; el system prompt debe invocar ambas y fijar el formato.\n"
            "evidence: inv1 solo corrigió el total y dom1 solo agregó los abonos; agg1 combinó "
            "ambos y fue el único con las dos líneas correctas.\n"
            "confidence: alta para este contraste aritmético\n</experience>"
        )
