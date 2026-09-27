from datetime import datetime

from pydantic import BaseModel

from app.models.garment import GarmentCategory, WarmthLevel


class GarmentOut(BaseModel):
    id: int
    name: str
    category: GarmentCategory
    color: str
    warmth: WarmthLevel
    image_url: str
    created_at: datetime

    class Config:
        from_attributes = True
