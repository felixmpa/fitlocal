"""Agente nutricionista.

Interpreta una descripción de comida en lenguaje natural, estima calorías y
macros, y lo registra en Airtable. Usa *structured outputs* para garantizar
que la respuesta tenga la forma exacta que necesitamos.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from fitlocal.config import settings
from fitlocal.core.store import AirtableStore
from fitlocal.agents.base import as_json, get_client

SYSTEM = (
    "Eres un nutricionista experto. Recibes la descripción en lenguaje natural "
    "de una comida y estimas sus calorías y macronutrientes. Usa porciones "
    "estándar cuando la cantidad sea ambigua y refléjalo en la confianza. "
    "Responde siempre en español en los nombres de los alimentos."
)


class FoodItem(BaseModel):
    name: str
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float


class MealAnalysis(BaseModel):
    meal: str = Field(description="desayuno, almuerzo, cena o snack")
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    items: list[FoodItem]
    confidence: float = Field(description="0.0 a 1.0: qué tan segura es la estimación")


class NutritionAgent:
    def __init__(self, store: AirtableStore | None = None, model: str | None = None):
        self.store = store or AirtableStore()
        self.model = model or settings.fitlocal_model
        self.client = get_client()

    def analyze(self, description: str, meal: str | None = None) -> MealAnalysis:
        """Interpreta el texto y devuelve el análisis estructurado (sin guardar)."""
        hint = f" La comida es: {meal}." if meal else ""
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=2000,
            system=SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"Analiza esta comida y estima sus macros.{hint}\n\n{description}",
                }
            ],
            output_format=MealAnalysis,
        )
        return response.parsed_output

    def log(
        self,
        description: str,
        meal: str | None = None,
        day: date | None = None,
    ) -> dict:
        """Interpreta y registra la comida en Airtable. Devuelve el análisis."""
        analysis = self.analyze(description, meal)
        day = day or date.today()
        self.store.add_nutrition(
            {
                "Logged At": _now_iso(),
                "Day": day.isoformat(),
                "Meal": analysis.meal,
                "Description": description,
                "Calories": analysis.calories,
                "Protein g": analysis.protein_g,
                "Carbs g": analysis.carbs_g,
                "Fat g": analysis.fat_g,
                "Items": as_json([i.model_dump() for i in analysis.items]),
                "Confidence": analysis.confidence,
            }
        )
        return analysis.model_dump()


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")
