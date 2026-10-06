"""Guardado de las fotos de las prendas.

Si SUPABASE_URL está configurada, las fotos se suben a Supabase Storage (lo
que se usa en la nube, donde el disco del servidor se borra en cada deploy).
Si no, se guardan en UPLOAD_DIR y se sirven desde /uploads (desarrollo local).
"""

import uuid
from pathlib import Path

import httpx
from fastapi import HTTPException, UploadFile

from app.core.config import settings

UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _use_supabase() -> bool:
    return bool(settings.supabase_url and settings.supabase_service_key)


def _supabase_object_url(filename: str, public: bool = False) -> str:
    base = settings.supabase_url.rstrip("/")
    scope = "object/public" if public else "object"
    return f"{base}/storage/v1/{scope}/{settings.supabase_bucket}/{filename}"


def save_garment_image(file: UploadFile) -> str:
    extension = Path(file.filename or "").suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{extension}"
    content = file.file.read()

    if _use_supabase():
        headers = {
            "apikey": settings.supabase_service_key,
            "Content-Type": file.content_type or "application/octet-stream",
        }
        # La clave legacy service_role es un JWT y también va como Bearer; las
        # claves nuevas (sb_secret_...) solo van en "apikey".
        if settings.supabase_service_key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {settings.supabase_service_key}"
        response = httpx.post(_supabase_object_url(filename), content=content, headers=headers, timeout=30)
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail="No se pudo guardar la imagen.")
        return filename

    with (UPLOAD_DIR / filename).open("wb") as out:
        out.write(content)
    return filename


def image_path_to_url(image_path: str) -> str:
    if _use_supabase():
        return _supabase_object_url(image_path, public=True)
    return f"/uploads/{image_path}"
