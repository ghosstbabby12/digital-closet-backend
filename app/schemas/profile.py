from pydantic import BaseModel


class BodyPhotoOut(BaseModel):
    image_url: str | None
