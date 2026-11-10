from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints, model_validator

from app.schemas.garment import GarmentOut
from app.schemas.weather import WeatherOut


EventTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class OutfitGenerateRequest(BaseModel):
    occasion: str
    lat: float
    lon: float
    # Para armar el outfit de un evento del calendario: van juntos o ninguno.
    event_title: EventTitle | None = None
    event_date: date | None = None

    @model_validator(mode="after")
    def _event_complete(self):
        if (self.event_title is None) != (self.event_date is None):
            raise ValueError("El evento necesita nombre y fecha.")
        return self


class OutfitOut(BaseModel):
    id: int
    occasion: str
    weather_temp_c: float
    weather_condition: str
    explanation: str
    garments: list[GarmentOut]
    event_title: str | None = None
    event_date: date | None = None
    created_at: datetime

    class Config:
        from_attributes = True
