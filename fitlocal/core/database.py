"""Motor de base de datos y sesiones (SQLAlchemy).

SQLite hoy; migrar a PostgreSQL es solo cambiar `FITLOCAL_DB_URL`.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from fitlocal.config import settings
from fitlocal.core.models import Base


def _make_engine():
    url = settings.fitlocal_db_url
    # Para SQLite, asegúrate de que la carpeta exista (p.ej. data/).
    if url.startswith("sqlite:///"):
        path = url.removeprefix("sqlite:///")
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db() -> None:
    """Crea las tablas si no existen."""
    Base.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    """Context manager para una sesión transaccional."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
