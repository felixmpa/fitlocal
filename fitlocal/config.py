"""Configuración central, leída desde variables de entorno (.env)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ajustes de la aplicación.

    Los valores se cargan desde variables de entorno o desde un archivo `.env`.
    Ver `.env.example` para la lista completa.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
    )

    # --- Garmin ---
    garmin_email: str | None = None
    garmin_password: str | None = None

    # --- Anthropic ---
    anthropic_api_key: str | None = None

    # --- App ---
    # Modelo por defecto para los agentes. claude-opus-4-8 es el más capaz;
    # para reducir coste en llamadas frecuentes puedes usar claude-sonnet-4-6.
    fitlocal_model: str = "claude-opus-4-8"
    fitlocal_goal: str = "Mejorar mi salud general y consistencia"
    fitlocal_db_url: str = "sqlite:///data/fitlocal.db"


settings = Settings()
