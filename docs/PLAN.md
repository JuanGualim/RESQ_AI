# RESQ AI — Plan por fases del equipo

**Open Agent Hackathon 2026 · Track 3: Reasoning Architecture**
Versión 2 · viernes 23 de octubre de 2026 (reparto ajustado a las máquinas del equipo) · horas en **hora de Guatemala (UTC-6)**
Entrega: **martes 27 de octubre, 17:45** (límite duro). Meta interna: **martes 27, 12:00**.

> El documento vivo del proyecto es `AGENTS.md` en el repo. Este plan es la referencia de fases y reparto; si algo cambia, se anota primero en `AGENTS.md` (sección "Registro de decisiones").

---

## 1. Qué vamos a construir

**En una frase:** RESQ AI ayuda a un coordinador municipal de emergencias a decidir cómo distribuir ayuda durante una inundación. Combina datos de comunidades, albergues, carreteras, lluvia y reportes de campo contradictorios, prioriza con reglas de protocolo y entrega un plan de distribución que se replantea solo cuando cambia la realidad, explicando por qué cambió.

| Pieza | Definición |
| --- | --- |
| Usuario | Coordinador de emergencias de un municipio (COE municipal) |
| Decisión | Qué comunidades atender primero, con qué recursos, desde qué bodega o albergue, con qué vehículo y por qué ruta |
| Salida | Plan versionado (v1, v2, …): asignaciones con prioridad, ruta, razón y evidencia; cuando hay replan, qué cambió y por qué |
| Momento WOW | En vivo se bloquea una carretera (botón en la UI). Los agentes concilian reportes, replanifican, el crítico valida y el reporte explica el cambio |

### Por qué Track 3

| Lo que pide el track | Cómo lo cumple RESQ AI |
| --- | --- |
| Datos | Comunidades, albergues, bodegas, carreteras, vehículos, reportes y lluvia, consultados en Zetaris |
| Conocimiento | Reglas de prioridad del protocolo (vulnerabilidad, niños y adultos mayores, capacidad) |
| Memoria / estado | World Model (Meterless): estado compartido y eventos; plan anterior para comparar |
| Razonamiento | Conciliador, analista, planificador y crítico que se revisan entre sí |
| Decisiones y acciones confiables | Plan validado por reglas duras en código; replan ante eventos; escalamiento a humano |

### Alcance

**Sí:** 1 municipio ficticio · 12–15 comunidades · 3–4 albergues · 2 bodegas · ~20 tramos de carretera como grafo · 5–8 vehículos · ~30 reportes de campo (algunos contradictorios) · lluvia real de Open-Meteo para coordenadas de referencia · 3 escenarios de prueba.

**No:** rutas GPS reales, datos reales de personas, modelos hidrológicos, app móvil, login o multiusuario.

---

## 2. Arquitectura

```text
Coordinador (UI Streamlit)
   │  pregunta  /  evento: "bloquear tramo T7"
   ▼
[Intake] ── clasifica la solicitud: situación · plan · evento · "¿por qué?"
   ▼
[Conciliador] ── reportes oficiales vs. brigadas vs. redes ──► hechos + confianza ──► World Model
   ▼
[Analista de riesgo] ── SQL en Zetaris ──► índice de riesgo por comunidad ──► World Model
   ▼
[Planificador] ── reglas + herramienta de rutas + capacidades ──► plan vN
   ▼
[Crítico] ── valida reglas duras (código) y razones (LLM)
   │   ✗ ──► devuelve al Planificador con observaciones (máx. 3 vueltas)
   │   ✗✗ sin solución o baja confianza ──► ESCALAR: "requiere decisión humana"
   ✓
[Explicador] ── plan final + diferencias con la versión anterior y su causa (eventos del World Model)

Servicios compartidos: Zetaris (datos) · World Model (estado + eventos) · Nightshift → Nemotron (modelos) · traza JSONL
```

**Principio de diseño: el LLM decide y explica; el código calcula.** Rutas más cortas, capacidades, inventario y validaciones duras son funciones deterministas. Los agentes razonan sobre sus resultados. Así el sistema es reproducible y no inventa rutas ni números.

### Agentes

