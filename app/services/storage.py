import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings

UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def save_garment_image(file: UploadFile) -> str:
    extension = Path(file.filename or "").suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{extension}"
    destination = UPLOAD_DIR / filename
    with destination.open("wb") as out:
        out.write(file.file.read())
    return filename


def image_path_to_url(image_path: str) -> str:
    return f"/uploads/{image_path}"
