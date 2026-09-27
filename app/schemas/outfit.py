from datetime import datetime

from pydantic import BaseModel

from app.schemas.garment import GarmentOut
from app.schemas.weather import WeatherOut


class OutfitGenerateRequest(BaseModel):
    occasion: str
    lat: float
    lon: float


class OutfitOut(BaseModel):
    id: int
    occasion: str
    weather_temp_c: float
    weather_condition: str
    explanation: str
    garments: list[GarmentOut]
    created_at: datetime

    class Config:
        from_attributes = True
