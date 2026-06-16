"""Sincroniza datos de Garmin hacia Airtable desde la línea de comandos.

    python scripts/sync_garmin.py            # solo hoy
    python scripts/sync_garmin.py --days 7   # últimos 7 días
    python scripts/sync_garmin.py --start 2026-06-01 --end 2026-06-15
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

# Permite ejecutar el script desde cualquier directorio.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fitlocal.connectors.garmin import GarminConnector  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincroniza Garmin -> Airtable")
    parser.add_argument("--days", type=int, help="Número de días hacia atrás desde hoy")
    parser.add_argument("--start", type=date.fromisoformat, help="Fecha inicio (YYYY-MM-DD)")
    parser.add_argument("--end", type=date.fromisoformat, help="Fecha fin (YYYY-MM-DD)")
    args = parser.parse_args()

    today = date.today()
    if args.start:
        start, end = args.start, (args.end or today)
    elif args.days:
        start, end = today - timedelta(days=args.days - 1), today
    else:
        start, end = today, today

    print(f"Sincronizando Garmin de {start} a {end}...")
    GarminConnector().sync_range(start, end)
    print("Hecho. Revisa tu base de Airtable.")


if __name__ == "__main__":
    main()
