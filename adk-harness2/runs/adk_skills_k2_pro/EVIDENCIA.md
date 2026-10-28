# Evidencia: Harness² mejorando un agente de Google ADK

Cada candidato es un árbol de archivos (prompt, guardrails, memoria, tools). `harness_compiler.build_agent` lo convierte en un `LlmAgent`. Abajo, por tarea: qué cambió cada candidato, cómo quedó la instrucción y las tools de ADK, y qué entregó.

> ⚠️ **Sesiones del editor fallidas** (esos candidatos quedaron iguales a la base):

> - `agg1`: rc=0: empty reply
> - `agg2`: rc=0: empty reply
> - `inv2`: rc=0: empty reply

## Tarea `conciliacion-marzo` — corrida `adk_conciliacion-oc-agg2`

Respuesta correcta (solo para este reporte; Harness² **no** la ve):

```
Total USD: 480.24
Abonos: 2
```

| Candidato | Archivos que cambió | Tools ADK resultantes | Entregable | ¿Correcto? |
|---|---|---|---|---|
| **base** | — | resumir_extracto | `Total USD: 568.83 / Abonos: 0` | ❌ |
| **inv1** | `scripts/resumir_extracto.py`, `skills/conciliacion-tarjetas/SKILL.md` | resumir_extracto | `Total USD: 480.24 / Abonos: 2` | ✅ |
| **inv2** | `scripts/resumir_extracto.py`, `skills/conciliacion-tarjetas/SKILL.md` | resumir_extracto | `Total USD: 480.24 / Abonos: 2 / ```json / { /  "skill": "conciliacion-tarjetas", /  "tool_code": "print(default_api.resumir_extracto(clp_por_usd = 950, ruta_csv = \"ledger.csv\"))" / } / ```` | ❌ |
| **dom1** | `scripts/resumir_extracto.py`, `skills/conciliacion-tarjetas/SKILL.md` | resumir_extracto | `Total USD: 480.24 / Abonos: 2` | ✅ |
| **dom2** | `scripts/resumir_extracto.py`, `skills/conciliacion-tarjetas/SKILL.md` | resumir_extracto | `Total USD: 480.24 / Abonos: 2` | ✅ |
| **agg1** | — | resumir_extracto | `Total USD: 568.83 / Abonos: 0` | ❌ |
| **agg2** | — | resumir_extracto | `Total USD: 568.83 / Abonos: 0` | ❌ |

### conciliacion-marzo · inv1: cambios propuestos

> Nota del editor: - `scripts/resumir_extracto.py`: In `base1.md` and `base2.md` at `[ACTION] resumir_extracto`, the script returned `{'total_usd': '568.83'}` because it filtered out negative amounts (abonos) and didn't count them. I updated the script to include all amounts in the net total and return the abonos count.
- `skills/conciliacion-tarjetas/SKILL.md`: In `base1.md` and `base2.md` at `[OBSERVATION]` after loading the skill, the instructions forced the agent to use 900 CLP/USD and hardcode `Abonos: 0`. I replaced these with the verified workspace fact (exchange rate is 950 from `fx.txt`) and updated the prompt to report the actual abonos count computed by the script.

**`scripts/resumir_extracto.py`**

```diff
--- base/scripts/resumir_extracto.py
+++ candidato/scripts/resumir_extracto.py
@@ -6,7 +6,7 @@
 
 
 def resumir_extracto(ruta_csv: str, clp_por_usd: float) -> dict:
-    """Suma los cargos del extracto de la tarjeta corporativa, convirtiendo CLP a USD.
+    """Calcula el neto del extracto (cargos y abonos) en USD y cuenta los abonos.
 
     Args:
       ruta_csv: ruta al CSV del extracto (columnas date, description, amount, currency).
@@ -17,10 +17,11 @@
     tasa = Decimal(str(clp_por_usd))
     total = sum(
         (Decimal(r["amount"]) / (tasa if r["currency"] == "CLP" else 1)
-         for r in filas if Decimal(r["amount"]) > 0),
+         for r in filas),
         Decimal(0),
     )
-    return {"total_usd": f"{total:.2f}"}
+    abonos = sum(1 for r in filas if Decimal(r["amount"]) < 0)
+    return {"total_usd": f"{total:.2f}", "abonos": abonos}
 
 
 if __name__ == "__main__":  # CLI del harness: python3 scripts/resumir_extracto.py '{"arg": "valor"}'
```

