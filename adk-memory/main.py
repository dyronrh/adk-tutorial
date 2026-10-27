"""Corre el agente con sesiones persistentes: SQLite en local, Postgres en producción.

    python main.py "Hola, me llamo Dayron y programo en Go"
    python main.py "¿Cómo me llamo?"        # nueva sesión, mismo usuario
"""

import asyncio
import os
import sys

from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from agente.agent import root_agent

# En Cloud Run: postgresql+asyncpg://usuario:clave@host/db (Cloud SQL)
DB_URL = os.getenv("SESSION_DB_URL", "sqlite+aiosqlite:///memoria.db")
APP, USER = "asistente_dev", "dayron"


async def main(mensaje: str) -> None:
    sesiones = DatabaseSessionService(db_url=DB_URL)
    runner = Runner(app_name=APP, agent=root_agent, session_service=sesiones)

    # Cada ejecución abre una conversación NUEVA: lo que recuerde viene de "user:"
    sesion = await sesiones.create_session(app_name=APP, user_id=USER)
    pregunta = types.Content(role="user", parts=[types.Part(text=mensaje)])

    async for evento in runner.run_async(user_id=USER, session_id=sesion.id, new_message=pregunta):
        if evento.is_final_response() and evento.content:
            print(evento.content.parts[0].text)


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "Hola"))
