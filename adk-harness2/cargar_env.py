"""Carga el .env del proyecto en os.environ (como hace `adk run`). Lo exportado en la shell gana."""

import os
from pathlib import Path


def cargar_env(path: Path = Path(__file__).parent / ".env") -> list[str]:
    cargadas = []
    if not path.is_file():
        return cargadas
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        key, value = key.strip(), value.strip().strip("\"'")
        if key not in os.environ:
            os.environ[key] = value
            cargadas.append(key)
    return cargadas



cargar_env()
# El editor de Harness² corre en OpenCode; su proveedor `google/...` lee esta variable.
if os.environ.get("GOOGLE_API_KEY"):
    os.environ.setdefault("GOOGLE_GENERATIVE_AI_API_KEY", os.environ["GOOGLE_API_KEY"])
# Editor por defecto: Gemini con la misma API key (sin Vertex). Exporta otro si quieres.
# gemini-2.5-pro describía la composición sin escribir los archivos (agg1 quedaba = base).
os.environ.setdefault("HARNESS2_IMPROVER_MODEL", "google/gemini-3.1-pro-preview")
