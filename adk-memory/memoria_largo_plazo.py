"""Memoria a largo plazo (episódica) sin llamar al modelo: guarda una conversación pasada y búscala.

    python memoria_largo_plazo.py

En producción el MemoryService sería Memory Bank (agentengine://…) o sqlite:// en local, y el agente
la consulta con las tools `load_memory` (cuando el modelo lo decide) o `preload_memory` (cada turno).
"""

import asyncio
import time

from google.adk.events import Event
from google.adk.memory import InMemoryMemoryService
from google.adk.sessions import InMemorySessionService
from google.genai import types

APP, USER = "asistente_dev", "dayron"


def mensaje(autor: str, texto: str) -> Event:
    rol = "user" if autor == "user" else "model"
    return Event(author=autor, invocation_id="inv", timestamp=time.time(),
                 content=types.Content(role=rol, parts=[types.Part(text=texto)]))


async def main() -> None:
    sesiones = InMemorySessionService()
    memoria = InMemoryMemoryService()

    # la conversación de la semana pasada
    pasada = await sesiones.create_session(app_name=APP, user_id=USER)
    for ev in (mensaje("user", "El incidente de checkout-api fue por el despliegue v2.4"),
               mensaje("asistente_dev", "Anotado: revisaré despliegues recientes primero")):
        await sesiones.append_event(pasada, ev)
    pasada = await sesiones.get_session(app_name=APP, user_id=USER, session_id=pasada.id)

    # al cerrar la conversación, pasa a la memoria de largo plazo
    await memoria.add_session_to_memory(pasada)

    # hoy, en otra conversación, el agente busca en lo que vivió
    resultado = await memoria.search_memory(app_name=APP, user_id=USER, query="checkout-api despliegue")
    textos = [m.content.parts[0].text for m in resultado.memories]
    print("recuerdos encontrados:", textos)
    assert any("v2.4" in t for t in textos), "no encontró la conversación pasada"
    print("OK: la conversación de la semana pasada se puede recuperar en una nueva")


if __name__ == "__main__":
    asyncio.run(main())
