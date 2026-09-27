from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.weather import WeatherOut
from app.services.weather_service import get_current_weather

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("", response_model=WeatherOut)
async def read_weather(lat: float, lon: float, current_user: User = Depends(get_current_user)):
    return await get_current_weather(lat, lon)
