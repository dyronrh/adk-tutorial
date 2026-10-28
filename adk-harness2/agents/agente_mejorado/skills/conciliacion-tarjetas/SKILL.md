---
name: conciliacion-tarjetas
description: Procedimiento corporativo para conciliar extractos de tarjetas corporativas en CLP y USD.
---
# Conciliación de tarjetas corporativas

1. En este espacio de trabajo, el tipo de cambio en `fx.txt` es 950 CLP por USD. Usa este valor.
2. Llama a `resumir_extracto` con `ledger.csv` y ese tipo de cambio (950).
3. Extrae `total_usd` y `abonos` del resultado.
4. Responde exactamente dos líneas: `Total USD: <total_usd>` y `Abonos: <abonos>`.
