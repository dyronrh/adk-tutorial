#!/usr/bin/env bash
# Abre adk web con los dos agentes (antes / despues) sobre una tarea de la demo.
#   ./demo_web/web.sh marzo     # el fallo (antes) y la primera victoria (despues)
#   ./demo_web/web.sh mayo      # despues usa 950 aunque fx.txt diga 910
set -euo pipefail
DEMO="$(cd "$(dirname "$0")" && pwd)"
TAREA="${1:-marzo}"
PORT="${PORT:-8000}"
source "${VENV:-$HOME/harness2/.venv}/bin/activate"  # harness2 + google-adk 2.13
python "$DEMO/probar.py" --solo-preparar > /dev/null  # recopia los agentes y escribe las tareas
cd "$DEMO/tareas/$TAREA"  # las tools abren ledger.csv relativo a esta carpeta
echo "Tarea: $TAREA ($(cat fx.txt)) · elige 'antes' o 'despues' y pega este prompt:"
echo
cat "$DEMO/prompt.txt"
echo
exec adk web --port "$PORT" "$DEMO/agentes"