| Agente | Qué hace | Modelo (lane) | Herramientas | Escribe en |
| --- | --- | --- | --- | --- |
| Intake | Clasifica la solicitud y elige el flujo | Rápido | Reglas o Scout Intent (opcional) | Traza |
| Conciliador | Decide el estado real de tramos y albergues cuando los reportes se contradicen, con confianza y justificación | Rápido | `run_sql` | World Model |
| Analista de riesgo | Calcula riesgo por comunidad: lluvia, elevación, vulnerabilidad, accesibilidad | Rápido | `run_sql` | World Model |
| Planificador | Asigna recursos, vehículos y rutas según reglas de prioridad | Profundo | `best_route`, inventario, capacidades | Plan |
| Crítico | Revisa reglas duras (capacidad, tramos bloqueados, comunidades críticas sin atender, vehículo apto) y que cada razón tenga evidencia | Profundo | Validadores en código | Observaciones / escalamiento |
| Explicador | Redacta el plan final y el "qué cambió y por qué" | Rápido | World Model (historial de eventos) | Reporte |

Lanes de Nightshift (corre en la máquina de Harry): **rápido** = `nvidia/nemotron-3.5-lightning-30b-a3b` (verificado) · **profundo** = un Nemotron super (por confirmar cuál responde con nuestra cuenta).

### Tecnología de sponsors

| Sponsor | Papel en RESQ AI | Obligatorio |
| --- | --- | --- |
| Zetaris | Única fuente de datos: Postgres del escenario registrado en Zetaris + API de Open-Meteo como tabla REST, todo vía SQL | Sí |
| Meterless World Model | Estado compartido de comunidades, tramos y albergues; cada cambio es un evento; el historial explica los replanes | Sí (engine) |
| Meterless Nightshift | Proveedor principal de IA de la app (API compatible con OpenAI) | Sí |
| Cursor | Entorno de desarrollo de los 3 | Sí |
| NVIDIA Nemotron | Modelos de los lanes, servidos por Nightshift. Opta al premio DGX Spark | Recomendado |
| H-MEM / Scout Intent | Lecciones de emergencias anteriores / clasificación de solicitudes | Opcional, solo si sobra tiempo |

### Datos del escenario

Viven en un **Postgres propio** (contenedor Docker en la máquina de Juan) registrado como fuente en Zetaris, porque Zetaris no lee CSV de la laptop. Se generan con `scripts/generate_data.py` (semilla fija) y se guarda una copia en `data/sample/` para el modo sin servicios (`SAMPLE_MODE`).

| Tabla | Columnas principales |
| --- | --- |
| `comunidades` | id, nombre, poblacion, pct_ninos, pct_adultos_mayores, vulnerabilidad (1–5), elevacion_m, lat, lon, nodo_vial |
| `albergues` | id, nombre, capacidad, ocupacion_actual, nodo_vial |
| `bodegas` / `inventario` | id, nombre, nodo_vial / bodega_id, recurso, cantidad |
| `tramos` | id, origen, destino, distancia_km, superficie, estado_oficial |
| `vehiculos` | id, tipo, capacidad_kg, puede_vadear, bodega_id |
| `reportes_campo` | id, timestamp, fuente (oficial · brigada · redes), objeto_tipo, objeto_id, estado_reportado, detalle |
| `lluvia` (REST, Open-Meteo) | fecha_hora, precipitacion_mm |
| `docs/protocolo.md` | Reglas de prioridad (conocimiento del dominio) |

Las contradicciones se **siembran a propósito** (ej.: el reporte oficial dice "T7 abierto", dos brigadas dicen "T7 inundado"). El agente debe descubrirlas; nunca se escriben resultados en el código.

---

## 3. Equipo y responsabilidades

El reparto sigue las máquinas de cada uno:

- **Juan** usa Linux, así que no puede correr Nightshift. Desarrolla con NVIDIA directo.
- **Harry** tiene Windows y el mejor equipo. Es host de Nightshift, se encarga de las pruebas pesadas y de la demo.
- **Chema** Le tocan piezas deterministas, pequeñas y bien definidas, que se prueban con `pytest` y `SAMPLE_MODE`, sin Docker, sin Zetaris local y sin Nightshift local.

