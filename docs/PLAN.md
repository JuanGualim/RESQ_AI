# RESQ AI — Plan por fases del equipo

**Open Agent Hackathon 2026 · Track 3: Reasoning Architecture**
Versión 1 · viernes 23 de octubre de 2026 · horas en **hora de Guatemala (UTC-6)**
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

Lanes de Nightshift: **rápido** = `nvidia/nemotron-3.5-lightning-30b-a3b` (verificado) · **profundo** = un Nemotron super (por confirmar cuál responde con nuestra cuenta).

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

| Integrante | Máquina | Rol | Dueño de |
| --- | --- | --- | --- |
| **Juan** | EndeavourOS (Linux) · host de **Zetaris** | Datos e integración (líder técnico) | Zetaris encendido en las sesiones · Postgres del escenario · generador de datos · tabla Open-Meteo · herramienta `run_sql` · `SAMPLE_MODE` · `data/README.md` · revisión de PRs · mantener `AGENTS.md` · **sube la entrega a HackOS** |
| **Integrante 2** (nombre: ______) | Windows · host de **Nightshift** | Agentes y modelos | Nightshift y sus lanes · `resq/llm.py` · grafo LangGraph · prompts · ciclo del crítico · escalamiento · traza JSONL · evidencia de Nemotron |
| **Integrante 3** (nombre: ______) | Windows | Engine y producto | Meterless World Model (integración + conformance) · herramienta de rutas (networkx) · UI Streamlit · README · video · slide deck |

Todos: probar escenarios, revisar el guion de la demo y actualizar `AGENTS.md` al cerrar cada sesión.

---

## 4. Fases

### Fase 0 — Arranque · viernes 23, hasta las 14:00

Objetivo: los tres con entorno funcionando y contratos acordados.

- [ ] Integrantes 2 y 3 completan `docs/SETUP_EQUIPO.md`: `smoke_test.py` da 3 PASS desde su máquina
- [ ] Tailscale: los 3 en la misma red; Zetaris de Juan y Nightshift de Integrante 2 alcanzables
- [ ] Juan: primer commit (AGENTS.md, CLAUDE.md, requirements.txt, smoke test, docs)
- [ ] Llamada de 45 min: revisar esquema de datos y contratos (sección 5) y anotarlos en `AGENTS.md`
- [ ] Integrante 3: correr *IMPLEMENT → Run the 90-second proof* y decidir cómo integrar World Model en Python (riesgo R1)

**Gate:** smoke test en las 3 máquinas y contratos escritos.

### Fase 1 — MVP de punta a punta · viernes 23 tarde → sábado 24, 12:00

Objetivo: entra una pregunta, sale un plan v1 (feo pero real) con datos de Zetaris y Nemotron vía Nightshift.

- [ ] Juan: generador de datos, Postgres, registro en Zetaris, `run_sql`, 10 consultas clave probadas
- [ ] Integrante 2: `llm.py` (lanes rápido y profundo, headers de Meterless), grafo mínimo Analista → Planificador → Explicador, traza JSONL
- [ ] Integrante 3: `best_route` sobre el grafo de tramos; World Model con entidades y el evento `tramo_bloqueado`; conformance corriendo

**Gate (sáb 24, 12:00):** `python -m resq.run --pregunta "..."` imprime un plan v1 con rutas válidas.

### Fase 2 — Sistema multiagente real · sábado 24 tarde → domingo 25, 22:00

Objetivo: el comportamiento que premian los jueces.

- [ ] Integrante 2: Crítico con ciclo de revisión (máx. 3), rama de escalamiento, Conciliador, Intake
- [ ] Integrante 3: World Model como estado compartido de todos los agentes; replan disparado por evento; diferencias entre versiones del plan
- [ ] Juan: reportes contradictorios sembrados, tabla Open-Meteo, 3 escenarios de prueba, `SAMPLE_MODE`
- [ ] **Check-in sáb 24, 20:00:** "si entregáramos mañana, ¿qué fallaría?"

**Gate (dom 25, 22:00):** bloquear 2 tramos distintos produce 2 replanes distintos y correctos, con la traza del ciclo del crítico.

### Fase 3 — Producto y confiabilidad · lunes 26, hasta las 14:00

- [ ] Integrante 3: UI Streamlit (mapa esquemático, plan, botón "bloquear tramo", panel "¿por qué cambió?", traza de agentes)
- [ ] Integrante 2: timeouts, reintentos acotados, errores honestos; lane Nemotron fijo y captura de los logs de Nightshift
- [ ] Juan: instalación desde cero en Windows siguiendo el README; `input_examples/` y `output_examples/`
- [ ] Solo si sobra tiempo: H-MEM o Scout Intent

