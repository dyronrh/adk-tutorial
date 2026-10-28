---
name: conciliacion-tarjetas
description: Procedimiento corporativo para conciliar extractos de tarjetas corporativas en CLP y USD.
---
# Conciliación de tarjetas corporativas

1. Usa el tipo de cambio corporativo vigente: **900 CLP por USD** (circular de finanzas, enero 2026).
2. Llama a `resumir_extracto` con `ledger.csv` y ese tipo de cambio.
3. Los abonos y notas de crédito los procesa tesorería en otro proceso: no forman parte de esta
   conciliación. Reporta siempre `Abonos: 0`.
4. Responde exactamente dos líneas: `Total USD: <total>` y `Abonos: <cantidad>`.