**`skills/conciliacion-tarjetas/SKILL.md`**

```diff
--- base/skills/conciliacion-tarjetas/SKILL.md
+++ candidato/skills/conciliacion-tarjetas/SKILL.md
@@ -4,8 +4,7 @@
 ---
 # Conciliación de tarjetas corporativas
 
-1. Usa el tipo de cambio corporativo vigente: **900 CLP por USD** (circular de finanzas, enero 2026).
-2. Llama a `resumir_extracto` con `ledger.csv` y ese tipo de cambio.
-3. Los abonos y notas de crédito los procesa tesorería en otro proceso: no forman parte de esta
-   conciliación. Reporta siempre `Abonos: 0`.
-4. Responde exactamente dos líneas: `Total USD: <total>` y `Abonos: <cantidad>`.
+In this workspace, the exchange rate in `fx.txt` is **950** CLP por USD.
+
+1. Llama a `resumir_extracto` con `ledger.csv` y ese tipo de cambio.
+2. Responde exactamente dos líneas: `Total USD: <total_usd>` y `Abonos: <abonos>`.
```

**Lo que recibe ADK** (instrucción compuesta, diff contra la base):

```diff

```

**Tools del `LlmAgent`:**

- `resumir_extracto(ruta_csv, clp_por_usd)` — Calcula el neto del extracto (cargos y abonos) en USD y cuenta los abonos.
- `load_skill(skill_name)` — SkillToolset nativo de ADK: ['conciliacion-tarjetas']

### conciliacion-marzo · inv2: cambios propuestos

> Nota del editor: - `skills/conciliacion-tarjetas/SKILL.md`: In both `base1.md` and `base2.md`, the agent blindly followed the outdated skill instructions to use a 900 CLP exchange rate and report `Abonos: 0`, which contradicted the task and `fx.txt`. I updated it to declare the verified workspace fact (exchange rate is 950 CLP from `fx.txt`) and request the actual values.
- `scripts/resumir_extracto.py`: In both `base1.md` and `base2.md`, the agent called `resumir_extracto`, but the script was hardcoded to filter out negative amounts (`> 0`). I modified it to sum all amounts for the net total and to count the number of abonos (`< 0`) to support the task's requirements.

**`scripts/resumir_extracto.py`**

```diff
--- base/scripts/resumir_extracto.py
+++ candidato/scripts/resumir_extracto.py
@@ -6,7 +6,7 @@
 
 
 def resumir_extracto(ruta_csv: str, clp_por_usd: float) -> dict:
-    """Suma los cargos del extracto de la tarjeta corporativa, convirtiendo CLP a USD.
+    """Calcula el neto y los abonos del extracto de la tarjeta corporativa en USD.
 
     Args:
       ruta_csv: ruta al CSV del extracto (columnas date, description, amount, currency).
@@ -17,10 +17,11 @@
     tasa = Decimal(str(clp_por_usd))
     total = sum(
         (Decimal(r["amount"]) / (tasa if r["currency"] == "CLP" else 1)
-         for r in filas if Decimal(r["amount"]) > 0),
+         for r in filas),
         Decimal(0),
     )
-    return {"total_usd": f"{total:.2f}"}
+    abonos = sum(1 for r in filas if Decimal(r["amount"]) < 0)
+    return {"neto_usd": f"{total:.2f}", "cantidad_abonos": abonos}
 
 
 if __name__ == "__main__":  # CLI del harness: python3 scripts/resumir_extracto.py '{"arg": "valor"}'
```

**`skills/conciliacion-tarjetas/SKILL.md`**

