from datetime import datetime

from pydantic import BaseModel, Field

from app.models.garment import GarmentCategory, WarmthLevel


class GarmentUpdate(BaseModel):
    """Campos editables de una prenda; los que no se envían no cambian."""

    name: str | None = Field(default=None, max_length=120)
    color: str | None = Field(default=None, max_length=60)
    category: GarmentCategory | None = None
    warmth: WarmthLevel | None = None


class GarmentOut(BaseModel):
    id: int
    name: str
    category: GarmentCategory
    color: str
    warmth: WarmthLevel
    image_url: str
    cutout_url: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