| Integrante | Máquina | Rol | Dueño de |
| --- | --- | --- | --- |
| **Juan** | EndeavourOS (Linux) · host de **Zetaris** | Datos, estado e integración (líder técnico) | Zetaris encendido en las sesiones · Postgres del escenario · `scripts/generate_data.py` · `data/sample/` · tabla Open-Meteo · `run_sql` · `SAMPLE_MODE` · **World Model** (servicio + cliente Python + conformance) · agentes **Conciliador** y **Analista de riesgo** · `config.py` · revisión de PRs · `AGENTS.md` · README final · **sube la entrega a HackOS** |
| **Harry** | Windows, equipo potente · host de **Nightshift** | Agentes, modelos y pruebas pesadas | Nightshift, sus lanes y su exposición por Tailscale · `resq/llm.py` · `schemas.py` · grafo LangGraph · `run.py` · agentes **Planificador**, **Crítico** y **Explicador** · ciclo crítico y escalamiento · traza JSONL · **batería de pruebas de punta a punta con Nightshift** · instalación desde cero en Windows · evidencia de Nemotron · `output_examples/` · máquina de la demo · **grabación del video** |
| **Chema** | Windows | Herramientas deterministas, UI y comunicación | `docs/protocolo.md` · `resq/tools/routing.py` (`best_route`) + pruebas · `resq/tools/validators.py` + pruebas · agente **Intake** (por reglas) · UI Streamlit sobre datos de ejemplo · `input_examples/` · prueba de instalación en `SAMPLE_MODE` en su equipo · guion del video · slide deck · borrador del README de uso |

Todos: probar escenarios, revisar el guion de la demo y actualizar `AGENTS.md` al cerrar cada sesión.

**Por qué este reparto:**

- Chema trabaja casi todo en local con funciones puras y datos de `data/sample/`, así que su máquina nunca carga Docker, Zetaris ni modelos. Sus piezas son críticas (rutas y validadores), pero tienen especificación cerrada y pruebas, y Juan las revisa.
- Harry concentra lo que necesita Nightshift cerca: prompts, ciclo del crítico, pruebas repetidas, medición de latencia y la demo en vivo, que obligatoriamente usa Nightshift.
- Juan concentra lo que vive junto a Zetaris (datos y agentes basados en SQL) y el World Model. El World Model corre en Node, que en Linux no tiene problemas, y no necesita Nightshift.

### Disponibilidad de hosts

| Servicio | Host | Cuándo debe estar encendido | Acceso del resto |
| --- | --- | --- | --- |
| Zetaris (UI `:3000`, REST `:8888`) | Juan | Bloques de trabajo acordados en el chat + toda la Fase 3–4 | Tailscale (IP de Juan) |
| Nightshift (`:8088/v1`) | Harry | Bloques de trabajo + pruebas + demo; laptop con corriente y sin suspensión | Tailscale. TODO(verificar): si Nightshift solo escucha en `127.0.0.1`, exponerlo con `tailscale serve` o `netsh interface portproxy` |
| World Model (servicio Node) | Quien ejecuta el agente (cada uno local) | Siempre que se corra el grafo | `WORLD_MODEL_URL=http://127.0.0.1:<puerto>` |

Si Nightshift no está disponible, todos desarrollan con NVIDIA directo, que solo se permite en desarrollo y se configura en `.env`.

---

## 4. Fases

**Regla de trabajo en paralelo:** nadie espera a nadie. Cada dueño publica **primero un stub** con el contrato de §5 (datos de ejemplo, World Model en memoria, `chat()` falso) y después lo reemplaza por la versión real sin cambiar la firma.

### Fase 0 — Arranque · viernes 23, hasta las 14:00

Objetivo: los tres con entorno funcionando, contratos acordados y R1 decidido.

- [ ] **Juan:** invitar colaboradores en GitHub · crear `docs/SETUP_EQUIPO.md`, que hoy se referencia pero **no existe** · Tailscale + exponer Zetaris · esqueleto de carpetas de §5 de `AGENTS.md` + `resq/config.py`
- [ ] **Juan:** correr *IMPLEMENT → Run the 90-second proof* del World Model en Linux y cerrar la decisión de R1 (ver §7)
- [ ] **Harry:** instalar Nightshift + proveedor NVIDIA · confirmar qué Nemotron *super* responde para el lane profundo · exponer por Tailscale · pasar URL y token **por privado** · desactivar suspensión
- [ ] **Chema:** Python 3.12 + venv + `requirements.txt` · `smoke_test.py` (Zetaris de Juan por Tailscale + modelo) · leer `AGENTS.md` · empezar `docs/protocolo.md`
- [ ] **Llamada de 45 min (~12:00):** confirmar esquema de datos y contratos de §5 y anotarlos en `AGENTS.md`