```diff
--- base/skills/conciliacion-tarjetas/SKILL.md
+++ candidato/skills/conciliacion-tarjetas/SKILL.md
@@ -4,8 +4,6 @@
 ---
 # Conciliación de tarjetas corporativas
 
-1. Usa el tipo de cambio corporativo vigente: **900 CLP por USD** (circular de finanzas, enero 2026).
+1. In this workspace, the exchange rate in `fx.txt` is **950 CLP por USD**. Usa este tipo de cambio.
 2. Llama a `resumir_extracto` con `ledger.csv` y ese tipo de cambio.
-3. Los abonos y notas de crédito los procesa tesorería en otro proceso: no forman parte de esta
-   conciliación. Reporta siempre `Abonos: 0`.
-4. Responde exactamente dos líneas: `Total USD: <total>` y `Abonos: <cantidad>`.
+3. Responde exactamente dos líneas: `Total USD: <neto>` y `Abonos: <cantidad>`.
```

**Lo que recibe ADK** (instrucción compuesta, diff contra la base):

```diff

```

**Tools del `LlmAgent`:**

- `resumir_extracto(ruta_csv, clp_por_usd)` — Calcula el neto y los abonos del extracto de la tarjeta corporativa en USD.
- `load_skill(skill_name)` — SkillToolset nativo de ADK: ['conciliacion-tarjetas']

### conciliacion-marzo · dom1: cambios propuestos

> Nota del editor: - `context/harness/scripts/resumir_extracto.py`: In `base1.md` and `base2.md` at `[ACTION] resumir_extracto({'clp_por_usd': 900, 'ruta_csv': 'ledger.csv'})`, the script returned `{'total_usd': '568.83'}` by summing only positive amounts and ignoring the task's requirement for a net total and a count of abonos. I updated it to calculate both the net total (`total_usd`) and the count of negative movements (`cantidad_abonos`).
- `context/harness/skills/conciliacion-tarjetas/SKILL.md`: In `base1.md` and `base2.md` at `[OBSERVATION]` after `load_skill`, the skill's instructions incorrectly told the agent to hardcode `900 CLP por USD` and always report `Abonos: 0`. The task specified the FX is in `fx.txt` (which is 950) and to report the count of abonos. I updated the skill with the workspace fact that FX is 950 CLP/USD and instructed it to use the updated `resumir_extracto` outputs to report both lines accurately.

**`scripts/resumir_extracto.py`**

```diff
--- base/scripts/resumir_extracto.py
+++ candidato/scripts/resumir_extracto.py
@@ -6,7 +6,7 @@
 
 
 def resumir_extracto(ruta_csv: str, clp_por_usd: float) -> dict:
-    """Suma los cargos del extracto de la tarjeta corporativa, convirtiendo CLP a USD.
+    """Calcula el total neto (cargos y abonos) del extracto y la cantidad de abonos.
 
     Args:
       ruta_csv: ruta al CSV del extracto (columnas date, description, amount, currency).
@@ -15,15 +15,19 @@
     with open(ruta_csv) as f:
         filas = list(csv.DictReader(f))
     tasa = Decimal(str(clp_por_usd))
-    total = sum(
-        (Decimal(r["amount"]) / (tasa if r["currency"] == "CLP" else 1)
-         for r in filas if Decimal(r["amount"]) > 0),
-        Decimal(0),
-    )
-    return {"total_usd": f"{total:.2f}"}
+    total_neto = Decimal(0)
+    abonos_count = 0
+    for r in filas:
+        amt = Decimal(r["amount"])
+        usd_amt = amt / (tasa if r["currency"] == "CLP" else Decimal(1))
+        total_neto += usd_amt
+        if amt < 0:
+            abonos_count += 1
+            
+    return {"total_usd": f"{total_neto:.2f}", "cantidad_abonos": abonos_count}
 
 
-if __name__ == "__main__":  # CLI del harness: python3 scripts/resumir_extracto.py '{"arg": "valor"}'
+if __name__ == "__main__":
     import json, sys
     out = resumir_extracto(**json.loads(sys.argv[1] if len(sys.argv) > 1 else "{}"))
     print(json.dumps(out, ensure_ascii=False, default=str))
```

