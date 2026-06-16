"""Crea las tablas de fitlocal en tu base de Airtable.

Ejecútalo una sola vez tras configurar AIRTABLE_TOKEN y AIRTABLE_BASE_ID.
El token necesita el scope `schema.bases:write`.

    python scripts/setup_airtable.py
"""

from __future__ import annotations

from pyairtable import Api

from fitlocal.config import settings
from fitlocal.core.store import (
    TABLE_ACTIVITIES,
    TABLE_DAILY,
    TABLE_NUTRITION,
    TABLE_SNAPSHOTS,
)


def _num(name: str, precision: int = 0) -> dict:
    return {"name": name, "type": "number", "options": {"precision": precision}}


def _text(name: str) -> dict:
    return {"name": name, "type": "singleLineText"}


def _long(name: str) -> dict:
    return {"name": name, "type": "multilineText"}


# El primer campo de cada lista es el campo primario de la tabla.
TABLES = {
    TABLE_DAILY: [
        _text("Day"),
        _num("Steps"),
        _num("Resting HR"),
        _num("Sleep Score"),
        _num("Sleep Hours", 1),
        _num("Stress Avg"),
        _num("Body Battery High"),
        _num("Body Battery Low"),
        _num("HRV"),
        _num("VO2max", 1),
        _num("Training Readiness"),
        _num("Calories Burned"),
        _num("Weight kg", 1),
    ],
    TABLE_ACTIVITIES: [
        _text("Activity ID"),
        _text("Day"),
        _text("Type"),
        _text("Name"),
        _num("Duration min", 1),
        _num("Distance km", 2),
        _num("Avg HR"),
        _num("Max HR"),
        _num("Calories"),
    ],
    TABLE_NUTRITION: [
        _text("Logged At"),
        _text("Day"),
        _text("Meal"),
        _long("Description"),
        _num("Calories"),
        _num("Protein g", 1),
        _num("Carbs g", 1),
        _num("Fat g", 1),
        _long("Items"),
        _num("Confidence", 2),
    ],
    TABLE_SNAPSHOTS: [
        _text("Key"),
        _text("Source"),
        _text("Endpoint"),
        _text("Day"),
        _long("Payload"),
        _text("Fetched At"),
    ],
}


def main() -> None:
    if not settings.airtable_token or not settings.airtable_base_id:
        raise SystemExit("Define AIRTABLE_TOKEN y AIRTABLE_BASE_ID en tu .env primero.")

    base = Api(settings.airtable_token).base(settings.airtable_base_id)
    existing = {t.name for t in base.tables()}

    for name, fields in TABLES.items():
        if name in existing:
            print(f"= '{name}' ya existe, se omite.")
            continue
        base.create_table(name, fields=fields)
        print(f"+ Tabla '{name}' creada.")

    print("\nListo. Tu base de Airtable está preparada para fitlocal.")


if __name__ == "__main__":
    main()
