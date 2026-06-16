"""API FastAPI de fitlocal.

Arranca con:  uvicorn fitlocal.api.main:app --reload
Docs:         http://localhost:8000/docs
"""

from __future__ import annotations

from datetime import date

from fastapi import FastAPI
from pydantic import BaseModel

from fitlocal.agents.analyst import AnalystAgent
from fitlocal.agents.coach import CoachAgent
from fitlocal.agents.nutrition import NutritionAgent
from fitlocal.connectors.garmin import GarminConnector
from fitlocal.core.store import AirtableStore

app = FastAPI(title="fitlocal", version="0.1.0")


# --- Esquemas de petición -----------------------------------------------


class NutritionIn(BaseModel):
    description: str
    meal: str | None = None
    day: date | None = None


class SyncIn(BaseModel):
    start: date | None = None
    end: date | None = None


# --- Salud ---------------------------------------------------------------


@app.get("/")
def root():
    return {"app": "fitlocal", "status": "ok"}


# --- Datos ---------------------------------------------------------------


@app.get("/metrics")
def metrics(days: int = 14):
    """Métricas diarias recientes (desde Airtable)."""
    return AirtableStore().recent_daily_metrics(days)


# --- Nutrición -----------------------------------------------------------


@app.post("/nutrition")
def log_nutrition(body: NutritionIn):
    """Registra una comida en lenguaje natural; el agente estima los macros."""
    agent = NutritionAgent()
    return agent.log(body.description, meal=body.meal, day=body.day)


# --- Sincronización Garmin ----------------------------------------------


@app.post("/sync/garmin")
def sync_garmin(body: SyncIn):
    """Sincroniza datos de Garmin para un rango (por defecto: hoy)."""
    start = body.start or date.today()
    end = body.end or start
    GarminConnector().sync_range(start, end)
    return {"synced": {"start": start.isoformat(), "end": end.isoformat()}}


# --- Agentes -------------------------------------------------------------


@app.get("/analyst")
def analyst(days: int = 14):
    """Análisis de tendencias de tus datos."""
    return {"analysis": AnalystAgent().analyze(days)}


@app.get("/coach")
def coach(days: int = 14):
    """Sugerencias del coach según tu meta."""
    return {"advice": CoachAgent().advise(days)}
