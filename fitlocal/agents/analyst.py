"""Agente analista de datos.

Lee las métricas recientes (Garmin + nutrición + actividades) y detecta
tendencias y correlaciones. No da el plan — solo el diagnóstico de los datos.
"""

from __future__ import annotations

from fitlocal.config import settings
from fitlocal.core.store import AirtableStore
from fitlocal.agents.base import as_json, get_client, text_of

SYSTEM = (
    "Eres un analista de datos de salud y rendimiento. Te dan métricas diarias "
    "(sueño, FC en reposo, HRV, estrés, Body Battery, pasos), entrenamientos y "
    "registros de alimentación. Tu trabajo es detectar tendencias, anomalías y "
    "correlaciones relevantes, de forma objetiva y basada en los datos. "
    "No inventes datos que no estén presentes. Responde en español, conciso."
)


class AnalystAgent:
    def __init__(self, store: AirtableStore | None = None, model: str | None = None):
        self.store = store or AirtableStore()
        self.model = model or settings.fitlocal_model
        self.client = get_client()

    def gather(self, days: int = 14) -> dict:
        """Reúne los datos recientes que alimentan el análisis."""
        return {
            "metricas_diarias": self.store.recent_daily_metrics(days),
            "actividades": self.store.recent_activities(days),
            "nutricion": self.store.recent_nutrition(days),
        }

    def analyze(self, days: int = 14) -> str:
        data = self.gather(days)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Estos son mis datos de los últimos {days} días. "
                        "Analiza tendencias, anomalías y correlaciones.\n\n"
                        f"{as_json(data)}"
                    ),
                }
            ],
        )
        return text_of(response)
