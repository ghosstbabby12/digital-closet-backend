import unicodedata

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.weather import CityOut, WeatherOut

OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"


def _require_api_key() -> None:
    if not settings.openweather_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENWEATHER_API_KEY no está configurada en el backend (.env).",
        )


async def search_cities(query: str) -> list[CityOut]:
    """Busca ciudades de todo el mundo por nombre (máximo 5 resultados)."""
    _require_api_key()
    params = {"q": query, "limit": 5, "appid": settings.openweather_api_key}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(GEOCODING_URL, params=params)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="No se pudo buscar la ciudad.")
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="No se pudo buscar la ciudad.")

    # La API repite ciudades (p. ej. "Bogota" y "Bogotá"): se agrupan sin
    # distinguir tildes ni mayúsculas y se conserva el nombre con tildes.
    cities: dict[tuple, CityOut] = {}
    for place in response.json():
        city = CityOut(
            name=place["name"],
            state=place.get("state"),
            country=place["country"],
            lat=place["lat"],
            lon=place["lon"],
        )
        key = (_fold(city.name), _fold(city.state or ""), city.country)
        existing = cities.get(key)
        if existing is None:
            cities[key] = city
        elif _accent_count(city.name) > _accent_count(existing.name):
            cities[key] = existing.model_copy(update={"name": city.name})
    return list(cities.values())


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()


def _accent_count(text: str) -> int:
    return sum(1 for ch in text if not ch.isascii())


async def get_current_weather(lat: float, lon: float) -> WeatherOut:
    _require_api_key()

    params = {
        "lat": lat,
        "lon": lon,
        "appid": settings.openweather_api_key,
        "units": "metric",
        "lang": "es",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(OPENWEATHER_URL, params=params)

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="No se pudo obtener el clima.")

    data = response.json()
    weather = data["weather"][0]
    return WeatherOut(
        temp_c=data["main"]["temp"],
        feels_like_c=data["main"]["feels_like"],
        condition=weather["description"],
        condition_main=weather["main"],
        city=data.get("name", ""),
    )
