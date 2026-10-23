# AGENTS.md — RESQ AI

> **Lee este archivo completo antes de tocar código.** Es la fuente de verdad del proyecto para personas y agentes de IA (Cursor, Claude Code, Codex). Al terminar cada sesión de trabajo, actualiza **§8 Estado actual**, **§9 Próximos pasos** y, si decidiste algo, **§10 Registro de decisiones**.

Última actualización: 2026-10-23 03:00 (GT) · por: Juan

---

## 1. El proyecto en 30 segundos

**RESQ AI** es un sistema multiagente que ayuda a un **coordinador municipal de emergencias** a decidir cómo distribuir ayuda durante una **inundación**. Combina datos de comunidades, albergues, bodegas, carreteras, vehículos, lluvia y reportes de campo contradictorios; prioriza con reglas de protocolo; y entrega un **plan de distribución versionado** que se replantea cuando cambia la realidad (ej.: se bloquea una carretera), explicando **qué cambió y por qué**.

- Evento: **Open Agent Hackathon 2026** · **Track 3: Reasoning Architecture**
- Entrega: **martes 27-oct-2026, 17:45 hora de Guatemala** (23:45 UTC). Meta interna: martes 12:00.
- Equipo: Juan (Linux, datos e integración), Integrante 2 (Windows, agentes y modelos, host de Nightshift), Integrante 3 (Windows, engine y producto).
- Plan completo: `docs/PLAN.md` · Setup de entorno: `docs/SETUP_EQUIPO.md`

## 2. Reglas no negociables (si se rompe una, quedamos descalificados o perdemos puntos)

1. **Zetaris es la única fuente de datos del agente.** Todo dato del escenario se lee con SQL a través de Zetaris (`resq/tools/zetaris.py`). La excepción es `SAMPLE_MODE=true` (copia local para jueces y desarrollo sin servicios).
2. **Meterless Nightshift es el proveedor principal de IA.** Toda llamada a un modelo pasa por `resq/llm.py`, que usa la API compatible con OpenAI de Nightshift. NVIDIA directo solo se permite en desarrollo, cambiando `.env`; nunca como valor por defecto.
3. **Al menos un Meterless Engine funcionando de verdad:** usamos **World Model** como estado compartido de los agentes, con su suite de conformance pasando. Mencionarlo o instalarlo sin usarlo no cuenta.
4. **Desarrollo en Cursor** (además se permiten Claude Code y Codex).
5. **Secretos solo en `.env`** (ignorado por git). En el repo, `.env.example` con valores falsos. Nunca imprimas, registres en logs ni escribas en código claves o tokens.
6. **Nada hardcodeado en la demo.** Los resultados salen de los datos y del razonamiento de los agentes. Las contradicciones se siembran en los datos, nunca en el código.
7. **Datos sintéticos.** Nada de datos reales de personas. El municipio es ficticio; la lluvia viene de Open-Meteo (pública, sin clave).
8. **Sistema multiagente real**, no un pipeline lineal: debe haber crítica, revisión, reintentos acotados, ramificación y escalamiento, con traza visible.

## 3. Arquitectura

```text
UI (Streamlit) ── pregunta / evento ("bloquear tramo T7")
  ▼
Intake ─ clasifica: situacion | plan | evento | por_que
  ▼
Conciliador ─ reportes contradictorios → hechos + confianza ─► World Model
  ▼
Analista de riesgo ─ SQL (Zetaris) → riesgo por comunidad ─► World Model
  ▼
Planificador ─ reglas + best_route + capacidades → Plan vN
  ▼
Crítico ─ validadores en código + LLM
  │  ✗ → vuelve al Planificador con observaciones (máx. 3 vueltas)
  │  ✗✗ → escalado=True: "requiere decisión humana"
  ✓
Explicador ─ plan final + cambios vs. versión anterior (historial del World Model)

Compartido: Zetaris · World Model · Nightshift→Nemotron · traza JSONL en logs/
```

**Principio: el LLM decide y explica; el código calcula.** Rutas, capacidades, inventario y validaciones duras son funciones deterministas y probadas. Los agentes razonan sobre sus resultados.

