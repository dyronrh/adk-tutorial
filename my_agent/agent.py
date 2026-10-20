from google.adk.agents.llm_agent import Agent

def get_current_time(city: str) -> dict:
    """Returns the current time in a city."""
    return {"status": "success", "city": city, "time": "10:30 AM"}

root_agent = Agent(
    model="gemini-flash-latest",
    name="root_agent",
    description="Tells the current time in a city.",
    instruction="You are a helpful assistant. When asked for the time in a city, use the get_current_time tool.",
    tools=[get_current_time],
)
