# adk-harness2 — Harness² + Google ADK: mi agente encontró sus propios errores y los corrigió solo

Código del video de Harness² de la serie *Google ADK de cero a producción*: un agente de ADK con tools **y skills nativas** que Harness² mejora sin reentrenar el modelo y sin ver nunca la respuesta correcta. Luego se exporta otra vez como un agente de ADK normal.

```
mi_agente/                tu agente ADK normal (LlmAgent + tools Python + SkillToolset)
      │  import_agent.py      instruction -> systemprompt.md · cada tool -> scripts/<tool>.py · skills/ -> skills/
      ▼
runs/<salida>/base/       harness base
      │  Harness²             ejecuta el agente, compara variantes, edita prompt/reglas/memoria/skills/tools
      ▼
runs/<salida>/.../harness/   harness adoptado + EXPERIENCE.md
      │  export_agent.py
      ▼
agents/agente_mejorado/   agente ADK normal otra vez (agent.py + tools/ + skills/), sin dependencia de Harness²
```

Harness² no toca los pesos del modelo ni tu `mi_agente/`. Edita los archivos del harness, prueba las variantes en las mismas tareas, elige la mejor **sin respuestas de referencia** (comparando ejecuciones) y guarda la lección en `EXPERIENCE.md` para la siguiente tarea.

Diagramas de la arquitectura y del ciclo por tarea: [ARQUITECTURA.md](ARQUITECTURA.md).

## El caso del video

`mi_agente/` concilia extractos de tarjetas corporativas en CLP y USD y tiene **4 defectos** que nadie le dice a Harness²:

1. La skill `conciliacion-tarjetas` fija un tipo de cambio viejo (900) en vez de leer `fx.txt`.
2. La skill dice "Reporta siempre `Abonos: 0`".
3. La tool `resumir_extracto` descarta los montos negativos.
4. Ninguna tool lee `fx.txt`.

Resultado de la corrida del 27-oct-2026 (`runs/adk_skills_k2_pro`, 25 min, 7,99 USD): la skill dejó de forzar `Abonos: 0`, la tool suma los negativos y cuenta los abonos, y la skill cambió 900 por **950 fijo** (copió el número, no la regla). En la validación (`runs/validacion.md`, Gemini 2.5 Flash, 3 repeticiones), las tareas vistas pasaron de 0 a 6 de 6 y las nuevas de 0 a 6 de 9. Mayo, con tipo de cambio 910, falla las 3 veces por ese 950.

## Requisitos

- Python 3.12, `pip install -r requirements.txt` (google-adk 2.13+, que trae `SkillToolset`).
- Harness² instalado desde su repo (`pip install -e <ruta>/harness2`). En mi máquina todo está en `~/harness2/.venv`.
- Una API key de Gemini: copia `.env.example` a `.env` y rellénala. El agente y el editor de Harness² (vía OpenCode) usan la misma.

## Archivos

| Archivo | Qué hace |
|---|---|
| `mi_agente/` | El agente de partida, con `skills/conciliacion-tarjetas/SKILL.md`. Cámbialo por el tuyo |
| `import_agent.py` | `root_agent` → harness base (instrucción, tools y skills) |
| `harness_compiler.py` | harness → `LlmAgent` en cada ejecución: cada `scripts/<n>.py` con `def <n>(...)` es una tool, y `skills/` se carga con un `SkillToolset` nativo |
| `adk_adapter.py` | `BenchmarkAdapter` de Harness²: tareas, ejecución con `InMemoryRunner`, trayectoria y entregable (la respuesta final) |
| `export_agent.py` | harness adoptado → `agents/agente_mejorado/` |
| `validar.py` | Antes / después con el modelo real, sobre tareas vistas y nuevas (holdout) |
| `report.py` | `EVIDENCIA.md`: diffs por candidato, instrucción y tools que ve ADK, entregables, código final |
| `offline.py` | Modelo y editor **guionados** para una prueba de humo sin credenciales |
| `demo_web/` | Las escenas del video en `adk web` (ver abajo) |

## Correr Harness²

