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


class GoalIn(BaseModel):
    objective: str | None = None
    active: bool | None = True
    target_weight_kg: float | None = None
    target_body_fat_pct: float | None = None
    target_waist_cm: float | None = None
    target_chest_cm: float | None = None
    target_bicep_cm: float | None = None
    target_quad_cm: float | None = None


class MeasurementIn(BaseModel):
    date: date | None = None
    weight_kg: float | None = None
    body_fat_pct: float | None = None
    waist_cm: float | None = None
    chest_cm: float | None = None
    bicep_cm: float | None = None
    quad_cm: float | None = None
    notes: str | None = None


# --- Salud ---------------------------------------------------------------


@app.get("/")
def root():
    return {"app": "fitlocal", "status": "ok"}


# --- Datos ---------------------------------------------------------------


@app.get("/metrics")
def metrics(days: int = 14):
    """Métricas diarias recientes (desde Airtable)."""
    return AirtableStore().recent_daily_metrics(days)


# --- Meta y mediciones ---------------------------------------------------


@app.get("/goal")
def get_goal():
    """Meta actual: objetivo + actual vs deseado por métrica."""
    return AirtableStore().goal_summary()


@app.post("/goal")
def set_goal(body: GoalIn):
    """Define o actualiza tus valores deseados (la meta)."""
    AirtableStore().set_goal(
        {
            "Name": "Mi meta",
            "Objective": body.objective,
            "Active": body.active,
            "Target Weight kg": body.target_weight_kg,
            "Target Body Fat %": body.target_body_fat_pct,
            "Target Waist cm": body.target_waist_cm,
            "Target Chest cm": body.target_chest_cm,
            "Target Bicep cm": body.target_bicep_cm,
            "Target Quad cm": body.target_quad_cm,
        }
    )
    return AirtableStore().goal_summary()


@app.post("/measurements")
def add_measurement(body: MeasurementIn):
    """Registra una sesión de medición corporal (peso, grasa, cm)."""
    day = body.date or date.today()
    AirtableStore().add_measurement(
        {
            "Date": day.isoformat(),
            "Weight kg": body.weight_kg,
            "Body Fat %": body.body_fat_pct,
            "Waist cm": body.waist_cm,
            "Chest cm": body.chest_cm,
            "Bicep cm": body.bicep_cm,
            "Quad cm": body.quad_cm,
            "Notes": body.notes,
        }
    )
    return AirtableStore().goal_summary()


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