**Lunes 26, 14:00: CONGELAR FUNCIONES.** Desde aquí solo se corrigen errores.

### Fase 4 — Empaquetar y entregar · lunes 26, 14:00 → martes 27, 12:00

- [ ] Integrante 3: video de 1–4 min (guion abajo) y slide deck
- [ ] Juan: README final, `data/README.md`, `.env.example`, declaración de componentes previos, explicación de sponsors
- [ ] Integrante 2: revisión de trazas y sección técnica del deck
- [ ] **Martes 27, 12:00: Juan sube todo a HackOS.** Límite duro: 17:45

---

## 5. Contratos entre partes

Para trabajar en paralelo sin pisarse. Cambiar un contrato = avisar al grupo y anotarlo en `AGENTS.md`.

```python
# resq/tools/zetaris.py  (Juan)
def run_sql(sql: str, limit: int = 500) -> list[dict]: ...   # una sentencia; lanza ZetarisError

# resq/llm.py  (Integrante 2)
def chat(messages: list[dict], lane: str = "fast", tools: list | None = None) -> dict: ...  # lane: "fast" | "deep"

# resq/world/  (Integrante 3)
def get_state() -> dict: ...                 # comunidades, tramos, albergues con su estado actual
def apply_event(event: dict) -> None: ...    # {"tipo": "tramo_bloqueado", "id": "T7", "fuente": ..., "ts": ...}
def history() -> list[dict]: ...             # eventos en orden

# resq/tools/routing.py  (Integrante 3)
def best_route(origen: str, destino: str, state: dict, vehiculo: str) -> Route | None: ...

# resq/schemas.py  (todos; Integrante 2 lo crea)
class Asignacion(BaseModel): comunidad_id; origen_id; recurso; cantidad; vehiculo_id; ruta: list[str]; prioridad: int; razon: str; evidencia: list[str]
class Plan(BaseModel): version: int; asignaciones: list[Asignacion]; sin_atender: list[str]; riesgos: list[str]; confianza: float; escalado: bool; cambios_vs_anterior: list[str]
```

---

## 6. Forma de trabajo

- **Ramas:** `feat/<area>-<tema>` → Pull Request a `main`; Juan revisa; se integra al menos una vez al día.
- **Al cerrar cada sesión:** actualizar la sección *Estado* de `AGENTS.md` (qué quedó, qué sigue, bloqueos).
- **Bloqueos:** más de 45 min trabado se avisa al grupo; después HackOS (#help desk, canal del sponsor o mentores).
- **Secretos:** nunca en el repo, chats públicos ni capturas. Tokens solo por mensaje privado.
- **Agentes de IA** (Cursor, Claude Code, Codex): leen `AGENTS.md` primero; cambios pequeños; correr pruebas antes de cada commit.
- **Máquinas host:** Zetaris (Juan) y Nightshift (Integrante 2) encendidos en los bloques de trabajo acordados. Sin Nightshift, se desarrolla con NVIDIA directo (solo para desarrollo).

---

## 7. Riesgos y plan B

| # | Riesgo | Plan B |
| --- | --- | --- |
| R1 | Los engines de Meterless están en TypeScript y el agente en Python | Viernes: (a) implementar la spec en Python con un adaptador para la conformance, o (b) World Model como microservicio Node que Python llama por HTTP |
| R2 | Nightshift solo en una máquina | NVIDIA directo para desarrollo; la demo y la prueba final se hacen con Nightshift; laptop de Integrante 2 conectada a corriente y sin suspensión |
| R3 | Zetaris no alcanzable desde Windows por Tailscale | Revisar puertos y `tailscale serve`; mientras tanto, `SAMPLE_MODE` |
| R4 | Zetaris no lee CSV locales | Postgres propio registrado como fuente |
| R5 | Los jueces no pueden levantar Zetaris + Nightshift | README claro, `SAMPLE_MODE`, video y `output_examples/` |
| R6 | El modelo inventa datos | Validaciones duras en código, crítico, toda asignación referencia IDs reales |
| R7 | El alcance crece | Gates por fase; congelar el lunes 14:00 |
| R8 | RAM de la máquina de Juan | Cerrar apps, zram activo, `docker compose stop` cuando no se use |

---

## 8. Guion del video (máx. 4 min)

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
- [ ] Prueba de instalación desde cero hecha
- [ ] Subido antes del martes 27 a las 12:00
