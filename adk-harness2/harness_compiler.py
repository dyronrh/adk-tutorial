"""Compila un árbol de harness de Harness² (c1..c8) a un agente de Google ADK.

Harness² edita ARCHIVOS (systemprompt.md, guardrails.md, skills/, scripts/, ...).
Este módulo es el puente: lee esos archivos y construye un `LlmAgent` equivalente.
Si Harness² cambia un archivo, el agente ADK cambia de comportamiento en la
siguiente ejecución, sin tocar los pesos del modelo.

Mapeo de componentes:
  c1 systemprompt.md                     -> instruction (InstructionProvider, sin templating)
  c2 guardrails.md                       -> instruction + before_tool_callback (`deny: <regex>`)
  c3 LongTermMEMORY.md                   -> instruction (memoria de dominio siempre presente)
  c4 tool_descriptions/tool_guidance.md  -> instruction (cómo usar las herramientas)
  c5 sub_agents/<n>/AGENT.md             -> tool `task` que delega en un LlmAgent hijo
  c6 skills/<n>/SKILL.md (+ scripts/)    -> SkillToolset nativo de ADK (list_skills / load_skill)
  c7 scripts/<n>.py                      -> tool ADK `<n>`:
                                              - si define `def <n>(...)`, con esa misma firma tipada
                                                y docstring (así importa import_agent.py tus tools)
                                              - si no, `<n>(args: str)` y se ejecuta como CLI
  c8 plugin/                             -> no mapeado (ver README)

El harness importado de un agente tiene c1..c4, c6 y c7, así que el agente compilado
tiene exactamente las tools y skills originales. El SkillToolset aparece si el harness tiene skills (importadas del agente o
creadas por Harness²) y `task` solo si Harness² crea subagentes.
"""

from __future__ import annotations

import ast
import inspect
import json
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Callable

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.skills import load_skill_from_dir
from google.adk.skills.models import Frontmatter, Skill
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.tools.tool_context import ToolContext
from google.genai import types

ALWAYS_ON = (
    ("systemprompt.md", None),
    ("guardrails.md", "Guardrails (reglas obligatorias)"),
    ("LongTermMEMORY.md", "Memoria de largo plazo del dominio"),
    ("tool_descriptions/tool_guidance.md", "Guía de herramientas"),
)
_FM = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
_TYPES = {"str": str, "int": int, "float": float, "bool": bool, "list": list, "dict": dict}


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = _FM.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip("\"'")
    return meta, m.group(2).strip()


def _catalog(root: Path, pattern: str) -> dict[str, tuple[str, str]]:
    """name -> (description, body) para skills/*/SKILL.md o sub_agents/*/AGENT.md."""
    out = {}
    for f in sorted(root.glob(pattern)):
        meta, body = _frontmatter(f.read_text(encoding="utf-8"))
        out[meta.get("name", f.parent.name)] = (meta.get("description", ""), body)
    return out


def load_skills(harness: Path, log: Callable[[str], None] = lambda s: None) -> list[Skill]:
    """skills/<n>/ -> Skill de ADK. Si el editor dejó un frontmatter inválido, la skill se carga
    igual con nombre = carpeta (y se avisa en la trayectoria) para no perder su contenido."""
    out = []
    for d in sorted(p for p in (Path(harness) / "skills").glob("*") if (p / "SKILL.md").is_file()):
        try:
            out.append(load_skill_from_dir(d))
        except Exception as exc:  # noqa: BLE001
            meta, body = _frontmatter((d / "SKILL.md").read_text(encoding="utf-8"))
            log(f"[ERROR] skill {d.name}: {exc}. Cargada con nombre de carpeta.")
            out.append(Skill(frontmatter=Frontmatter(
                name=d.name, description=meta.get("description") or f"Skill {d.name}"),
                instructions=body))
    return out


def compose_instruction(harness: Path, skills: dict, subagents: dict) -> str:
    parts = []
    for rel, title in ALWAYS_ON:
        text = _read(harness / rel)
        if text:
            parts.append(f"## {title}\n{text}" if title else text)
    if skills:
        lines = "\n".join(f"- `{n}`: {d}" for n, (d, _) in skills.items())
        parts.append(f"## Skills disponibles (cárgalas con la herramienta `load_skill`)\n{lines}")
    if subagents:
        lines = "\n".join(f"- `{n}`: {d}" for n, (d, _) in subagents.items())
        parts.append(f"## Subagentes (delega con la herramienta `task`)\n{lines}")
    return "\n\n".join(parts)


def _deny_patterns(guardrails: str) -> list[re.Pattern]:
    """Líneas `deny: <regex>` en guardrails.md se vuelven bloqueos que el modelo no puede saltarse."""
    return [re.compile(m.strip()) for m in re.findall(r"^\s*-?\s*deny:\s*(.+)$", guardrails, re.M)]


# ---- c7: scripts -> tools -------------------------------------------------------------------
def script_spec(path: Path) -> tuple[str, inspect.Signature | None]:
    """(docstring, firma) leídos con ast, sin ejecutar el script. Firma None = script CLI."""
    try:
        mod = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return f"Ejecuta scripts/{path.name}.", None
    fn = next((n for n in mod.body if isinstance(n, ast.FunctionDef) and n.name == path.stem), None)
    if fn is None:
        return ast.get_docstring(mod) or f"Ejecuta scripts/{path.name}.", None
    args, defaults = fn.args.args, fn.args.defaults
    pad = [inspect.Parameter.empty] * (len(args) - len(defaults))
    params = [
        inspect.Parameter(
            a.arg, inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=_TYPES.get(getattr(a.annotation, "id", ""), str),
            default=d if d is inspect.Parameter.empty else ast.literal_eval(d),
        )
        for a, d in zip(args, pad + list(defaults))
    ]
    return ast.get_docstring(fn) or "", inspect.Signature(params, return_annotation=dict)


