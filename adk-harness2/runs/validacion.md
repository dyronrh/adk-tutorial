# Validación antes / después

Modelo: `gemini-2.5-flash` · 3 repeticiones por tarea · antes=`mi_agente` · después=`agents/agente_mejorado`

| Tarea | Antes | Después |
|---|---|---|
| vista-conciliacion-marzo | 0/3 | 3/3 |
| vista-conciliacion-abril | 0/3 | 3/3 |
| holdout-mayo-fx910 | 0/3 | 0/3 |
| holdout-junio-sin-abonos | 0/3 | 3/3 |
| holdout-julio-solo-usd | 0/3 | 3/3 |

- Tareas vistas por Harness²: antes 0 → después 6 de 6
- Tareas nuevas (holdout):   antes 0 → después 6 de 9

Si mejora en las vistas pero no en el holdout, el harness se sobreajustó a esas tareas.

## Detalle

### vista-conciliacion-marzo · ANTES

```
esperado: 'Total USD: 480.24\nAbonos: 2'
run 1: 'Total USD: 568.83\nAbonos: 0' ❌
run 2: 'Total USD: 568.83\nAbonos: 0' ❌
run 3: 'Total USD: 568.83\nAbonos: 0' ❌
```

### vista-conciliacion-marzo · DESPUÉS

```
esperado: 'Total USD: 480.24\nAbonos: 2'
run 1: 'Total USD: 480.24\nAbonos: 2' ✅
run 2: 'Total USD: 480.24\nAbonos: 2' ✅
run 3: 'Total USD: 480.24\nAbonos: 2' ✅
```

### vista-conciliacion-abril · ANTES

```
esperado: 'Total USD: 270.00\nAbonos: 2'
run 1: 'Total USD: 324.44\nAbonos: 0' ❌
run 2: 'Total USD: 324.44\nAbonos: 0' ❌
run 3: 'Total USD: 324.44\nAbonos: 0' ❌
```

### vista-conciliacion-abril · DESPUÉS

```
esperado: 'Total USD: 270.00\nAbonos: 2'
run 1: 'Total USD: 270.00\nAbonos: 2' ✅
run 2: 'Total USD: 270.00\nAbonos: 2' ✅
run 3: 'Total USD: 270.00\nAbonos: 2' ✅
```

### holdout-mayo-fx910 · ANTES

```
esperado: 'Total USD: 412.40\nAbonos: 1'
run 1: 'Total USD: 517.96\nAbonos: 0' ❌
run 2: 'Total USD: 517.96\nAbonos: 0' ❌
run 3: 'Total USD: 517.96\nAbonos: 0' ❌
```

### holdout-mayo-fx910 · DESPUÉS

```
esperado: 'Total USD: 412.40\nAbonos: 1'
run 1: 'Total USD: 395.56\nAbonos: 1' ❌
run 2: 'Total USD: 395.56\nAbonos: 1' ❌
run 3: 'Total USD: 395.56\nAbonos: 1\n```json\n{\n "skill": "conciliacion-tarjetas",\n "steps": [\n  {\n   "step": 1,\n   "description": "Load skill `conciliacion-tarjetas`.",\n   "tool_code": "print(default_api.load_skill(skill_name = \\"conciliacion-tarjetas\\"))",\n   "tool_output": "{\\"load_skill_response\\": {\\"frontmatter\\": {\\"description\\": \\"Procedimiento corporativo para conciliar extractos de tarjetas corporativas en CLP y USD.\\", \\"metadata\\": {}, \\"name\\": \\"conciliacion-tarjetas\\"}, \\"instructions\\": \\"# Conciliación de tarjetas corporativas\\\\n\\\\n1. En este espacio de trabajo, el tipo de cambio en `fx.txt` es 950 CLP por USD. Usa este valor.\\\\n2. Llama a `resumir_extracto` con `ledger.csv` y ese tipo de cambio (950).\\\\n3. Extrae `total_usd` y `abonos` del resultado.\\\\n4. Responde exactamente dos líneas: `Total USD: <total_usd>` y `Abonos: <abonos>`.\\", \\"skill_name\\": \\"conciliacion-tarjetas\\"}}"\n  },\n  {\n   "step": 2,\n   "description": "Call `resumir_extracto` with `ledger.csv` and the exchange rate (950) as specified in the skill instructions.",\n   "tool_code": "print(default_api.resumir_extracto(clp_por_usd = 950, ruta_csv = \\"ledger.csv\\"))",\n   "tool_output": "{\\"resumir_extracto_response\\": {\\"abonos\\": 1, \\"total_usd\\": \\"395.56\\"}}"\n  },\n  {\n   "step": 3,\n   "description": "Extract `total_usd` and `abonos` from the result and format the output as specified by the skill.",\n   "output": "Total USD: 395.56\\nAbonos: 1"\n  }\n ]\n}\n```' ❌
```

### holdout-junio-sin-abonos · ANTES

```
esperado: 'Total USD: 139.99\nAbonos: 0'
run 1: 'Total USD: 142.21\nAbonos: 0' ❌
run 2: 'Total USD: 142.21\nAbonos: 0' ❌
run 3: 'Total USD: 142.21\nAbonos: 0' ❌
```

### holdout-junio-sin-abonos · DESPUÉS

```
esperado: 'Total USD: 139.99\nAbonos: 0'
run 1: 'Total USD: 139.99\nAbonos: 0' ✅
run 2: 'Total USD: 139.99\nAbonos: 0' ✅
run 3: 'Total USD: 139.99\nAbonos: 0' ✅
```

### holdout-julio-solo-usd · ANTES

```
esperado: 'Total USD: 550.00\nAbonos: 2'
run 1: 'Total USD: 630.50\nAbonos: 0\n```' ❌
run 2: 'Total USD: 630.50\nAbonos: 0' ❌
run 3: 'Total USD: 630.50\nAbonos: 0' ❌
```

### holdout-julio-solo-usd · DESPUÉS

```
esperado: 'Total USD: 550.00\nAbonos: 2'
run 1: 'Total USD: 550.00\nAbonos: 2' ✅
run 2: 'Total USD: 550.00\nAbonos: 2' ✅
run 3: 'Total USD: 550.00\nAbonos: 2' ✅
```
