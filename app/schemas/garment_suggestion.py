from pydantic import BaseModel, Field

from app.models.garment import GarmentCategory, WarmthLevel


class GarmentSuggestion(BaseModel):
    name: str = Field(max_length=120)
    color: str = Field(max_length=60)
    category: GarmentCategory
    warmth: WarmthLevel