**Gate:** smoke test con 3 PASS en las 3 máquinas (Juan con NVIDIA directo; Harry y Chema con Nightshift), contratos escritos y R1 decidido.

### Fase 1 — MVP de punta a punta · viernes 23, 14:00 → sábado 24, 12:00

Objetivo: entra una pregunta, sale un plan v1 (feo pero real) con datos de Zetaris y Nemotron vía Nightshift.

| Quién | Tarea | Hito |
| --- | --- | --- |
| Juan | `generate_data.py` (semilla fija) → **`data/sample/` publicado primero**, porque desbloquea a todos | **vie 18:00** |
| Juan | Stub de `resq/world/` en memoria con el contrato real | vie 20:00 |
| Juan | Postgres + registro en Zetaris + `run_sql` + 10 consultas clave probadas | sáb 10:00 |
| Juan | World Model real (servicio Node) + cliente Python + **conformance en verde** | sáb 12:00 (puede pasar a sáb tarde) |
| Harry | `schemas.py` (contrato compartido) | **vie 18:00** |
| Harry | `llm.py`: lanes `fast`/`deep`, headers de Meterless, timeout de 90 s, máx. 2 reintentos | vie 22:00 |
| Harry | `graph.py` mínimo Analista → Planificador → Explicador + `run.py` + traza JSONL | sáb 12:00 |
| Chema | `docs/protocolo.md` cerrado (reglas de prioridad numeradas, para citarlas como evidencia) | vie 20:00 |
| Chema | `best_route` (networkx sobre `tramos`; omite tramos bloqueados y tramos inundados para vehículos que no vadean) + `tests/test_routing.py` | sáb 12:00 |

**Gate (sáb 24, 12:00):** `python -m resq.run --pregunta "..."` imprime un plan v1 con rutas válidas, ya sea con datos de Zetaris o con `SAMPLE_MODE`.

### Fase 2 — Sistema multiagente real · sábado 24, 12:00 → domingo 25, 22:00

Objetivo: el comportamiento que premian los jueces.

- [ ] **Chema:** `validators.py` + pruebas: capacidad del vehículo, inventario suficiente, ruta sin tramos bloqueados, vehículo apto para el tramo, comunidades críticas sin atender, IDs que existen. **Primeras 4 reglas antes del sáb 18:00**, porque el Crítico depende de ellas
- [ ] **Chema:** agente Intake por reglas + pruebas · UI Streamlit v1 sobre `output_examples/` (mapa esquemático de nodos y tramos, tabla del plan, panel de traza)
- [ ] **Harry:** Crítico (validadores de Chema + revisión LLM de razones y evidencia) · ciclo de máx. 3 vueltas · rama de escalamiento · replan disparado por evento · `cambios_vs_anterior` a partir de `world.history()`
- [ ] **Harry:** publicar 2–3 planes reales en `output_examples/` para la UI de Chema (sáb 20:00)
- [ ] **Juan:** Conciliador y Analista de riesgo con SQL real · reportes contradictorios sembrados · tabla Open-Meteo · 3 escenarios de prueba · `SAMPLE_MODE` completo · World Model como estado compartido de todos los agentes
- [ ] **Check-in sáb 24, 20:00 (20 min):** "si entregáramos mañana, ¿qué fallaría?"
- [ ] **Harry, dom 25 tarde, primera prueba pesada:** 3 escenarios × 5 corridas con Nightshift. Registrar latencia por agente, vueltas del crítico, fallos y escalamientos en `logs/`, y compartir un resumen

**Gate (dom 25, 22:00):** bloquear 2 tramos distintos produce 2 replanes distintos y correctos, con la traza del ciclo del crítico, y la prueba pesada no muestra fallos sin explicación.

### Fase 3 — Producto y confiabilidad · lunes 26, hasta las 14:00

- [ ] **Harry + Chema (en pareja, en la máquina de Harry):** conectar la UI al grafo real (botón "bloquear tramo", panel "¿por qué cambió?")
- [ ] **Harry:** timeouts, reintentos acotados y errores honestos · lane Nemotron fijo y capturas de los logs de Nightshift · **segunda prueba pesada** (3 escenarios × 10 corridas + ambos eventos) · instalación desde cero en Windows en modo completo · generar `output_examples/` finales
- [ ] **Chema:** pulir la UI · **instalación desde cero en `SAMPLE_MODE` en su equipo**, que prueba que un juez con windows puede correrlo · borrador del README (instalación y uso) · `input_examples/`
- [ ] **Juan:** `data/README.md` · revisar que se cumplan las 8 reglas de §2 de `AGENTS.md` · buscar secretos en todo el historial de git (`git log -p | grep -E "nvapi-|Bearer "`) · arreglar errores e integrar PRs
- [ ] Solo si sobra tiempo: H-MEM o Scout Intent