| Agente | Lane | Herramientas | Salida |
| --- | --- | --- | --- |
| Intake | fast | reglas (Scout Intent opcional) | tipo de solicitud |
| Conciliador | fast | `run_sql` | eventos de hecho verificado → World Model |
| Analista de riesgo | fast | `run_sql` | riesgo por comunidad → World Model |
| Planificador | deep | `best_route`, inventario | `Plan` |
| Crítico | deep | `validators.*` | aprobado / observaciones / escalado |
| Explicador | fast | `world.history()` | reporte final |

Framework: **LangGraph** (Python). Estado del grafo = `ResqState` (pydantic) + World Model como estado de dominio compartido.

## 4. Stack y servicios

| Pieza | Detalle |
| --- | --- |
| Python | 3.12 recomendado (Juan usa 3.14 en Linux; si una dependencia falla, usar 3.12) |
| Agentes | LangGraph, `openai` (cliente compatible), pydantic |
| Rutas | networkx sobre la tabla `tramos` |
| UI | Streamlit |
| Zetaris | Corre en la laptop de Juan (Docker). UI `:3000`, REST `:8888/api/v1.0`. El equipo entra por Tailscale |
| Nightshift | Corre en el Windows de Integrante 2. Base URL `:8088/v1`. Lanes: fast = `nvidia/nemotron-3.5-lightning-30b-a3b`; deep = Nemotron super (por confirmar) |
| World Model | Meterless engine. Spec y conformance: https://github.com/Meterless/Meterless/tree/main/engines/world-model |
| Prompts de Meterless | https://meterless.ai/engines.html (IMPLEMENT → *Keep parallel agents in sync*; POWER → *Add Meterless as a provider*) |

### Cómo hablar con Zetaris

- `POST {ZETARIS_REST_URL}/sql-editor/sqls/run`
- Headers: `Authorization: Bearer {ZETARIS_API_KEY}`, `X-Org-ID: {ZETARIS_ORG_ID}`, `X-Request-ID: <uuid4 nuevo>`
- Body: `{"queryId": "<uuid4>", "sql": "<UNA sentencia>", "source": "SqlEditor", "limit": N}` → respuesta con `data` (filas)
- Dialecto **Lightning SQL**. **Una sentencia por request.** Referencia: http://localhost:8888/redoc/index.html y https://github.com/zetaris/getting-started (su `AGENTS.md`)
- Zetaris **no lee archivos de la laptop**: los datos del escenario van en un Postgres propio registrado como fuente.
- Nunca uses el puerto 8889 (interno).

### Cómo hablar con Nightshift

- API compatible con OpenAI: `GET /v1/models`, `POST /v1/chat/completions`
- Headers: `Authorization: Bearer {METERLESS_RUNTIME_TOKEN}`, `meterless-app: resq-ai`, `meterless-scope: user`
- `meterless/auto` puede enrutar a un modelo no-NVIDIA: para la demo y el premio NVIDIA, **fijar un lane con Nemotron**.
- Errores conocidos: `404 page not found` = URL sin `/v1` o modelo no-chat (`rerank`, `embed`); `Function … Not found for account` = modelo sin endpoint para la cuenta.

## 5. Estructura del repo (objetivo)

```text
RESQ_AI/
├── AGENTS.md              # este archivo (contexto vivo)
├── CLAUDE.md              # apunta a AGENTS.md
├── README.md              # instalación, uso, dependencias (para jueces)
├── requirements.txt
├── .env.example           # sin secretos
├── smoke_test.py          # verifica Zetaris + modelo (de la guía oficial)
├── docs/
│   ├── PLAN.md            # plan por fases
│   ├── SETUP_EQUIPO.md    # guía de entorno
│   └── protocolo.md       # reglas de prioridad (conocimiento del dominio)
├── resq/
│   ├── config.py          # lee .env, SAMPLE_MODE
│   ├── llm.py             # chat(messages, lane, tools) → Nightshift
│   ├── schemas.py         # Asignacion, Plan, Evento, ResqState
│   ├── graph.py           # grafo LangGraph
│   ├── agents/            # intake, conciliador, analista, planificador, critico, explicador
│   ├── tools/
│   │   ├── zetaris.py     # run_sql
│   │   ├── routing.py     # best_route
│   │   └── validators.py  # reglas duras del crítico
│   ├── world/             # integración World Model
│   └── run.py             # CLI: python -m resq.run --pregunta "..."
├── app/streamlit_app.py   # UI
├── scripts/generate_data.py   # datos sintéticos (semilla fija)
├── data/sample/ + data/README.md
├── input_examples/  output_examples/
├── logs/                  # trazas JSONL (no se suben los .log)
└── tests/
```

