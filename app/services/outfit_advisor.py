"""Capa de IA que arma el outfit.

Expone una interfaz (OutfitAdvisor) para que la lógica de negocio no dependa
de cómo se genera la sugerencia. Hoy solo existe un motor basado en reglas
(sin costo, sin API key). Cuando se decida el proveedor de IA (Claude u
OpenAI), se agrega una nueva clase que implemente `suggest` usando visión +
razonamiento sobre las fotos reales, y se conecta en `get_outfit_advisor`
según la variable de entorno AI_PROVIDER.
"""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.config import settings
from app.models.garment import Garment, GarmentCategory, WarmthLevel
from app.schemas.weather import WeatherOut

WARMTH_RANK = {WarmthLevel.light: 0, WarmthLevel.medium: 1, WarmthLevel.heavy: 2}

DRESSY_OCCASIONS = {"fiesta", "formal", "cita", "boda", "gala"}
COLD_CONDITIONS = {"rain", "drizzle", "thunderstorm", "snow", "mist", "fog"}


@dataclass
class OutfitSuggestion:
    garments: list[Garment]
    explanation: str


class OutfitAdvisor(ABC):
    @abstractmethod
    def suggest(self, garments: list[Garment], weather: WeatherOut, occasion: str) -> OutfitSuggestion:
        ...


def _desired_warmth(temp_c: float) -> WarmthLevel:
    if temp_c >= 25:
        return WarmthLevel.light
    if temp_c >= 16:
        return WarmthLevel.medium
    return WarmthLevel.heavy


def _pick_by_category(
    garments: list[Garment], category: GarmentCategory, desired: WarmthLevel
) -> Garment | None:
    candidates = [g for g in garments if g.category == category]
    if not candidates:
        return None
    desired_rank = WARMTH_RANK[desired]
    candidates.sort(key=lambda g: abs(WARMTH_RANK[g.warmth] - desired_rank))
    closest_distance = abs(WARMTH_RANK[candidates[0].warmth] - desired_rank)
    best = [g for g in candidates if abs(WARMTH_RANK[g.warmth] - desired_rank) == closest_distance]
    return random.choice(best)


class RuleBasedOutfitAdvisor(OutfitAdvisor):
    """Arma el outfit combinando categoría de prenda, nivel de abrigo y ocasión.

    No usa un modelo de lenguaje: es determinista sobre reglas simples de
    estilismo (abrigo según temperatura, vestido vs. top+pantalón según
    ocasión, accesorio en ocasiones formales). Sirve como implementación por
    defecto funcional mientras se decide y conecta un proveedor de IA real.
    """

    def suggest(self, garments: list[Garment], weather: WeatherOut, occasion: str) -> OutfitSuggestion:
        if not garments:
            raise ValueError("El clóset está vacío: sube al menos una prenda antes de generar un outfit.")

        desired = _desired_warmth(weather.temp_c)
        occasion_key = occasion.strip().lower()
        chosen: list[Garment] = []

        wants_dress = occasion_key in DRESSY_OCCASIONS
        dress = _pick_by_category(garments, GarmentCategory.dress, desired) if wants_dress else None
        if dress:
            chosen.append(dress)
        else:
            top = _pick_by_category(garments, GarmentCategory.top, desired)
            bottom = _pick_by_category(garments, GarmentCategory.bottom, desired)
            chosen.extend(g for g in (top, bottom) if g)

        shoes = _pick_by_category(garments, GarmentCategory.shoes, desired)
        if shoes:
            chosen.append(shoes)

        needs_outerwear = weather.temp_c < 18 or weather.condition_main.lower() in COLD_CONDITIONS
        if needs_outerwear:
            outer_desired = WarmthLevel.heavy if weather.temp_c < 12 else WarmthLevel.medium
            outerwear = _pick_by_category(garments, GarmentCategory.outerwear, outer_desired)
            if outerwear:
                chosen.append(outerwear)

        if occasion_key in DRESSY_OCCASIONS:
            accessory = _pick_by_category(garments, GarmentCategory.accessory, desired)
            if accessory:
                chosen.append(accessory)

        if not chosen:
            raise ValueError(
                "No hay suficientes prendas en el clóset para armar un outfit para esa ocasión y clima."
            )

        explanation = self._build_explanation(chosen, weather, occasion_key, needs_outerwear)
        return OutfitSuggestion(garments=chosen, explanation=explanation)

    @staticmethod
    def _build_explanation(
        chosen: list[Garment], weather: WeatherOut, occasion_key: str, needs_outerwear: bool
    ) -> str:
        names = [f"{g.name or g.category.value} {g.color}".strip() for g in chosen]
        pieces = ", ".join(names[:-1]) + (f" y {names[-1]}" if len(names) > 1 else names[0])

        clima_frase = f"{weather.temp_c:.0f}°C y {weather.condition}"
        razones = [f"Elegí {pieces} porque hoy hay {clima_frase}"]

        if needs_outerwear:
            razones.append("y conviene una capa extra para no pasar frío")
        if occasion_key:
            razones.append(f"pensando en una ocasión {occasion_key}")

        return ", ".join(razones) + "."


def get_outfit_advisor() -> OutfitAdvisor:
    provider = settings.ai_provider.lower()
    if provider == "rule_based":
        return RuleBasedOutfitAdvisor()
    raise NotImplementedError(
            f"AI_PROVIDER='{provider}' aún no está implementado. "
            "Agrega una clase OutfitAdvisor (ej. ClaudeOutfitAdvisor) en este archivo "
            "y regístrala aquí."
    )