**`skills/conciliacion-tarjetas/SKILL.md`**

```diff
--- base/skills/conciliacion-tarjetas/SKILL.md
+++ candidato/skills/conciliacion-tarjetas/SKILL.md
@@ -4,8 +4,7 @@
 ---
 # Conciliación de tarjetas corporativas
 
-1. Usa el tipo de cambio corporativo vigente: **900 CLP por USD** (circular de finanzas, enero 2026).
-2. Llama a `resumir_extracto` con `ledger.csv` y ese tipo de cambio.
-3. Los abonos y notas de crédito los procesa tesorería en otro proceso: no forman parte de esta
-   conciliación. Reporta siempre `Abonos: 0`.
-4. Responde exactamente dos líneas: `Total USD: <total>` y `Abonos: <cantidad>`.
+1. En este workspace, el tipo de cambio es de 950 CLP por USD (verificado en fx.txt). Usa este valor.
+2. Llama a `resumir_extracto` con `ledger.csv` y ese tipo de cambio (950).
+3. La herramienta `resumir_extracto` ahora calcula el neto (cargos más abonos) y cuenta los abonos automáticamente.
+4. Responde exactamente dos líneas con los resultados: `Total USD: <total_usd>` y `Abonos: <cantidad_abonos>`.
```

**Lo que recibe ADK** (instrucción compuesta, diff contra la base):

```diff

```

**Tools del `LlmAgent`:**

- `resumir_extracto(ruta_csv, clp_por_usd)` — Calcula el total neto (cargos y abonos) del extracto y la cantidad de abonos.
- `load_skill(skill_name)` — SkillToolset nativo de ADK: ['conciliacion-tarjetas']

### conciliacion-marzo · dom2: cambios propuestos

> Nota del editor: - `skills/conciliacion-tarjetas/SKILL.md`: En `base1.md`, el agente ejecutó `[ACTION] resumir_extracto({'clp_por_usd': 900...})` y devolvió `Abonos: 0` debido a reglas hardcodeadas. Se reemplazaron por el "workspace fact" de que la tasa (de fx.txt) es 950 y que los abonos sí se concilian.
- `scripts/resumir_extracto.py`: En `base1.md`, la herramienta devolvió `{'total_usd': '568.83'}` porque el código filtraba `if Decimal(r["amount"]) > 0`. Se corrigió el script para sumar todos los movimientos (neto) y devolver simultáneamente la cantidad de `abonos`.

**`scripts/resumir_extracto.py`**

```diff
--- base/scripts/resumir_extracto.py
+++ candidato/scripts/resumir_extracto.py
@@ -6,7 +6,7 @@
 
 
 def resumir_extracto(ruta_csv: str, clp_por_usd: float) -> dict:
-    """Suma los cargos del extracto de la tarjeta corporativa, convirtiendo CLP a USD.
+    """Calcula el total neto y cuenta los abonos del extracto de la tarjeta corporativa, convirtiendo CLP a USD.
 
     Args:
       ruta_csv: ruta al CSV del extracto (columnas date, description, amount, currency).
@@ -15,12 +15,15 @@
     with open(ruta_csv) as f:
         filas = list(csv.DictReader(f))
     tasa = Decimal(str(clp_por_usd))
-    total = sum(
-        (Decimal(r["amount"]) / (tasa if r["currency"] == "CLP" else 1)
-         for r in filas if Decimal(r["amount"]) > 0),
-        Decimal(0),
-    )
-    return {"total_usd": f"{total:.2f}"}
+    total = Decimal(0)
+    abonos = 0
+    for r in filas:
+        amt = Decimal(r["amount"])
+        if amt < 0:
+            abonos += 1
+        valor_usd = amt / (tasa if r["currency"] == "CLP" else 1)
+        total += valor_usd
+    return {"total_usd": f"{total:.2f}", "abonos": abonos}
 
 
 if __name__ == "__main__":  # CLI del harness: python3 scripts/resumir_extracto.py '{"arg": "valor"}'
```

**`skills/conciliacion-tarjetas/SKILL.md`**

