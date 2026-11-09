from pydantic import BaseModel


class WeatherOut(BaseModel):
    temp_c: float
    feels_like_c: float
    condition: str
    condition_main: str
    city: str


class CityOut(BaseModel):
    name: str
    state: str | None = None
    country: str
    lat: float
    lon: float
