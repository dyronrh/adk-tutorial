"""Comprueba la persistencia sin llamar al modelo, con la configuración REAL del agente:
la misma DB_URL de main.py y la misma herramienta `recordar`.

    python test_persistencia.py

Falla si alguien rompe la URL (dos barras, memoria RAM) o quita el prefijo user: de `recordar`.
"""

import asyncio
import time
import uuid
from types import SimpleNamespace

from google.adk.events import Event, EventActions
from google.adk.sessions import DatabaseSessionService

from agente.agent import recordar
from main import APP, DB_URL

USER = f"test-{uuid.uuid4().hex[:8]}"  # usuario nuevo en cada ejecución: no toca datos reales


async def escribir() -> None:
    sesiones = DatabaseSessionService(db_url=DB_URL)
    s = await sesiones.create_session(app_name=APP, user_id=USER)
    ctx = SimpleNamespace(state={})
    recordar("nombre", "Dayron", ctx)          # la herramienta real decide el prefijo
    delta = {**ctx.state, "paso_actual": 3}    # uno de usuario, otro de sesión
    await sesiones.append_event(s, Event(author="recordar", actions=EventActions(state_delta=delta),
                                         invocation_id="inv-1", timestamp=time.time()))


async def leer() -> dict:
    sesiones = DatabaseSessionService(db_url=DB_URL)                       # proceso "nuevo"
    s = await sesiones.create_session(app_name=APP, user_id=USER)   # conversación nueva
    return dict(s.state)


if __name__ == "__main__":
    print("DB_URL:", DB_URL)
    asyncio.run(escribir())
    estado = asyncio.run(leer())
    print("estado en la sesión nueva:", estado)
    assert estado.get("user:nombre") == "Dayron", "user:nombre no sobrevivió: ¿DB_URL en memoria o recordar sin user:?"
    assert "paso_actual" not in estado, "el estado de sesión no debería pasar a otra conversación"
    print("OK: user:nombre sobrevive al reinicio; paso_actual se queda en su conversación")
