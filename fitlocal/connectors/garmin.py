"""Conector de Garmin Connect (vía la librería no oficial `garminconnect`).

Aísla TODO lo que depende de Garmin en un solo lugar. Si Garmin cambia su API
interna y algo se rompe, se arregla aquí sin tocar el resto del proyecto.

Estrategia de ingesta:
  1. Bajar los datos crudos de Garmin para un día.
  2. Guardar el JSON completo en `raw_snapshots` (red de seguridad).
  3. Normalizar lo más útil en `daily_metrics` y `activities`.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from fitlocal.config import settings
from fitlocal.core.database import get_session
from fitlocal.core.models import Activity, DailyMetric, RawSnapshot


class GarminConnector:
    """Envuelve la conexión a Garmin Connect y la ingesta a la BD."""

    SOURCE = "garmin"

    def __init__(self, email: str | None = None, password: str | None = None):
        self.email = email or settings.garmin_email
        self.password = password or settings.garmin_password
        self._client = None  # se inicializa de forma perezosa al primer uso

    def _login(self):
        if self._client is not None:
            return self._client
        if not self.email or not self.password:
            raise RuntimeError(
                "Faltan credenciales de Garmin. Define GARMIN_EMAIL y "
                "GARMIN_PASSWORD en tu .env."
            )
        # Import perezoso: así el resto del proyecto no exige la librería.
        from garminconnect import Garmin

        client = Garmin(self.email, self.password)
        client.login()
        self._client = client
        return client

    # --- Helpers de persistencia ----------------------------------------

    def _save_snapshot(self, session, endpoint: str, day: date, payload) -> None:
        """Guarda (o reemplaza) el JSON crudo de un endpoint para un día."""
        if payload is None:
            return
        existing = session.scalar(
            select(RawSnapshot).where(
                RawSnapshot.source == self.SOURCE,
                RawSnapshot.endpoint == endpoint,
                RawSnapshot.day == day,
            )
        )
        if existing:
            existing.payload = payload
        else:
            session.add(
                RawSnapshot(
                    source=self.SOURCE, endpoint=endpoint, day=day, payload=payload
                )
            )

    def _upsert_daily(self, session, day: date, fields: dict) -> None:
        """Crea o actualiza la fila de métricas de un día."""
        clean = {k: v for k, v in fields.items() if v is not None}
        if not clean:
            return
        metric = session.scalar(select(DailyMetric).where(DailyMetric.day == day))
        if metric is None:
            metric = DailyMetric(day=day)
            session.add(metric)
        for key, value in clean.items():
            setattr(metric, key, value)

    # --- Ingesta ---------------------------------------------------------

    def sync_day(self, day: date) -> None:
        """Descarga y guarda todos los datos de un día."""
        client = self._login()
        iso = day.isoformat()

        # Cada llamada está envuelta para que un endpoint que falle no tumbe
        # al resto. Garmin a veces no tiene datos de cierto tipo en un día.
        stats = _safe(lambda: client.get_stats(iso))
        sleep = _safe(lambda: client.get_sleep_data(iso))
        rhr = _safe(lambda: client.get_rhr_day(iso))
        body_battery = _safe(lambda: client.get_body_battery(iso, iso))
        hrv = _safe(lambda: client.get_hrv_data(iso))
        readiness = _safe(lambda: client.get_training_readiness(iso))
        body_comp = _safe(lambda: client.get_body_composition(iso))

        with get_session() as session:
            # 1) Guardar todo en crudo.
            for endpoint, payload in {
                "stats": stats,
                "sleep": sleep,
                "rhr": rhr,
                "body_battery": body_battery,
                "hrv": hrv,
                "training_readiness": readiness,
                "body_composition": body_comp,
            }.items():
                self._save_snapshot(session, endpoint, day, payload)

            # 2) Normalizar lo más útil a columnas.
            self._upsert_daily(
                session,
                day,
                {
                    "steps": _dig(stats, "totalSteps"),
                    "resting_hr": _dig(stats, "restingHeartRate"),
                    "calories_burned": _dig(stats, "totalKilocalories"),
                    "stress_avg": _dig(stats, "averageStressLevel"),
                    "body_battery_high": _dig(stats, "bodyBatteryHighestValue"),
                    "body_battery_low": _dig(stats, "bodyBatteryLowestValue"),
                    "sleep_score": _dig(sleep, "dailySleepDTO", "sleepScores", "overall", "value"),
                    "sleep_seconds": _dig(sleep, "dailySleepDTO", "sleepTimeSeconds"),
                    "hrv": _dig(hrv, "hrvSummary", "lastNightAvg"),
                    "training_readiness": _readiness_score(readiness),
                    "weight_kg": _weight_kg(body_comp),
                },
            )

    def sync_activities(self, limit: int = 20) -> None:
        """Descarga las últimas actividades/entrenamientos."""
        client = self._login()
        activities = _safe(lambda: client.get_activities(0, limit)) or []

        with get_session() as session:
            for act in activities:
                gid = str(act.get("activityId")) if act.get("activityId") else None
                if gid is None:
                    continue
                existing = session.scalar(
                    select(Activity).where(Activity.garmin_activity_id == gid)
                )
                if existing:
                    continue
                start = act.get("startTimeLocal", "")
                day = _parse_day(start)
                session.add(
                    Activity(
                        garmin_activity_id=gid,
                        day=day,
                        activity_type=_dig(act, "activityType", "typeKey"),
                        name=act.get("activityName"),
                        duration_seconds=act.get("duration"),
                        distance_m=act.get("distance"),
                        avg_hr=act.get("averageHR"),
                        max_hr=act.get("maxHR"),
                        calories=act.get("calories"),
                    )
                )

    def sync_range(self, start: date, end: date) -> None:
        """Sincroniza un rango de días [start, end] inclusive."""
        current = start
        while current <= end:
            self.sync_day(current)
            current += timedelta(days=1)
        self.sync_activities()


# --- Utilidades sin estado ----------------------------------------------


def _safe(fn):
    """Ejecuta una llamada a Garmin; devuelve None si falla."""
    try:
        return fn()
    except Exception:
        return None


def _dig(data, *keys):
    """Navega un dict/lista anidado de forma segura. Devuelve None si no existe."""
    cur = data
    for key in keys:
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
    return cur


def _readiness_score(readiness):
    """Training Readiness puede venir como lista de un elemento."""
    if isinstance(readiness, list) and readiness:
        return _dig(readiness[0], "score")
    return _dig(readiness, "score")


def _weight_kg(body_comp):
    grams = _dig(body_comp, "totalAverage", "weight")
    return round(grams / 1000.0, 2) if isinstance(grams, (int, float)) else None


def _parse_day(start_time_local: str) -> date:
    """'2026-06-15 07:30:00' -> date(2026, 6, 15). Hoy por defecto si falla."""
    try:
        return date.fromisoformat(start_time_local.split(" ")[0])
    except Exception:
        return date.today()
