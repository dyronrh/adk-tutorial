from google.adk.agents import Agent
from google.adk.tools import ToolContext


def recordar(clave: str, valor: str, tool_context: ToolContext) -> dict:
    """Guarda un dato del usuario para futuras conversaciones."""
    tool_context.state[f"user:{clave}"] = valor
    return {"status": "guardado", "clave": clave}


root_agent = Agent(
    name="asistente_dev",
    model="gemini-3.6-flash",
    instruction="""Eres un asistente para desarrolladores. Responde en texto plano, sin markdown.

Lo que sabes del usuario:
- Nombre: {user:nombre?}
- Lenguaje favorito: {user:lenguaje?}

Si el usuario te dice su nombre o su lenguaje, guárdalo con `recordar` usando la clave "nombre" o "lenguaje".""",
    tools=[recordar],
)
