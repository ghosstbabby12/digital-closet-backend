from datetime import datetime

from pydantic import BaseModel


class BodyPhotoOut(BaseModel):
    image_url: str | None


class ProfileOut(BaseModel):
    id: int
    email: str
    created_at: datetime
    garment_count: int
    outfit_count: int
    look_count: int
    has_body_photo: bool
