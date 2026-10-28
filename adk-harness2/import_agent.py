"""Convierte un agente ADK existente en el harness base que Harness² va a mejorar.

  python import_agent.py mi_agente runs/adk/base

  root_agent.instruction (str)       -> systemprompt.md
  cada función de root_agent.tools   -> scripts/<tool>.py (función + imports del módulo + CLI JSON)
  docstrings de las tools            -> tool_descriptions/tool_guidance.md
  <agente>/skills/<n>/ (SkillToolset) -> skills/<n>/SKILL.md (+ scripts/): c6, Harness² también las edita
  guardrails.md / LongTermMEMORY.md  -> vacíos (Harness² decide si los llena)

`harness_compiler.build_agent` hace el camino inverso en cada ejecución, así que el agente
compilado desde este harness es el mismo agente que escribiste.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import sys
import textwrap
from pathlib import Path

CLI = '''

if __name__ == "__main__":  # CLI del harness: python3 scripts/{name}.py '{{"arg": "valor"}}'
    import json, sys
    out = {name}(**json.loads(sys.argv[1] if len(sys.argv) > 1 else "{{}}"))
    print(json.dumps(out, ensure_ascii=False, default=str))
'''


def _module_imports(module) -> str:
    """Imports de nivel módulo del agente, menos los de ADK (las tools no los necesitan)."""
    tree = ast.parse(inspect.getsource(module))
    keep = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            src = ast.get_source_segment(inspect.getsource(module), node) or ""
            if "google.adk" not in src and "__future__" not in src:
                keep.append(src)
    return "\n".join(keep)


def import_agent(module_name: str) -> dict[str, str]:
    """Devuelve el árbol de harness {ruta: contenido} del `root_agent` del módulo."""
    pkg = importlib.import_module(module_name)
    module = importlib.import_module(f"{module_name}.agent") if hasattr(pkg, "agent") else pkg
    agent = module.root_agent
    if not isinstance(agent.instruction, str):
        raise ValueError("Este importador necesita `instruction` como texto, no un callable.")
    imports = _module_imports(module)
    tree = {
        "systemprompt.md": agent.instruction.strip() + "\n",
        "guardrails.md": "",
        "LongTermMEMORY.md": "",
    }
    guidance = []
    agent_dir = Path(inspect.getfile(module)).parent
    for f in sorted((agent_dir / "skills").glob("*/**/*")):
        if f.is_file() and "__pycache__" not in f.parts:
            tree[f"skills/{f.relative_to(agent_dir / 'skills').as_posix()}"] = f.read_text(encoding="utf-8")
    for tool in agent.tools:
        if type(tool).__name__ == "SkillToolset":
            continue  # sus skills ya se copiaron desde <agente>/skills/
        fn = getattr(tool, "func", tool)  # FunctionTool o función suelta
        if not inspect.isfunction(fn):
            raise ValueError(f"Tool no soportada por el importador: {tool!r}")
        name = fn.__name__
        doc = inspect.getdoc(fn) or ""
        src = textwrap.dedent(inspect.getsource(fn))
        tree[f"scripts/{name}.py"] = (
            f'"""Tool ADK `{name}` importada de {module_name}."""\n'
            f"{imports}\n\n\n{src.rstrip()}\n{CLI.format(name=name)}"
        )
        params = ", ".join(inspect.signature(fn).parameters)
        guidance.append(f"- `{name}({params})`: {doc.splitlines()[0] if doc else ''}")
    tree["tool_descriptions/tool_guidance.md"] = "\n".join(guidance) + "\n"
    return tree


if __name__ == "__main__":
    from harness2.core import tree as HT
    from harness2.substrate.opencode import OpencodeSubstrate

    surface = OpencodeSubstrate().surface()
    out = HT.write_tree(surface, import_agent(sys.argv[1]), Path(sys.argv[2]), stubs=False)
    print(out)
