from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.weather import CityOut, WeatherOut
from app.services.weather_service import get_current_weather, search_cities

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("", response_model=WeatherOut)
async def read_weather(lat: float, lon: float, current_user: User = Depends(get_current_user)):
    return await get_current_weather(lat, lon)


@router.get("/cities", response_model=list[CityOut])
async def find_cities(
    q: str = Query(min_length=2, max_length=100),
    current_user: User = Depends(get_current_user),
):
    return await search_cities(q.strip())
