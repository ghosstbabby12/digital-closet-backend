import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.weather import WeatherOut

OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


async def get_current_weather(lat: float, lon: float) -> WeatherOut:
    if not settings.openweather_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENWEATHER_API_KEY no está configurada en el backend (.env).",
        )

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
