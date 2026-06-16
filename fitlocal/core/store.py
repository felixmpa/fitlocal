"""Capa de almacenamiento sobre Airtable.

Todo el acceso a datos pasa por aquí. El conector de Garmin y los agentes
hablan con `AirtableStore`, no con la API de Airtable directamente — así si algún
día cambiamos de almacén, solo se toca este archivo.

Diseño de tablas (ver scripts/setup_airtable.py para crearlas):
  - "Daily Metrics"  : una fila por día (resumen de bienestar de Garmin)
  - "Activities"     : un registro por entrenamiento
  - "Nutrition"      : una comida registrada manualmente + macros del agente
  - "Raw Snapshots"  : el JSON crudo de cada fuente (red de seguridad)
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from pyairtable import Api
from pyairtable.formulas import match

from fitlocal.config import settings

# --- Nombres de tablas ---------------------------------------------------
TABLE_DAILY = "Daily Metrics"
TABLE_ACTIVITIES = "Activities"
TABLE_NUTRITION = "Nutrition"
TABLE_SNAPSHOTS = "Raw Snapshots"
TABLE_GOAL = "Goal"
TABLE_MEASUREMENTS = "Measurements"

# Métricas del cuerpo: (clave para los agentes, campo en "Measurements",
# campo en "Goal"). Es la fuente de verdad para emparejar actual vs deseado.
BODY_METRICS = [
    ("peso_kg", "Weight kg", "Target Weight kg"),
    ("grasa_pct", "Body Fat %", "Target Body Fat %"),
    ("barriga_cm", "Waist cm", "Target Waist cm"),
    ("pecho_cm", "Chest cm", "Target Chest cm"),
    ("bicep_cm", "Bicep cm", "Target Bicep cm"),
    ("cuadricep_cm", "Quad cm", "Target Quad cm"),
]


class AirtableStore:
    """Acceso a datos respaldado por Airtable."""

    def __init__(self, token: str | None = None, base_id: str | None = None):
        self.token = token or settings.airtable_token
        self.base_id = base_id or settings.airtable_base_id
        if not self.token or not self.base_id:
            raise RuntimeError(
                "Faltan credenciales de Airtable. Define AIRTABLE_TOKEN y "
                "AIRTABLE_BASE_ID en tu .env."
            )
        self.api = Api(self.token)

    def _table(self, name: str):
        return self.api.table(self.base_id, name)

    # --- Escritura -------------------------------------------------------

    def upsert_daily_metric(self, fields: dict) -> None:
        """Crea o actualiza la fila de un día. `fields` debe incluir "Day"."""
        clean = {k: v for k, v in fields.items() if v is not None}
        if "Day" not in clean:
            raise ValueError("upsert_daily_metric requiere el campo 'Day'.")
        self._table(TABLE_DAILY).batch_upsert(
            [{"fields": clean}], key_fields=["Day"]
        )

    def save_snapshot(self, source: str, endpoint: str, day: str, payload) -> None:
        """Guarda (o reemplaza) el JSON crudo de un endpoint para un día."""
        if payload is None:
            return
        key = f"{source}:{endpoint}:{day}"
        fields = {
            "Key": key,
            "Source": source,
            "Endpoint": endpoint,
            "Day": day,
            "Payload": json.dumps(payload, ensure_ascii=False),
            "Fetched At": _now_iso(),
        }
        self._table(TABLE_SNAPSHOTS).batch_upsert([{"fields": fields}], key_fields=["Key"])

    def add_activity_if_new(self, fields: dict) -> bool:
        """Añade una actividad si su 'Activity ID' aún no existe. True si se añadió."""
        activity_id = fields.get("Activity ID")
        if not activity_id:
            return False
        table = self._table(TABLE_ACTIVITIES)
        if table.first(formula=match({"Activity ID": activity_id})):
            return False
        table.create({k: v for k, v in fields.items() if v is not None})
        return True

    def add_nutrition(self, fields: dict) -> dict:
        """Registra una comida. Devuelve el registro creado."""
        return self._table(TABLE_NUTRITION).create(
            {k: v for k, v in fields.items() if v is not None}
        )

    # --- Meta y mediciones ----------------------------------------------

    def set_goal(self, fields: dict) -> None:
        """Crea o actualiza la meta. Se identifica por 'Name'."""
        clean = {k: v for k, v in fields.items() if v is not None}
        clean.setdefault("Name", "Mi meta")
        self._table(TABLE_GOAL).batch_upsert([{"fields": clean}], key_fields=["Name"])

    def active_goal(self) -> dict:
        """Devuelve la meta activa (o la primera si ninguna está marcada)."""
        rows = [r["fields"] for r in self._table(TABLE_GOAL).all()]
        if not rows:
            return {}
        for row in rows:
            if row.get("Active"):
                return row
        return rows[0]

    def add_measurement(self, fields: dict) -> dict:
        """Registra una sesión de medición corporal."""
        return self._table(TABLE_MEASUREMENTS).create(
            {k: v for k, v in fields.items() if v is not None}
        )

    def latest_measurement(self) -> dict:
        """Devuelve la medición más reciente (por 'Date')."""
        rows = [r["fields"] for r in self._table(TABLE_MEASUREMENTS).all()]
        if not rows:
            return {}
        rows.sort(key=lambda r: str(r.get("Date", "")), reverse=True)
        return rows[0]

    def goal_summary(self) -> dict:
        """Contexto de meta listo para los agentes: actual vs deseado + diferencia.

        El peso, si no hay medición manual, cae a la última lectura de Garmin.
        """
        from fitlocal.config import settings

        goal = self.active_goal()
        measure = self.latest_measurement()

        metrics: dict = {}
        for key, mfield, tfield in BODY_METRICS:
            actual = measure.get(mfield)
            if actual is None and key == "peso_kg":
                actual = self._latest_daily_weight()
            deseado = goal.get(tfield)
            if actual is None and deseado is None:
                continue
            diff = None
            if isinstance(actual, (int, float)) and isinstance(deseado, (int, float)):
                diff = round(actual - deseado, 1)
            metrics[key] = {"actual": actual, "deseado": deseado, "diferencia": diff}

        return {
            "objetivo": goal.get("Objective") or settings.fitlocal_goal,
            "ultima_medicion": measure.get("Date"),
            "metricas": metrics,
        }

    def _latest_daily_weight(self):
        for row in reversed(self.recent_daily_metrics(60)):
            if row.get("Weight kg") is not None:
                return row["Weight kg"]
        return None

    # --- Lectura (para los agentes) -------------------------------------

    def recent_daily_metrics(self, days: int = 14) -> list[dict]:
        return self._recent(TABLE_DAILY, days)

    def recent_nutrition(self, days: int = 14) -> list[dict]:
        return self._recent(TABLE_NUTRITION, days)

    def recent_activities(self, days: int = 14) -> list[dict]:
        return self._recent(TABLE_ACTIVITIES, days)

    def _recent(self, table_name: str, days: int) -> list[dict]:
        """Devuelve los campos de los registros de los últimos `days` días.

        Como las fechas se guardan como texto ISO (YYYY-MM-DD), el orden
        lexicográfico coincide con el cronológico.
        """
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        rows = [r["fields"] for r in self._table(table_name).all()]
        rows = [r for r in rows if str(r.get("Day", "")) >= cutoff]
        rows.sort(key=lambda r: str(r.get("Day", "")))
        return rows


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
