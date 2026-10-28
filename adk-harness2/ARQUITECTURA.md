# Arquitectura: Harness² mejorando un agente de Google ADK

Versión Excalidraw (editable) en [diagramas/](diagramas/): ábrelos en https://excalidraw.com
(menú → Open) o con la extensión "Excalidraw" de VS Code. Se regeneran con
`python diagramas/generar.py`.

| Archivo | Contenido |
|---|---|
| `diagramas/1-arquitectura-general.excalidraw` | componentes y flujo de punta a punta |
| `diagramas/2-ciclo-por-tarea.excalidraw` | las 5 etapas por tarea, con los resultados reales de abril |
| `diagramas/3-sesion-del-editor.excalidraw` | qué hace una sesión de OpenCode |
| `diagramas/4-harness-a-adk.excalidraw` | cómo c1..c7 se convierten en un `LlmAgent` |

## 1. Vista general

```mermaid
flowchart LR
    subgraph TU["Tu código"]
        A["mi_agente/agent.py<br/>LlmAgent + tools Python"]
    end

    subgraph PUENTE["Puente ADK ↔ Harness² (este repo)"]
        IMP["import_agent.py<br/>instruction → systemprompt.md<br/>tools → scripts/&lt;tool&gt;.py"]
        BASE[("runs/…/base/<br/>harness base<br/>c1..c7 en archivos")]
        ADP["adk_adapter.py<br/>BenchmarkAdapter<br/>tareas · execute() · trayectoria"]
        CMP["harness_compiler.py<br/>harness → LlmAgent"]
        EXP["export_agent.py<br/>harness → agent.py + tools/"]
        REP["report.py<br/>EVIDENCIA.md"]
        VAL["validar.py<br/>antes vs después<br/>+ holdout"]
    end

    subgraph H2["Harness² (~/harness2)"]
        RD["run_domain()<br/>recursión por tarea"]
        LIB[("library/<br/>harness adoptado<br/>+ EXPERIENCE.md")]
    end

    subgraph EDIT["Editor (por sesión)"]
        OC["OpenCode fijado<br/>dependencies/opencode<br/>vía bun, aislado"]
    end

    subgraph GEM["Gemini (GOOGLE_API_KEY)"]
        G1["gemini-2.5-flash<br/>ejecuta el agente"]
        G2["gemini-3.1-pro-preview<br/>edita / compone / elige"]
    end

    OUT["agents/agente_mejorado/<br/>agente ADK normal"]

    A --> IMP --> BASE --> RD
    RD -- "execute(tarea, harness)" --> ADP
    ADP --> CMP -- "InMemoryRunner" --> G1
    RD -- "misión + evidencia" --> OC <--> G2
    OC -- "context/harness editado" --> RD
    RD --> LIB --> EXP --> OUT
    RD --> REP
    A --> VAL
    OUT --> VAL
```

## 2. Qué pasa en cada tarea (`--k 2 --mode parallel`)

```mermaid
flowchart TB
    T["Tarea: conciliacion-abril<br/>ledger.csv + fx.txt"]
    LIBIN[("EXPERIENCE.md de<br/>tareas anteriores")]

    subgraph S1["1 · BASE: evidencia"]
        B1["base1"] & B2["base2"]
    end

    subgraph S2["2 · PROPONER: 2k candidatos independientes"]
        I1["inv1"] & I2["inv2"]
        D1["dom1"] & D2["dom2"]
    end

    subgraph S3["3 · COMPONER: k composiciones independientes"]
        AG1["agg1"] & AG2["agg2"]
    end

    SEL{"4 · ELEGIR<br/>juez LLM compara ejecuciones<br/>sin respuesta de referencia"}
    XP["5 · APRENDER<br/>EXPERIENCE.md<br/>qué edición ayudó y por qué"]
    LIBOUT[("library/…/harness<br/>harness adoptado")]

    T --> S1
    LIBIN -.-> S2
    S1 -- "trayectorias + entregables" --> S2
    S2 -- "diffs + ejecuciones" --> S3
    S3 -- "ejecuciones" --> SEL
    SEL -- "abril: agg2" --> XP --> LIBOUT
    LIBOUT -. "siguiente tarea" .-> LIBIN
```