## 6. Contratos entre módulos

Cambiar un contrato = avisar al grupo + anotarlo en §10.

```python
# resq/tools/zetaris.py
def run_sql(sql: str, limit: int = 500) -> list[dict]: ...   # una sentencia; lanza ZetarisError

# resq/llm.py
def chat(messages: list[dict], lane: str = "fast", tools: list | None = None) -> dict: ...  # "fast" | "deep"

# resq/world/
def get_state() -> dict: ...
def apply_event(event: dict) -> None: ...    # {"tipo": "tramo_bloqueado", "id": "T7", "fuente": "...", "ts": "..."}
def history() -> list[dict]: ...

# resq/tools/routing.py
def best_route(origen: str, destino: str, state: dict, vehiculo: str) -> "Route | None": ...

# resq/schemas.py
class Asignacion(BaseModel): comunidad_id: str; origen_id: str; recurso: str; cantidad: int; vehiculo_id: str; ruta: list[str]; prioridad: int; razon: str; evidencia: list[str]
class Plan(BaseModel): version: int; asignaciones: list[Asignacion]; sin_atender: list[str]; riesgos: list[str]; confianza: float; escalado: bool; cambios_vs_anterior: list[str]
```

### Datos del escenario (tablas en Zetaris)

`comunidades`(id, nombre, poblacion, pct_ninos, pct_adultos_mayores, vulnerabilidad 1–5, elevacion_m, lat, lon, nodo_vial) · `albergues`(id, nombre, capacidad, ocupacion_actual, nodo_vial) · `bodegas`(id, nombre, nodo_vial) · `inventario`(bodega_id, recurso, cantidad) · `tramos`(id, origen, destino, distancia_km, superficie, estado_oficial) · `vehiculos`(id, tipo, capacidad_kg, puede_vadear, bodega_id) · `reportes_campo`(id, timestamp, fuente: oficial|brigada|redes, objeto_tipo, objeto_id, estado_reportado, detalle) · `lluvia` (REST Open-Meteo: fecha_hora, precipitacion_mm).

Tamaño: 12–15 comunidades, 3–4 albergues, 2 bodegas, ~20 tramos, 5–8 vehículos, ~30 reportes.

## 7. Convenciones para agentes de IA y personas

- **Idioma:** código e identificadores en español sin tildes o en inglés, pero consistente por módulo; textos al usuario en español.
- **Cambios pequeños** y enfocados en la tarea pedida; no reescribas módulos de otro integrante sin avisar.
- **No inventes APIs** de Zetaris o Meterless: consulta las fuentes de §4. Si no estás seguro, dilo y deja un `TODO(verificar)`.
- **Modelos:** solo a través de `resq/llm.py`. Ningún otro archivo crea clientes de OpenAI.
- **Datos:** solo a través de `resq/tools/zetaris.py` (o `SAMPLE_MODE`).
- **Traza:** cada paso de agente escribe una línea JSONL en `logs/` (`ts, run_id, agente, entrada_resumida, salida_resumida, lane, modelo, duracion_ms, iteracion`). Nunca incluir secretos.
- **Límites:** timeouts en toda llamada externa (Zetaris 60 s, modelo 90 s); máximo 3 vueltas del crítico; reintentos máximo 2.
- **Pruebas:** `pytest` en `tests/` para herramientas deterministas (routing, validators). Correr `python smoke_test.py` y `pytest` antes de abrir un PR.
- **Git:** ramas `feat/<area>-<tema>`; commits pequeños en español; PR a `main`; revisa Juan. Nunca `git add .env`.
- **Al cerrar sesión:** actualizar §8, §9 y §10 de este archivo.

### Cómo correr

