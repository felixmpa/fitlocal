"""Conector de Garmin Connect (vía la librería no oficial `garminconnect`).

Aísla TODO lo que depende de Garmin en un solo lugar. Si Garmin cambia su API
interna y algo se rompe, se arregla aquí sin tocar el resto del proyecto.

Estrategia de ingesta:
  1. Bajar los datos crudos de Garmin para un día.
  2. Guardar el JSON completo en "Raw Snapshots" (red de seguridad).
  3. Normalizar lo más útil en "Daily Metrics" y "Activities".
"""

from __future__ import annotations

from datetime import date, timedelta

from fitlocal.config import settings
from fitlocal.core.store import AirtableStore


class GarminConnector:
    """Envuelve la conexión a Garmin Connect y la ingesta a Airtable."""

    SOURCE = "garmin"

    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        store: AirtableStore | None = None,
    ):
        self.email = email or settings.garmin_email
        self.password = password or settings.garmin_password
        self.store = store or AirtableStore()
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

    # --- Ingesta ---------------------------------------------------------

    def sync_day(self, day: date) -> None:
        """Descarga y guarda todos los datos de un día."""
        client = self._login()
        iso = day.isoformat()

        # Cada llamada está envuelta para que un endpoint que falle no tumbe
        # al resto. Garmin a veces no tiene datos de cierto tipo en un día.
        stats = _safe(lambda: client.get_stats(iso))
        sleep = _safe(lambda: client.get_sleep_data(iso))
        body_battery = _safe(lambda: client.get_body_battery(iso, iso))
        hrv = _safe(lambda: client.get_hrv_data(iso))
        readiness = _safe(lambda: client.get_training_readiness(iso))
        body_comp = _safe(lambda: client.get_body_composition(iso))

        # 1) Guardar todo en crudo.
        for endpoint, payload in {
            "stats": stats,
            "sleep": sleep,
            "body_battery": body_battery,
            "hrv": hrv,
            "training_readiness": readiness,
            "body_composition": body_comp,
        }.items():
            self.store.save_snapshot(self.SOURCE, endpoint, iso, payload)

        # 2) Normalizar lo más útil a columnas de "Daily Metrics".
        sleep_seconds = _dig(sleep, "dailySleepDTO", "sleepTimeSeconds")
        self.store.upsert_daily_metric(
            {
                "Day": iso,
                "Steps": _dig(stats, "totalSteps"),
                "Resting HR": _dig(stats, "restingHeartRate"),
                "Calories Burned": _dig(stats, "totalKilocalories"),
                "Stress Avg": _dig(stats, "averageStressLevel"),
                "Body Battery High": _dig(stats, "bodyBatteryHighestValue"),
                "Body Battery Low": _dig(stats, "bodyBatteryLowestValue"),
                "Sleep Score": _dig(sleep, "dailySleepDTO", "sleepScores", "overall", "value"),
                "Sleep Hours": round(sleep_seconds / 3600, 1) if sleep_seconds else None,
                "HRV": _dig(hrv, "hrvSummary", "lastNightAvg"),
                "Training Readiness": _readiness_score(readiness),
                "Weight kg": _weight_kg(body_comp),
            }
        )

    def sync_activities(self, limit: int = 20) -> None:
        """Descarga las últimas actividades/entrenamientos."""
        client = self._login()
        activities = _safe(lambda: client.get_activities(0, limit)) or []

        for act in activities:
            gid = act.get("activityId")
            if gid is None:
                continue
            duration_s = act.get("duration")
            distance_m = act.get("distance")
            self.store.add_activity_if_new(
                {
                    "Activity ID": str(gid),
                    "Day": _parse_day(act.get("startTimeLocal", "")),
                    "Type": _dig(act, "activityType", "typeKey"),
                    "Name": act.get("activityName"),
                    "Duration min": round(duration_s / 60, 1) if duration_s else None,
                    "Distance km": round(distance_m / 1000, 2) if distance_m else None,
                    "Avg HR": act.get("averageHR"),
                    "Max HR": act.get("maxHR"),
                    "Calories": act.get("calories"),
                }
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


def _parse_day(start_time_local: str) -> str:
    """'2026-06-15 07:30:00' -> '2026-06-15'. Hoy por defecto si falla."""
    try:
        return start_time_local.split(" ")[0] or date.today().isoformat()
    except Exception:
        return date.today().isoformat()