Cada nodo de las etapas 2 a 5 es **una sesión de OpenCode** (Gemini editando archivos), y cada
candidato de las etapas 1 a 3 se **ejecuta** como agente ADK en la misma tarea.

- **inv** (investigar): busca en las trayectorias de base el momento en que falla y corrige ese componente.
- **dom** (dominio): propone cambios desde el conocimiento del dominio.
- **agg** (agregar): ve todos los candidatos con sus diffs y resultados; conserva lo que funcionó.

## 3. Una sesión del editor

```mermaid
sequenceDiagram
    participant H as Harness² (Proposer)
    participant W as Carpeta de sesión
    participant O as OpenCode (bun)
    participant G as Gemini pro

    H->>W: MISSION.md, context/harness/, rollouts/, deliverables/
    H->>O: run "Read MISSION.md…" --dir W --model google/gemini-3.1-pro-preview
    Note over O: XDG_DATA/STATE propios · sin acceso fuera de W · límite de pasos
    loop herramientas (leer / editar archivos)
        O->>G: contexto + herramientas
        G-->>O: leer rollout, editar scripts/resumir_extracto.py, …
        O->>W: cambios en context/harness/
    end
    O-->>H: respuesta final con notas
    H->>W: recoge context/harness/
    H->>H: valida el árbol (¿cambió? ¿refs válidas?)
    alt inválido
        H->>O: "YOUR PREVIOUS ATTEMPT WAS REJECTED…" (intento 2)
    else válido
        H->>H: candidato listo para ejecutar
    end
    Note over H: todo queda en audit/ (mission.md, response.md, meta.json, workspace/)
```

## 4. Cómo un harness se vuelve un agente ADK (`harness_compiler.py`)

```mermaid
flowchart LR
    subgraph HARNESS["Harness (archivos)"]
        C1["c1 systemprompt.md"]
        C2["c2 guardrails.md"]
        C3["c3 LongTermMEMORY.md"]
        C4["c4 tool_guidance.md"]
        C5["c5 sub_agents/*/AGENT.md"]
        C6["c6 skills/*/SKILL.md"]
        C7["c7 scripts/&lt;n&gt;.py"]
    end

    subgraph ADK["LlmAgent"]
        INS["instruction"]
        CB["before_tool_callback<br/>(líneas deny: regex)"]
        T7["tool &lt;n&gt;(…)<br/>misma firma y docstring"]
        TS["tool skill(name)"]
        TT["tool task(agent, prompt)<br/>LlmAgent hijo"]
    end

    C1 & C3 & C4 --> INS
    C2 --> INS
    C2 --> CB
    C7 --> T7
    C6 --> TS
    C5 --> TT
```

c8 (plugins) no está mapeado. Las tools importadas desde `mi_agente` se ejecutan como
subproceso (`python3 scripts/<n>.py '{json}'`) dentro del workspace de la tarea.

## 5. Dónde queda cada cosa

| Artefacto | Ruta |
|---|---|
| Agente de partida | `mi_agente/agent.py` |
| Harness base | `runs/adk_real_k2/base/` |
| Árbol de cada candidato | `runs/adk_real_k2/runs/<corrida>/<tarea>/harnesses/<candidato>/` |
| Ejecución de cada candidato | `runs/adk_real_k2/executions/<corrida>/<tarea>/<candidato>/trajectory.md` |
| Sesiones del editor | `runs/adk_real_k2/audit/` |
| Selección | `runs/adk_real_k2/runs/<corrida>/<tarea>/selection/*/selection.json` |
| Harness adoptado + lección | `runs/adk_real_k2/library/k2/agg/contabilidad/harnesses/<tarea>/` |
| Agente mejorado | `agents/agente_mejorado/` |
| Reporte por candidato | `runs/adk_real_k2/EVIDENCIA.md` |
| Validación antes/después | `runs/validacion.md` |
