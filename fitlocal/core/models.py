"""Modelo de datos unificado.

La idea clave: tablas estructuradas para lo que consultamos seguido + una tabla
`raw_snapshots` que guarda el JSON crudo de cada fuente, tal cual. Así nunca
perdemos datos aunque todavía no los hayamos modelado en columnas.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class DailyMetric(Base):
    """Una fila por día: el resumen de bienestar normalizado de Garmin."""

    __tablename__ = "daily_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(Date, unique=True, index=True)

    steps: Mapped[int | None] = mapped_column(Integer)
    resting_hr: Mapped[int | None] = mapped_column(Integer)
    sleep_score: Mapped[int | None] = mapped_column(Integer)
    sleep_seconds: Mapped[int | None] = mapped_column(Integer)
    stress_avg: Mapped[int | None] = mapped_column(Integer)
    body_battery_high: Mapped[int | None] = mapped_column(Integer)
    body_battery_low: Mapped[int | None] = mapped_column(Integer)
    hrv: Mapped[int | None] = mapped_column(Integer)
    vo2max: Mapped[float | None] = mapped_column(Float)
    training_readiness: Mapped[int | None] = mapped_column(Integer)
    calories_burned: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Float)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Activity(Base):
    """Un registro por entrenamiento/actividad."""

    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    garmin_activity_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    day: Mapped[date] = mapped_column(Date, index=True)

    activity_type: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str | None] = mapped_column(String(255))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    distance_m: Mapped[float | None] = mapped_column(Float)
    avg_hr: Mapped[int | None] = mapped_column(Integer)
    max_hr: Mapped[int | None] = mapped_column(Integer)
    calories: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Nutrition(Base):
    """Una comida registrada manualmente e interpretada por el agente nutricionista."""

    __tablename__ = "nutrition"

    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    meal: Mapped[str | None] = mapped_column(String(32))  # desayuno / almuerzo / cena / snack

    description: Mapped[str] = mapped_column(Text)  # lo que escribió el usuario
    calories: Mapped[int | None] = mapped_column(Integer)
    protein_g: Mapped[float | None] = mapped_column(Float)
    carbs_g: Mapped[float | None] = mapped_column(Float)
    fat_g: Mapped[float | None] = mapped_column(Float)
    items: Mapped[list | None] = mapped_column(JSON)  # desglose por alimento
    confidence: Mapped[float | None] = mapped_column(Float)  # 0..1, seguridad del agente

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RawSnapshot(Base):
    """El JSON completo de cada llamada a una fuente, sin procesar.

    Red de seguridad: si mañana necesitamos una métrica que hoy no modelamos,
    ya la tenemos guardada aquí.
    """

    __tablename__ = "raw_snapshots"
    __table_args__ = (
        UniqueConstraint("source", "endpoint", "day", name="uq_snapshot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)  # p.ej. "garmin"
    endpoint: Mapped[str] = mapped_column(String(64))  # p.ej. "sleep", "stats"
    day: Mapped[date] = mapped_column(Date, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