**Lunes 26, 14:00: CONGELAR FUNCIONES.** Desde aquí solo se corrigen errores.

### Fase 4 — Empaquetar y entregar · lunes 26, 14:00 → martes 27, 12:00

- [ ] **Lun 16:00, ensayo de demo completo** en la máquina de Harry (Nightshift local + Zetaris de Juan por Tailscale), siguiendo el guion de §8. Los 3 conectados
- [ ] **Harry:** grabar el video el lunes en la noche (y una **grabación de respaldo** del flujo completo por si la red falla) · capturas para el deck · editar el video
- [ ] **Chema:** slide deck (herramienta en el navegador, nada pesado) · guion final del video · revisar que el README se entienda sin contexto
- [ ] **Juan:** README final, explicación de sponsors, declaración de componentes previos, `.env.example`, última revisión de la checklist de §9
- [ ] **Martes 27, 12:00: Juan sube todo a HackOS.** De 12:00 a 17:45 es solo colchón para emergencias

---

## 5. Contratos entre partes

Para trabajar en paralelo sin pisarse. Cambiar un contrato = avisar al grupo y anotarlo en `AGENTS.md`.

```python
# resq/tools/zetaris.py  (Juan)
def run_sql(sql: str, limit: int = 500) -> list[dict]: ...   # una sentencia; lanza ZetarisError

# resq/llm.py  (Harry)
def chat(messages: list[dict], lane: str = "fast", tools: list | None = None) -> dict: ...  # lane: "fast" | "deep"

# resq/world/  (Juan)
def get_state() -> dict: ...                 # comunidades, tramos, albergues con su estado actual
def apply_event(event: dict) -> None: ...    # {"tipo": "tramo_bloqueado", "id": "T7", "fuente": ..., "ts": ...}
def history() -> list[dict]: ...             # eventos en orden

# resq/tools/routing.py  (Chema)
def best_route(origen: str, destino: str, state: dict, vehiculo: str) -> Route | None: ...

# resq/tools/validators.py  (Chema)
def validar_plan(plan: Plan, state: dict) -> list[str]: ...  # lista vacía = sin violaciones; cada texto cita IDs

# resq/schemas.py  (todos; Harry lo crea)
class Asignacion(BaseModel): comunidad_id; origen_id; recurso; cantidad; vehiculo_id; ruta: list[str]; prioridad: int; razon: str; evidencia: list[str]
class Plan(BaseModel): version: int; asignaciones: list[Asignacion]; sin_atender: list[str]; riesgos: list[str]; confianza: float; escalado: bool; cambios_vs_anterior: list[str]

# Nodos del grafo (cada dueño implementa el suyo)  (Harry define, todos usan)
def nodo_<agente>(state: ResqState) -> dict: ...   # devuelve solo los campos que actualiza

# resq/run.py  (Harry) — lo que llama la UI de Chema
def ejecutar(pregunta: str, evento: dict | None = None) -> dict: ...  # {"plan": Plan, "traza": list[dict], "escalado": bool}
```

---

## 6. Forma de trabajo

