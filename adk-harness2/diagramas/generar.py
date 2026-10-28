"""Genera los diagramas de arquitectura en formato Excalidraw.

  python diagramas/generar.py

Abre los .excalidraw en https://excalidraw.com (menú > Open) o con la extensión
"Excalidraw" de VS Code. Se pueden editar a mano; si cambias este script, se regeneran.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

OUT = Path(__file__).parent
COLOR = {
    "tu": "#ffec99",       # tu código
    "puente": "#a5d8ff",   # este repo
    "h2": "#d0bfff",       # Harness²
    "oc": "#ffd8a8",       # OpenCode
    "gem": "#b2f2bb",      # Gemini
    "out": "#96f2d7",      # resultado
    "bad": "#ffc9c9",
    "good": "#b2f2bb",
    "gray": "#e9ecef",
    "none": "transparent",
}


class Diagram:
    def __init__(self) -> None:
        self.el: list[dict] = []
        self.by_id: dict[str, dict] = {}
        self.n = 0

    def _base(self, kind: str, x, y, w, h, **kw) -> dict:
        self.n += 1
        e = {
            "id": kw.pop("id", f"{kind}{self.n}"), "type": kind, "x": x, "y": y,
            "width": w, "height": h, "angle": 0, "strokeColor": "#1e1e1e",
            "backgroundColor": "transparent", "fillStyle": "solid", "strokeWidth": 2,
            "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [],
            "frameId": None, "roundness": None, "seed": random.randint(1, 2**31),
            "version": 1, "versionNonce": random.randint(1, 2**31), "isDeleted": False,
            "boundElements": [], "updated": 1, "link": None, "locked": False,
        }
        e.update(kw)
        self.el.append(e)
        self.by_id[e["id"]] = e
        return e

    def text(self, x, y, s, size=20, container=None, align="left", color="#1e1e1e", w=None):
        lines = s.split("\n")
        tw = w or max(len(l) for l in lines) * size * 0.55 + 4
        th = len(lines) * size * 1.25
        e = self._base("text", x, y, tw, th, text=s, originalText=s, fontSize=size,
                       fontFamily=5, textAlign=align, verticalAlign="middle",
                       containerId=container, lineHeight=1.25, autoResize=True,
                       strokeColor=color)
        if container:
            self.by_id[container]["boundElements"].append({"type": "text", "id": e["id"]})
        return e

    def box(self, id, x, y, w, h, label, color="none", size=18, shape="rectangle",
            dashed=False, bold=False):
        e = self._base(shape, x, y, w, h, id=id, backgroundColor=COLOR[color],
                       roundness={"type": 3} if shape == "rectangle" else {"type": 2},
                       strokeStyle="dashed" if dashed else "solid",
                       strokeWidth=4 if bold else 2)
        t = self.text(0, 0, label, size, container=id, align="center")
        t["x"] = x + (w - t["width"]) / 2
        t["y"] = y + (h - t["height"]) / 2
        return e

    def zone(self, id, x, y, w, h, title, size=22):
        self._base("rectangle", x, y, w, h, id=id, strokeStyle="dashed", strokeWidth=1,
                   roundness={"type": 3}, backgroundColor="#f8f9fa", strokeColor="#868e96")
        self.text(x + 14, y + 10, title, size, color="#495057")

    def arrow(self, a, b, label=None, dashed=False, side=None, via=None):
        """Flecha de a a b. side: ('r','l'), ('b','t'), ... ; via: puntos intermedios absolutos."""
        A, B = self.by_id[a], self.by_id[b]

        def anchor(E, s):
            cx, cy = E["x"] + E["width"] / 2, E["y"] + E["height"] / 2
            return {"r": (E["x"] + E["width"], cy), "l": (E["x"], cy),
                    "t": (cx, E["y"]), "b": (cx, E["y"] + E["height"])}[s]

        if side is None:
            dx = (B["x"] + B["width"] / 2) - (A["x"] + A["width"] / 2)
            dy = (B["y"] + B["height"] / 2) - (A["y"] + A["height"] / 2)
            side = (("r", "l") if dx > 0 else ("l", "r")) if abs(dx) > abs(dy) else \
                   (("b", "t") if dy > 0 else ("t", "b"))
        (x1, y1), (x2, y2) = anchor(A, side[0]), anchor(B, side[1])
        pts = [(x1, y1), *(via or []), (x2, y2)]
        e = self._base("arrow", x1, y1, abs(x2 - x1), abs(y2 - y1),
                       points=[[px - x1, py - y1] for px, py in pts],
                       lastCommittedPoint=None, startArrowhead=None, endArrowhead="arrow",
                       startBinding={"elementId": a, "focus": 0, "gap": 4},
                       endBinding={"elementId": b, "focus": 0, "gap": 4},
                       strokeStyle="dashed" if dashed else "solid",
                       roundness={"type": 2} if not via else None, elbowed=False)
        A["boundElements"].append({"type": "arrow", "id": e["id"]})
        B["boundElements"].append({"type": "arrow", "id": e["id"]})
        if label:
            t = self.text(0, 0, label, 15, container=e["id"], align="center")
            mx, my = pts[len(pts) // 2 - (0 if len(pts) % 2 else 1)]
            nx, ny = pts[len(pts) // 2]
            t["x"], t["y"] = (mx + nx) / 2 - t["width"] / 2, (my + ny) / 2 - t["height"] / 2
        return e

    def save(self, name: str) -> Path:
        p = OUT / name
        p.write_text(json.dumps({
            "type": "excalidraw", "version": 2, "source": "adk_harness2/diagramas/generar.py",
            "elements": self.el,
            "appState": {"viewBackgroundColor": "#ffffff", "gridSize": None},
            "files": {},
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        return p


def legend(d: Diagram, x, y):
    d.text(x, y, "Leyenda", 20)
    for i, (c, s) in enumerate([("tu", "tu código"), ("puente", "puente ADK ↔ Harness² (este repo)"),
                                ("h2", "Harness²"), ("oc", "OpenCode (editor)"),
                                ("gem", "Gemini"), ("out", "resultado")]):
        d.box(f"leg{i}", x, y + 36 + i * 44, 36, 30, "", c)
        d.text(x + 48, y + 40 + i * 44, s, 16)


# ---------------------------------------------------------------------------------------
def general() -> Path:
    d = Diagram()
    W, H = 250, 100
    d.text(40, -120, "Harness² mejorando un agente de Google ADK: vista general", 30)
    row = 60
    d.box("agent", 40, row, W, H, "mi_agente/agent.py\nLlmAgent + tools Python", "tu")
    d.box("imp", 360, row, W, H, "import_agent.py\ninstruction → systemprompt.md\ntools → scripts/<tool>.py", "puente", 16)
    d.box("base", 680, row, W, H, "harness base\nruns/…/base/\n(archivos c1..c7)", "puente")
    d.box("rd", 1000, row, W, H, "run_domain()\nrecursión por tarea", "h2", bold=True)
    d.box("lib", 1320, row, W, H, "library/\nharness adoptado\n+ EXPERIENCE.md", "h2")
    d.box("exp", 1640, row, W, H, "export_agent.py\nharness → agent.py + tools/", "puente", 16)
    d.box("mej", 1960, row, W, H, "agents/agente_mejorado/\nagente ADK normal", "out", bold=True)

    d.box("adp", 840, 300, W, H, "adk_adapter.py\nBenchmarkAdapter\ntareas · execute()", "puente", 16)
    d.box("cmp", 840, 470, W, H, "harness_compiler.py\nharness → LlmAgent\n(InMemoryRunner)", "puente", 16)
    d.box("flash", 840, 640, W, H, "gemini-2.5-flash\nejecuta el agente", "gem")

    d.box("oc", 1170, 300, W, H, "OpenCode fijado\n~/harness2/dependencies\n(bun, sesión aislada)", "oc", 16)
    d.box("pro", 1170, 470, W, H, "gemini-3.1-pro-preview\nedita · compone · elige", "gem", 16)

    d.box("rep", 1320, -100, W, 80, "report.py → EVIDENCIA.md", "puente", 16)
    d.box("val", 1960, 300, W, H, "validar.py\nantes vs después\n+ tareas nuevas", "puente", 16)

    d.arrow("agent", "imp")
    d.arrow("imp", "base")
    d.arrow("base", "rd")
    d.arrow("rd", "lib", "adopta")
    d.arrow("lib", "exp")
    d.arrow("exp", "mej")
    d.arrow("rd", "adp", "execute(tarea,\nharness)", side=("b", "t"))
    d.arrow("adp", "cmp")
    d.arrow("cmp", "flash")
    d.arrow("rd", "oc", "misión +\nevidencia", side=("b", "t"))
    d.arrow("oc", "pro", side=("b", "t"))
    d.arrow("pro", "oc", side=("t", "b"))
    d.arrow("rd", "rep", side=("t", "l"), via=[(1125, -60)])
    d.arrow("mej", "val", side=("b", "t"))
    d.arrow("agent", "val", "antes", dashed=True, side=("b", "b"),
            via=[(165, 860), (2085, 860)])
    legend(d, 40, 920)
    d.text(1520, 520, "1. Harness² ejecuta tu agente (flash) y\n   guarda trayectoria + respuesta.\n"
                      "2. El editor (OpenCode + pro) lee esa\n   evidencia y edita los archivos.\n"
                      "3. Ejecuta los candidatos, elige el\n   mejor y lo guarda en library/.", 17)
    return d.save("1-arquitectura-general.excalidraw")


def ciclo() -> Path:
    d = Diagram()
    W, H = 230, 90
    d.text(60, -150, "Qué pasa en cada tarea (--k 2 --mode parallel) — ejemplo: conciliacion-abril", 28)
    d.box("task", 480, -70, 340, 80, "Tarea: conciliacion-abril\nledger.csv + fx.txt", "gray")
    d.box("prev", 1120, -70, 260, 80, "EXPERIENCE.md de\ntareas anteriores", "h2", dashed=True)

    d.zone("z1", 40, 60, 1360, 160, "1 · BASE — tu agente tal cual (evidencia)")
    d.box("b1", 360, 110, W, H, "base1\n❌ 76240.00 / Abonos: 0", "bad", 16)
    d.box("b2", 720, 110, W, H, "base2\n❌ 76240.00 / Abonos: 0", "bad", 16)

    d.zone("z2", 40, 280, 1360, 170, "2 · PROPONER — 2k editores independientes")
    for i, (lab, txt) in enumerate([("inv1", "inv1 · investigar"), ("inv2", "inv2 · investigar"),
                                    ("dom1", "dom1 · dominio"), ("dom2", "dom2 · dominio")]):
        d.box(lab, 100 + i * 320, 335, W, H, f"{txt}\n✅ 270.00 / Abonos: 2", "good", 16)

    d.zone("z3", 40, 510, 1360, 160, "3 · COMPONER — k composiciones independientes")
    d.box("agg1", 360, 560, W, H, "agg1\n✅ 270.00 / Abonos: 2", "good", 16)
    d.box("agg2", 720, 560, W, H, "agg2\n✅ 270.00 / Abonos: 2", "good", 16, bold=True)

    d.box("sel", 520, 730, 260, 150, "4 · ELEGIR\njuez LLM, sin\nrespuesta correcta", "h2", 16,
          shape="diamond")
    d.box("xp", 360, 950, W, H, "5 · APRENDER\nEXPERIENCE.md", "h2", 16)
    d.box("lib", 720, 950, W, H, "library/…/harness\nharness adoptado (agg2)", "out", 16, bold=True)

    d.arrow("task", "z1", side=("b", "t"))
    d.arrow("prev", "z2", "", dashed=True, side=("b", "t"), via=[(1250, 260)])
    d.arrow("z1", "z2", "trayectorias + respuestas", side=("b", "t"))
    d.arrow("z2", "z3", "diffs + ejecuciones de cada candidato", side=("b", "t"))
    d.arrow("z3", "sel", "ejecuciones de agg1 y agg2", side=("b", "t"))
    d.arrow("sel", "xp", "elige agg2", side=("b", "t"), via=[(650, 915), (475, 915)])
    d.arrow("xp", "lib")
    d.arrow("lib", "prev", "siguiente tarea", dashed=True, side=("r", "r"),
            via=[(1460, 995), (1460, -30)])

    notes = ("Cada caja de las etapas 2 a 5 es una SESIÓN de OpenCode\n(Gemini pro leyendo y editando archivos).\n"
             "Cada candidato de las etapas 1 a 3 se EJECUTA como\nagente ADK en la misma tarea.\n\n"
             "inv  = busca en las trayectorias el momento en que\n        falla y corrige ese componente\n"
             "dom  = propone desde el conocimiento del dominio\n"
             "agg  = ve todos los candidatos con sus diffs y\n        resultados; conserva lo que funcionó\n"
             "elegir = compara ejecuciones; no conoce la respuesta")
    d.text(1520, 120, notes, 17)
    return d.save("2-ciclo-por-tarea.excalidraw")


def sesion() -> Path:
    d = Diagram()
    W, H = 260, 100
    d.text(40, -120, "Una sesión del editor (inv / dom / agg / select / experience)", 28)
    d.box("h2", 40, 40, W, H, "Harness² (Proposer)", "h2", bold=True)
    d.box("ws", 400, 40, W + 40, H + 40,
          "carpeta de sesión\nMISSION.md\ncontext/harness/  (editable)\nrollouts/ · deliverables/", "gray", 16)
    d.box("oc", 800, 40, W, H, "OpenCode fijado (bun)\nXDG propio · sin acceso\nfuera de la carpeta", "oc", 16)
    d.box("pro", 1160, 40, W, H, "gemini-3.1-pro-preview", "gem")
    d.box("val", 400, 300, W + 40, H, "valida el árbol\n¿cambió algo? ¿refs válidas?", "h2", 16)
    d.box("ok", 860, 300, W, H, "candidato listo\n→ se ejecuta como agente ADK", "out", 16)
    d.box("audit", 40, 560, W, H, "audit/<etapa>.*\nmission · response\nmeta · workspace", "gray", 16)

    d.arrow("h2", "ws", "1. prepara")
    d.arrow("ws", "oc", "2. run --dir")
    d.arrow("oc", "pro", "3. leer / editar\narchivos (loop)")
    d.arrow("ws", "val", "4. recoge\ncontext/harness/", side=("b", "t"))
    d.arrow("val", "ok", "válido")
    d.arrow("val", "h2", "inválido → intento 2\n(\"PREVIOUS ATTEMPT WAS REJECTED\")", dashed=True,
            side=("b", "b"), via=[(550, 470), (170, 470)])
    d.arrow("h2", "audit", "guarda todo", side=("l", "l"), dashed=True,
            via=[(10, 90), (10, 610)])
    return d.save("3-sesion-del-editor.excalidraw")


def mapeo() -> Path:
    d = Diagram()
    d.text(40, -100, "Cómo un harness se vuelve un LlmAgent (harness_compiler.py)", 28)
    files = [("c1", "c1 · systemprompt.md"), ("c2", "c2 · guardrails.md"), ("c3", "c3 · LongTermMEMORY.md"),
             ("c4", "c4 · tool_guidance.md"), ("c5", "c5 · sub_agents/*/AGENT.md"),
             ("c6", "c6 · skills/*/SKILL.md"), ("c7", "c7 · scripts/<n>.py")]
    for i, (k, s) in enumerate(files):
        d.box(k, 40, i * 110, 320, 80, s, "puente", 18)
    d.box("ins", 700, 110, 340, 140, "instruction\n(texto compuesto)", "gem", 20)
    d.box("cb", 700, 320, 340, 80, "before_tool_callback\nlíneas `deny: <regex>`", "gem", 16)
    d.box("t7", 700, 660, 340, 90, "tool <n>(…)\nmisma firma y docstring", "gem", 18, bold=True)
    d.box("ts", 700, 550, 340, 80, "tool skill(name)", "gem", 18)
    d.box("tt", 700, 440, 340, 80, "tool task(agent, prompt)\nLlmAgent hijo", "gem", 16)
    d.zone("adk", 660, 70, 420, 720, "LlmAgent")
    for k in ("c1", "c2", "c3", "c4"):
        d.arrow(k, "ins", side=("r", "l"))
    d.arrow("c2", "cb", side=("r", "l"))
    d.arrow("c5", "tt", side=("r", "l"))
    d.arrow("c6", "ts", side=("r", "l"))
    d.arrow("c7", "t7", side=("r", "l"))
    d.text(1140, 640, "Las tools importadas de mi_agente se ejecutan como\n"
                      "subproceso: python3 scripts/<n>.py '{json}'\n"
                      "dentro del workspace de la tarea.\n\n"
                      "c8 (plugins) no está mapeado.", 17)
    # la zona debe quedar detrás: muévela al principio
    z = [e for e in d.el if e["id"] == "adk" or (e["type"] == "text" and e["text"] == "LlmAgent")]
    d.el = z + [e for e in d.el if e not in z]
    return d.save("4-harness-a-adk.excalidraw")


if __name__ == "__main__":
    random.seed(7)
    for f in (general, ciclo, sesion, mapeo):
        print(f())