def script_tools(harness: Path) -> dict[str, tuple[str, inspect.Signature | None]]:
    return {f.stem: script_spec(f) for f in sorted((Path(harness) / "scripts").glob("*.py"))}


def _run_script(script: Path, argv: list[str], workspace: Path) -> dict:
    r = subprocess.run(["python3", str(script), *argv], cwd=workspace,
                       capture_output=True, text=True, timeout=120)
    if r.returncode == 0:
        try:
            out = json.loads(r.stdout)
            return out if isinstance(out, dict) else {"resultado": out}
        except json.JSONDecodeError:
            return {"resultado": r.stdout.strip()[-8000:]}
    return {"error": r.stderr.strip()[-2000:] or f"exit {r.returncode}"}


def _make_tool(harness: Path, name: str, doc: str, sig, workspace: Path) -> Callable:
    script = harness / "scripts" / f"{name}.py"
    if sig is None:
        def tool(args: str = "") -> dict:
            return _run_script(script, shlex.split(args), workspace)
        doc += "\n\nArgs:\n  args: argumentos de línea de comandos del script."
    else:
        def tool(**kwargs) -> dict:
            return _run_script(script, [json.dumps(kwargs, ensure_ascii=False)], workspace)
        tool.__signature__ = sig
        tool.__annotations__ = {p.name: p.annotation for p in sig.parameters.values()} | {"return": dict}
    tool.__name__ = tool.__qualname__ = name
    tool.__doc__ = doc
    return tool


def describe_agent(harness: Path) -> dict:
    """Lo que ADK verá para un árbol dado: instrucción final y catálogo de herramientas."""
    harness = Path(harness)
    skills = _catalog(harness / "skills", "*/SKILL.md")
    subagents = _catalog(harness / "sub_agents", "*/AGENT.md")
    tools = {
        f"{n}({', '.join(sig.parameters) if sig else 'args'})": doc
        for n, (doc, sig) in script_tools(harness).items()
    }
    if skills:
        tools["load_skill(skill_name)"] = f"SkillToolset nativo de ADK: {sorted(skills)}"
    if subagents:
        tools["task(agent, prompt)"] = f"Delega en subagentes: {sorted(subagents)}"
    return {
        "instruction": compose_instruction(harness, skills, subagents),
        "tools": tools,
        "deny": [p.pattern for p in _deny_patterns(_read(harness / "guardrails.md"))],
    }


def build_agent(
    harness: Path,
    workspace: Path,
    model: Any,
    *,
    name: str = "worker",
    log: Callable[[str], None] = lambda s: None,
    subagent_model: Any | None = None,
) -> LlmAgent:
    """Devuelve un LlmAgent cuyo comportamiento queda definido por el árbol `harness`."""
    harness, workspace = Path(harness), Path(workspace)
    skills = _catalog(harness / "skills", "*/SKILL.md")
    subagents = _catalog(harness / "sub_agents", "*/AGENT.md")
    instruction = compose_instruction(harness, skills, subagents)
    denies = _deny_patterns(_read(harness / "guardrails.md"))

    tools: list[Any] = [_make_tool(harness, n, d, s, workspace)
                        for n, (d, s) in script_tools(harness).items()]

    # ---- c6: skills nativas de ADK (SkillToolset) ------------------------------------------
    if skills:
        tools.append(SkillToolset(skills=load_skills(harness, log)))

    # ---- c5: subagentes con contexto propio ------------------------------------------------
    if subagents:
        script_only = list(tools)

        async def task(agent: str, prompt: str) -> dict:
            """Delega un subtrabajo a un subagente del harness; corre en su PROPIO contexto."""
            if agent not in subagents:
                return {"error": f"Subagente desconocido. Disponibles: {sorted(subagents)}"}
            child = LlmAgent(
                name=re.sub(r"\W", "_", agent),
                model=subagent_model or model,
                instruction=lambda _ctx, body=subagents[agent][1]: body,
                tools=script_only,
            )
            runner = InMemoryRunner(agent=child, app_name="h2_sub")
            s = await runner.session_service.create_session(app_name="h2_sub", user_id="h2")
            final = ""
            msg = types.Content(role="user", parts=[types.Part(text=prompt)])
            async for ev in runner.run_async(user_id="h2", session_id=s.id, new_message=msg):
                if ev.is_final_response() and ev.content and ev.content.parts:
                    final = "".join(p.text or "" for p in ev.content.parts)
            log(f"[SUBAGENT {agent}] {final[:400]}")
            return {"result": final}

        tools.append(task)

    # ---- c2: guardrails que se aplican DENTRO del bucle de herramientas --------------------
    def before_tool(tool: BaseTool, args: dict, tool_context: ToolContext) -> dict | None:
        flat = f"{tool.name} {args}"
        for pat in denies:
            if pat.search(flat):
                log(f"[ERROR] guardrail bloqueó {tool.name}: /{pat.pattern}/")
                return {"error": f"Bloqueado por guardrail: /{pat.pattern}/"}
        log(f"[ACTION] {tool.name}({args})")
        return None

    def after_tool(tool: BaseTool, args: dict, tool_context: ToolContext, tool_response: Any):
        log(f"[OBSERVATION]\n{str(tool_response)[:2000]}")
        return None

    return LlmAgent(
        name=name,
        model=model,
        # Un callable evita que ADK interprete {llaves} del harness como variables de estado.
        instruction=lambda _ctx: instruction,
        tools=tools,
        before_tool_callback=before_tool,
        after_tool_callback=after_tool,
    )
