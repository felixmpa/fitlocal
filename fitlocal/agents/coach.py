"""Agente coach / orquestador.

Junta el análisis de datos con tu meta concreta y te da sugerencias accionables.
Es el agente que "habla contigo": traduce los números en un plan.
"""

from __future__ import annotations

from fitlocal.config import settings
from fitlocal.core.store import AirtableStore
from fitlocal.agents.analyst import AnalystAgent
from fitlocal.agents.base import get_client, text_of

SYSTEM = (
    "Eres un coach de salud y rendimiento. Tu objetivo es ayudar al usuario a "
    "alcanzar su META concreta. Recibes un análisis de datos ya hecho por un "
    "analista. Conviértelo en sugerencias claras, priorizadas y accionables, "
    "siempre conectadas con la meta. Sé honesto sobre lo que los datos no "
    "permiten afirmar. No des consejo médico; ante señales preocupantes, "
    "recomienda consultar a un profesional. Responde en español."
)


class CoachAgent:
    def __init__(self, store: AirtableStore | None = None, model: str | None = None):
        self.store = store or AirtableStore()
        self.model = model or settings.fitlocal_model
        self.client = get_client()
        self.analyst = AnalystAgent(store=self.store, model=self.model)

    def advise(self, days: int = 14, goal: str | None = None) -> str:
        """Genera sugerencias para acercarte a tu meta."""
        goal = goal or settings.fitlocal_goal
        analysis = self.analyst.analyze(days)

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
                        f"MI META: {goal}\n\n"
                        f"ANÁLISIS DE MIS DATOS (últimos {days} días):\n{analysis}\n\n"
                        "Dame sugerencias concretas y priorizadas para acercarme a mi meta."
                    ),
                }
            ],
        )
        return text_of(response)