- **Ramas:** `feat/<area>-<tema>` → Pull Request a `main`; Juan revisa; se integra al menos una vez al día.
- **Check-ins diarios cortos (15 min):** 10:00 y 21:00. Cada quien dice qué terminó, qué sigue y qué lo bloquea.
- **Al cerrar cada sesión:** actualizar las secciones 8–10 de `AGENTS.md` (estado, próximos pasos y decisiones).
- **Bloqueos:** si alguien lleva más de 45 min trabado, avisa al grupo; si sigue, se pregunta en HackOS (#help desk, canal del sponsor o mentores).
- **Secretos:** nunca en el repo, chats públicos ni capturas. Tokens solo por mensaje privado.
- **Agentes de IA** (Cursor, Claude Code, Codex): leen `AGENTS.md` primero; cambios pequeños; correr pruebas antes de cada commit.
- **Máquinas host:** Zetaris (Juan) y Nightshift (Harry) encendidos en los bloques de trabajo acordados.
- **Equipo de Chema:** trabaja con `SAMPLE_MODE=true` y `pytest`. Las pruebas pesadas o largas se le piden a Harry.

---

## 7. Riesgos y plan B

| # | Riesgo | Plan B |
| --- | --- | --- |
| R1 | Los engines de Meterless están en TypeScript y el agente en Python. La conformance se corre con `WORLD_MODEL_IMPL=<index.ts> npx tsx conformance/runner.ts`, así que necesita una implementación en TS | **Recomendado: (b)** el World Model como servicio Node pequeño (implementación TS que pasa la conformance + HTTP con `get_state`/`apply_event`/`history`), que `resq/world/` llama desde Python. La alternativa (a), implementar en Python, obliga a escribir un adaptador TS para la conformance y es más trabajo. TODO(verificar): si basta con envolver la implementación `reference/` o los jueces esperan una propia generada con el prompt *IMPLEMENT* |
| R2 | Nightshift solo corre en la máquina de Harry, y Juan (Linux) no puede instalarlo | NVIDIA directo para desarrollo; la demo, la prueba pesada y el video se hacen en la máquina de Harry con Nightshift; laptop con corriente y sin suspensión |
| R3 | Zetaris o Nightshift no alcanzables por Tailscale | Revisar puertos y `tailscale serve`; mientras tanto, `SAMPLE_MODE` o NVIDIA directo |
| R4 | Zetaris no lee CSV locales | Postgres propio registrado como fuente |
| R5 | Los jueces no pueden levantar Zetaris + Nightshift | README claro, `SAMPLE_MODE`, video, `output_examples/` y trazas |
| R6 | El modelo inventa datos | Validaciones duras en código, crítico, toda asignación referencia IDs reales |
| R7 | El alcance crece | Gates por fase; congelar el lunes 14:00 |
| R8 | RAM de la máquina de Juan (Zetaris + Postgres + World Model) | Cerrar apps, zram activo, `docker compose stop` cuando no se use; el World Model es un proceso Node liviano |
| R9 | El equipo de Chema es limitado | Nada de Docker ni modelos locales; `SAMPLE_MODE` + `pytest`; integración en pareja en la máquina de Harry |
| R10 | La demo depende de 2 máquinas (Zetaris de Juan + Nightshift de Harry) y de la red | Ensayo el lun 16:00; grabación de respaldo; `SAMPLE_MODE` con Nightshift como plan C en vivo |
| R11 | Fase 1 tiene 3 frentes que dependen entre sí | Stubs con el contrato real desde el viernes (`data/sample/`, World Model en memoria, `schemas.py` a las 18:00) |

---

## 8. Guion del video (máx. 4 min)

Lo graba Harry en su máquina con Nightshift real. Chema escribe el guion final.

1. **0:00–0:30** — El problema: en una inundación los reportes se contradicen y los planes quedan viejos en minutos. Usuario: coordinador municipal.
2. **0:30–1:30** — Primer plan: riesgo por comunidad, asignaciones, rutas y la traza del crítico rechazando y corrigiendo algo.
3. **1:30–2:30** — WOW: se bloquea un tramo en vivo → conciliación → replan → "qué cambió y por qué".
4. **2:30–3:15** — Arquitectura y sponsors: Zetaris (SQL), World Model (eventos), Nightshift → Nemotron (logs del lane), Cursor.
5. **3:15–3:45** — Resultado para el usuario, límites y próximos pasos.

---

## 9. Checklist de entrega

- [ ] Video de 1–4 min subido
- [ ] Slide deck: problema y usuarios, solución, arquitectura de agentes, stack, uso de Zetaris y Meterless y qué tuvo de único, capturas, mejoras futuras
- [ ] Repo público con README (instalación, uso, dependencias), `.env.example`, `data/README.md`, ejemplos y trazas
- [ ] Explicación de sponsors: Zetaris, Meterless (engine + Nightshift), Cursor, NVIDIA
- [ ] Componentes previos declarados (el smoke test viene de la guía oficial)
- [ ] Cero secretos en el repo: ningún archivo ni commit con claves reales (`nvapi-…`, tokens de Zetaris o Nightshift)
- [ ] Prueba de instalación desde cero hecha: Windows en modo completo (Harry) y `SAMPLE_MODE` en equipo limitado (Chema)
- [ ] Subido antes del martes 27 a las 12:00
