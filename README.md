# fitlocal

Tracker personal de salud con coaching de **agentes IA**. Reúne tus datos
biométricos de **Garmin** y tu **alimentación** (en lenguaje natural), los
guarda en **Airtable**, y un equipo de agentes especializados (Claude) razona
sobre ellos para acercarte a tu meta.

## Idea

```
Garmin ─┐
        ├─▶  Airtable  ─▶  Agentes IA  ─▶  Sugerencias hacia tu meta
Comida ─┘   (datos)       (Claude)
```

- **Garmin** → sueño, FC en reposo, HRV, estrés, Body Battery, pasos, VO2max,
  entrenamientos, peso…
- **Comida** → la escribes en lenguaje natural ("2 huevos y una tostada") y el
  agente nutricionista estima calorías y macros.
- **Agentes** → un nutricionista, un analista de datos y un coach orquestador
  que conecta todo con tu **meta**.

## Arquitectura

```
fitlocal/
├── config.py            # configuración vía .env
├── core/
│   └── store.py         # capa de almacenamiento (Airtable)
├── connectors/
│   └── garmin.py        # ingesta de Garmin (aislada aquí)
├── agents/
│   ├── nutrition.py     # interpreta y registra comida (structured outputs)
│   ├── analyst.py       # detecta tendencias en los datos
│   └── coach.py         # orquestador: sugerencias según tu meta
└── api/
    └── main.py          # API FastAPI
scripts/
├── setup_airtable.py    # crea las tablas en tu base de Airtable
└── sync_garmin.py       # sincroniza Garmin -> Airtable
```

El almacenamiento está aislado en `core/store.py`: añadir nuevas fuentes de datos
es solo escribir un nuevo *connector*.

## Puesta en marcha

### 1. Instalar dependencias

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configurar credenciales

```bash
cp .env.example .env
# edita .env con tus datos
```

Necesitas:
- **Garmin**: tu email y contraseña de Garmin Connect.
- **Airtable**: un [Personal Access Token](https://airtable.com/create/tokens)
  con scopes `data.records:read`, `data.records:write`, `schema.bases:write`,
  y el **ID de tu base** (empieza por `app...`, lo ves en la URL).
- **Anthropic**: tu `ANTHROPIC_API_KEY`.

### 3. Preparar Airtable

```bash
python scripts/setup_airtable.py     # crea las 4 tablas en tu base
```

### 4. Usar

```bash
# Sincronizar Garmin (últimos 7 días)
python scripts/sync_garmin.py --days 7

# Levantar la API
uvicorn fitlocal.api.main:app --reload
# -> http://localhost:8000/docs
```

Endpoints principales:
- `POST /goal` — define tu meta (valores deseados)
- `POST /measurements` — registra una medición corporal (peso, grasa, cm)
- `GET /goal` — tu meta: actual vs deseado por métrica
- `POST /nutrition` — registra una comida: `{"description": "2 huevos y café"}`
- `POST /sync/garmin` — sincroniza Garmin
- `GET /metrics` — métricas diarias recientes
- `GET /analyst` — análisis de tendencias
- `GET /coach` — sugerencias según tu meta

## La meta vive en Airtable

Tu meta se modela en **dos tablas**, para no perder el historial de progreso:

- **`Goal`** — tus valores **deseados** (peso, grasa %, y cm de barriga, pecho,
  bícep, cuádriceps) + un objetivo en texto libre.
- **`Measurements`** — una fila por **sesión de medición**, con fecha y tus
  valores actuales. La "última medida" es la fila más reciente.

El sistema calcula al vuelo **actual vs deseado** y se lo pasa a cada agente como
la base de la meta sobre la que trabajar. (El peso, si no lo mides a mano, cae a
la última lectura de tu báscula Garmin.)

## Notas

- El conector de Garmin usa la librería **no oficial** `garminconnect`. Funciona
  muy bien para uso personal, pero puede romperse si Garmin cambia su API
  interna; por eso está aislado en un solo archivo.
- Los agentes **estiman** (sobre todo las calorías de la comida). Para tu meta
  personal suele ser suficiente; la consistencia importa más que el decimal.
- No es consejo médico.
