"""Propone los datos de una prenda a partir de su foto, con la API de Gemini.

En el plan gratis, Google usa lo que se le envía para mejorar sus productos.
Por eso solo se usa con fotos de prendas y la app lo avisa antes de elegir la foto.
"""

import base64

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import settings
from app.models.garment import GarmentCategory, WarmthLevel
from app.schemas.garment_suggestion import GarmentSuggestion

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_API_REVISION = "2026-05-20"

PROMPT = (
    "Describe la prenda principal de la foto para un clóset digital. Responde en español.\n"
    "- name: nombre corto de la prenda, sin marca (por ejemplo: Suéter de punto).\n"
    "- color: su color principal en una o dos palabras, en minúsculas.\n"
    "- category: top (parte de arriba), bottom (parte de abajo), dress (vestido), "
    "outerwear (abrigo o chamarra), shoes (calzado) o accessory (accesorio).\n"
    "- warmth: light (para calor), medium (entretiempo) o heavy (para frío)."
)

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "color": {"type": "string"},
        "category": {"type": "string", "enum": [item.value for item in GarmentCategory]},
        "warmth": {"type": "string", "enum": [item.value for item in WarmthLevel]},
    },
    "required": ["name", "color", "category", "warmth"],
}


def _output_text(interaction: dict) -> str:
    for step in interaction.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for block in step.get("content", []):
            if block.get("type") == "text":
                return block.get("text", "")
    return ""


def suggest_garment_details(content: bytes, content_type: str) -> GarmentSuggestion:
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="El autocompletado no está configurado en el servidor.")

    try:
        response = httpx.post(
            GEMINI_URL,
            headers={
                "x-goog-api-key": settings.gemini_api_key,
                "Api-Revision": GEMINI_API_REVISION,
            },
            json={
                "model": settings.gemini_model,
                "input": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image",
                        "data": base64.b64encode(content).decode("ascii"),
                        "mime_type": content_type,
                    },
                ],
                "response_format": {
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": RESPONSE_SCHEMA,
                },
            },
            timeout=30,
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="No se pudo conectar con el servicio de autocompletado.")

    if response.status_code == 429:
        raise HTTPException(status_code=503, detail="Se agotó el límite de autocompletado. Intenta más tarde.")
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="El servicio de autocompletado no está disponible.")

    interaction = response.json()
    if interaction.get("status") != "completed":
        raise HTTPException(status_code=502, detail="No se pudo analizar esa foto.")
    try:
        return GarmentSuggestion.model_validate_json(_output_text(interaction))
    except ValidationError:
        raise HTTPException(status_code=502, detail="No se pudo analizar esa foto.")