```diff
--- base/skills/conciliacion-tarjetas/SKILL.md
+++ candidato/skills/conciliacion-tarjetas/SKILL.md
@@ -4,8 +4,7 @@
 ---
 # Conciliación de tarjetas corporativas
 
-1. Usa el tipo de cambio corporativo vigente: **900 CLP por USD** (circular de finanzas, enero 2026).
+1. En este workspace, el tipo de cambio corporativo en fx.txt es **950 CLP por USD**.
 2. Llama a `resumir_extracto` con `ledger.csv` y ese tipo de cambio.
-3. Los abonos y notas de crédito los procesa tesorería en otro proceso: no forman parte de esta
-   conciliación. Reporta siempre `Abonos: 0`.
-4. Responde exactamente dos líneas: `Total USD: <total>` y `Abonos: <cantidad>`.
+3. En este workspace, los abonos y notas de crédito (montos negativos) sí forman parte de la conciliación. El script calculará el neto correcto y la cantidad de abonos.
+4. Responde exactamente dos líneas con los resultados del script: `Total USD: <total_usd>` y `Abonos: <abonos>`.
```

**Lo que recibe ADK** (instrucción compuesta, diff contra la base):

```diff

```

**Tools del `LlmAgent`:**

- `resumir_extracto(ruta_csv, clp_por_usd)` — Calcula el total neto y cuenta los abonos del extracto de la tarjeta corporativa, convirtiendo CLP a USD.
- `load_skill(skill_name)` — SkillToolset nativo de ADK: ['conciliacion-tarjetas']

### conciliacion-marzo: selección

- elegido: **agg1** (¿es la base? False)
- por qué: Both candidates are identical, but both fail on FIDELITY (ignoring the 950 FX rate in fx.txt and the negative abonos). I selected candidate A by default. Runner-up B was rejected because it shares the exact same calculation errors and zero count for abonos, offering no improvements.

> Las tareas siguientes repiten el mismo patrón de diffs; abajo va solo su tabla. Los árboles completos están en `runs/<corrida>/<tarea>/harnesses/`.

## Tarea `conciliacion-abril` — corrida `adk_conciliacion-oc-agg2`

Respuesta correcta (solo para este reporte; Harness² **no** la ve):

```
Total USD: 270.00
Abonos: 2
```

| Candidato | Archivos que cambió | Tools ADK resultantes | Entregable | ¿Correcto? |
|---|---|---|---|---|
| **base** | — | resumir_extracto | `Total USD: 324.44 / Abonos: 0` | ❌ |
| **inv1** | `scripts/resumir_extracto.py`, `skills/conciliacion-tarjetas/SKILL.md` | resumir_extracto | `Total USD: 270.00 / Abonos: 2` | ✅ |
| **inv2** | — | resumir_extracto | `Total USD: 324.44 / Abonos: 0` | ❌ |
| **dom1** | `scripts/resumir_extracto.py`, `skills/conciliacion-tarjetas/SKILL.md` | resumir_extracto | `Total USD: 270.00 / Abonos: 2` | ✅ |
| **dom2** | `scripts/resumir_extracto.py`, `skills/conciliacion-tarjetas/SKILL.md` | resumir_extracto | `Total USD: 270.00 / Abonos: 2` | ✅ |
| **agg1** | `scripts/resumir_extracto.py`, `skills/conciliacion-tarjetas/SKILL.md` | resumir_extracto | `Total USD: 270.00 / Abonos: 2` | ✅ |
| **agg2** | `scripts/resumir_extracto.py`, `skills/conciliacion-tarjetas/SKILL.md` | resumir_extracto | `Total USD: 270.00 / Abonos: 2` | ✅ |

### conciliacion-abril: selección

- elegido: **agg2** (¿es la base? False)
- por qué: Both candidates are functionally identical and correctly satisfy all instructions, accurately calculating the net total (270.00 USD) and identifying the two abonos. They perfectly match the requested CONFORMANCE and FIDELITY. Since the artifacts are indistinguishable in their content, Candidate A is chosen arbitrarily over Candidate B.
