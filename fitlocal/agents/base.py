"""Utilidades compartidas por los agentes."""

from __future__ import annotations

import json

import anthropic

from fitlocal.config import settings


def get_client() -> anthropic.Anthropic:
    """Cliente de Anthropic configurado desde el entorno."""
    if not settings.anthropic_api_key:
        raise RuntimeError("Falta ANTHROPIC_API_KEY en tu .env.")
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def text_of(response) -> str:
    """Extrae el texto de una respuesta de la Messages API."""
    return "".join(b.text for b in response.content if b.type == "text").strip()


def as_json(data) -> str:
    """Serializa datos para incrustarlos en un prompt de forma legible."""
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)