```bash
source ~/harness2/.venv/bin/activate

# 1) Prueba de humo (sin LLM): las ediciones están guionadas en offline.py
python run.py --offline --k 1 --mode parallel

# 2) Mejora real, como en el video (editor por defecto: google/gemini-3.1-pro-preview)
python run.py --k 2 --mode parallel --output runs/adk_skills_k2_pro
```

Si la carpeta de salida ya existe, Harness² **reanuda** (las tareas salen `skipped` y no se ejecuta nada): bórrala o usa otro `--output`.

En la corrida del video la reflexión salió `confounded` en las dos tareas (cambiaron la tool y la skill a la vez) y no guardó ninguna lección, así que `run.py` no exportó. El agente se exportó a mano desde el harness adoptado de abril (la traza cruda de esa corrida no está en el repo; el resumen sí, en `runs/adk_skills_k2_pro/EVIDENCIA.md` y `result.json`, y el agente exportado en `agents/agente_mejorado/`):

```bash
python export_agent.py runs/adk_skills_k2_pro/runs/adk_conciliacion-oc-agg2/conciliacion-abril/harnesses/agg2 agents/agente_mejorado
```

## Validar antes / después

```bash
python validar.py --repeticiones 3     # mi_agente vs agents/agente_mejorado, con Gemini real
```

Corre los dos agentes con el mismo modelo sobre las tareas vistas y sobre tareas nuevas (`HOLDOUT` en `validar.py`), N veces cada una, y compara contra la respuesta correcta. Resultado en `runs/validacion.md`. Si mejora en las vistas pero no en el holdout, el harness se sobreajustó.

## Verlo en adk web

```bash
./demo_web/web.sh marzo     # antes: 900 → 568,83 ❌ · despues: 950 → 480,24 / Abonos 2 ✅
./demo_web/web.sh mayo      # despues usa 950 aunque fx.txt diga 910 → 395,56 ❌
python demo_web/probar.py   # las 4 combinaciones sin abrir el navegador, con las llamadas a la tool
```

Abre http://127.0.0.1:8000, elige `antes` o `despues` y pega el prompt que imprime la terminal (`demo_web/prompt.txt`). En la traza se ven `load_skill` y `resumir_extracto` con su `clp_por_usd`.

- `web.sh` arranca adk web **dentro** de `demo_web/tareas/<tarea>/`, porque las tools abren `ledger.csv` con ruta relativa. Usa `VENV=<ruta>` si tu entorno no está en `~/harness2/.venv`.
- `demo_web/agentes/antes` y `despues` son **copias** de `mi_agente/` y `agents/agente_mejorado/` que se regeneran en cada arranque: adk web 2.13 descubre los agentes con `os.walk` y no entra en enlaces simbólicos.

## Para usar tu propio agente

1. Copia tu agente a `mi_agente/` (o cambia `AGENT_MODULE` en `adk_adapter.py`). El importador necesita `instruction` como texto, tools que sean funciones Python y, si las tiene, skills en `mi_agente/skills/<nombre>/SKILL.md`.
2. Cambia `TASKS` y `task_prompt` en `adk_adapter.py` por casos reales de tu dominio. `reference_answer` solo la usan el reporte y `validar.py` para marcar ✅/❌; Harness² no la ve.
3. Usa tareas variadas (en el video, 2 tipos de cambio distintos habrían obligado a escribir la regla en vez de copiar el 950), y deja algunas fuera para el holdout.

## Límites

- Harness² no soporta ADK oficialmente; esto reutiliza la superficie de OpenCode (c1..c8).
- No se importan ni exportan callbacks, sub_agents de ADK, `AgentTool`, MCP toolsets ni instrucciones con `{estado}`. Las tools importadas deben ser autocontenidas (función + imports del módulo).
- Una skill es conocimiento: no puede leer archivos. Si el arreglo necesita datos, el editor tiene que escribir una tool.
- c8 (plugins) no está mapeado.
- Cada corrida real hace varias ejecuciones del agente y varias sesiones del editor: cuesta tokens (la del video, 7,99 USD).
