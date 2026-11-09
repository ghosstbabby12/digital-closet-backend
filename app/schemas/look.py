from datetime import datetime

from pydantic import BaseModel, Field


class LookGenerateRequest(BaseModel):
    garment_ids: list[int] = Field(min_length=1, max_length=6)


class LookOut(BaseModel):
    id: int
    image_url: str
    garment_ids: list[int]
    created_at: datetime
