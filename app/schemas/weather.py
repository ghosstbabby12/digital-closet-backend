from pydantic import BaseModel


class WeatherOut(BaseModel):
    temp_c: float
    feels_like_c: float
    condition: str
    condition_main: str
    city: str