```bash
# Linux/macOS
python -m venv .venv && source .venv/bin/activate
# Windows: py -3.12 -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env        # y completar valores reales
python smoke_test.py        # 3 PASS esperados
# (cuando existan)
python -m resq.run --pregunta "¿Cómo distribuimos la ayuda ahora?"
streamlit run app/streamlit_app.py
```

### Variables de entorno

| Variable | Uso |
| --- | --- |
| `ZETARIS_BASE_URL` | UI de Zetaris (smoke test) |
| `ZETARIS_REST_URL`, `ZETARIS_ORG_ID`, `ZETARIS_API_KEY` | API REST de Zetaris |
| `METERLESS_BASE_URL`, `METERLESS_RUNTIME_TOKEN`, `METERLESS_MODEL` | Nightshift (proveedor principal) |
| `MODEL_BASE_URL`, `MODEL_API_KEY`, `NEMOTRON_MODEL` | Modelo activo (Nightshift por defecto; NVIDIA directo solo en desarrollo) |
| `LANE_FAST_MODEL`, `LANE_DEEP_MODEL` | Modelo por lane (por definir) |
| `SAMPLE_MODE` | `true` = usar `data/sample/` sin Zetaris |

---

## 8. Estado actual

**Fase actual: 0 — Arranque** (meta: viernes 23, 14:00)

Hecho:
- [x] Track 3 elegido; idea RESQ AI definida
- [x] Zetaris instalado y corriendo en la laptop de Juan (`verify.sh` OK, token de API creado, REST probado)
- [x] Cursor funcionando (Juan)
- [x] `smoke_test.py` → 3 PASS en Linux de Juan, con NVIDIA directo y `nvidia/nemotron-3.5-lightning-30b-a3b`
- [x] Repo `JuanGualim/RESQ_AI` creado con `smoke_test.py`, `.gitignore`, `.env.example`, `requirements.txt`, `AGENTS.md`, `CLAUDE.md`, `docs/`

Pendiente / bloqueado:
- [ ] Primer commit y push (aún no hay commits)
- [ ] Nightshift instalado en el Windows de Integrante 2
- [ ] Tailscale entre las 3 máquinas; Zetaris y Nightshift alcanzables
- [ ] Setup de Integrantes 2 y 3 (smoke test en sus máquinas)
- [ ] Decidir integración de World Model en Python (TS nativo vs. adaptador vs. microservicio) — riesgo R1

## 9. Próximos pasos (en orden)

1. **Juan:** primer commit + push; invitar colaboradores en GitHub; Tailscale y exponer Zetaris (`docs/SETUP_EQUIPO.md` §G).
2. **Integrante 2:** Nightshift + NVIDIA + lanes; compartir URL y token por privado (§F).
3. **Integrante 3:** setup; correr *IMPLEMENT → Run the 90-second proof*; proponer la integración de World Model.
4. **Todos:** llamada de 45 min para confirmar esquema de datos y contratos (§6).
5. **Fase 1** (vie tarde → sáb 12:00): generador de datos + Postgres en Zetaris (Juan) · `llm.py` + grafo mínimo (Integrante 2) · `best_route` + World Model básico (Integrante 3).

## 10. Registro de decisiones

| Fecha (GT) | Decisión | Por qué |
| --- | --- | --- |
| 2026-10-22 | Track 3: Reasoning Architecture | El resultado es una decisión que se replantea con estado nuevo |
| 2026-10-23 | Zetaris en la laptop Linux de Juan; Nightshift en el Windows de Integrante 2; red Tailscale | Nightshift no tiene versión Linux; Zetaris necesita 16 GB |
| 2026-10-23 | Desarrollo con NVIDIA directo permitido; Nightshift obligatorio en demo y valores por defecto | No bloquear a nadie si el host de Nightshift no está disponible |
| 2026-10-23 | Engine principal: World Model | Estado compartido + historial de eventos = explicación de replanes |
| 2026-10-23 | Rutas y validaciones en código determinista; el LLM decide y explica | Confiabilidad y reproducibilidad ante jueces |
| 2026-10-23 | Datos del escenario en Postgres propio registrado en Zetaris | Zetaris no lee CSV locales |
