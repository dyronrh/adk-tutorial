# adk-memory — Google ADK #3: tu agente olvida todo en Cloud Run

Código del capítulo 3 de la serie *Google ADK de cero a producción*: memoria de corto plazo (sesión), semántica (estado con `user:`) y episódica (`MemoryService`), con sesiones persistentes en base de datos.

## Requisitos

- Python 3.11+
- `pip install -r requirements.txt` (instala `google-adk[db]` 2.12+ y `aiosqlite`)
- Una API key de Gemini solo para `main.py`: copia `.env.example` a `.env` y rellénala (o exporta `GOOGLE_API_KEY`).

## Archivos

| Archivo | Qué hace |
|---|---|
| `agente/agent.py` | El agente: la herramienta `recordar` escribe en `tool_context.state` con el prefijo `user:`, y la instrucción lee el bloque de memoria `{user:nombre?}` / `{user:lenguaje?}`. |
| `main.py` | Corre el agente con `DatabaseSessionService` (`sqlite+aiosqlite:///memoria.db` en local; en producción, `SESSION_DB_URL` con Postgres/Cloud SQL). Cada ejecución abre una conversación nueva. |
| `test_persistencia.py` | Comprueba la persistencia **sin llamar al modelo**, con la `DB_URL` y la herramienta reales: `user:nombre` sobrevive al reinicio y el dato de sesión no. Falla si alguien rompe la URL o quita el prefijo `user:`. Ideal para CI. |
| `memoria_largo_plazo.py` | Memoria episódica sin modelo: guarda una conversación con `add_session_to_memory` y la recupera desde otra con `search_memory`. |

## Probarlo

```bash
python test_persistencia.py          # sin API key
python memoria_largo_plazo.py        # sin API key

python main.py "Hola, me llamo Dayron y programo en Go"
python main.py "¿En qué lenguaje programo?"   # conversación nueva → "Programas en Go."
```

## La trampa del video

`sqlite://memoria.db` (dos barras) no es una ruta: con `adk web` o `--session_service_uri` ADK te da memoria en RAM sin avisar. Usa tres barras: `sqlite:///memoria.db`. Con `DatabaseSessionService` directo, la URL de dos barras da un error visible.
