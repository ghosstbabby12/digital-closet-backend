"""Guardado de las fotos de las prendas y del cuerpo de cada usuario.

Si SUPABASE_URL está configurada, las fotos se suben a Supabase Storage (lo
que se usa en la nube, donde el disco del servidor se borra en cada deploy).
Si no, se guardan en UPLOAD_DIR y se sirven desde /uploads (desarrollo local).

Las prendas van a un bucket público. La foto del cuerpo va a un bucket privado
y solo se accede a ella con enlaces firmados que expiran.
"""

import uuid
from pathlib import Path

import httpx
from fastapi import HTTPException, UploadFile

from app.core.config import settings

UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SIGNED_URL_SECONDS = 24 * 60 * 60


def _use_supabase() -> bool:
    return bool(settings.supabase_url and settings.supabase_service_key)


def _storage_base() -> str:
    return f"{settings.supabase_url.rstrip('/')}/storage/v1"


def _supabase_object_url(filename: str, public: bool = False) -> str:
    scope = "object/public" if public else "object"
    return f"{_storage_base()}/{scope}/{settings.supabase_bucket}/{filename}"


def _auth_headers() -> dict[str, str]:
    headers = {"apikey": settings.supabase_service_key}
    # La clave legacy service_role es un JWT y también va como Bearer; las
    # claves nuevas (sb_secret_...) solo van en "apikey".
    if settings.supabase_service_key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {settings.supabase_service_key}"
    return headers


def _save(content: bytes, extension: str, content_type: str, object_url: str | None = None) -> str:
    filename = f"{uuid.uuid4().hex}{extension}"

    if _use_supabase():
        url = f"{object_url}/{filename}" if object_url else _supabase_object_url(filename)
        response = httpx.post(
            url,
            content=content,
            headers={**_auth_headers(), "Content-Type": content_type},
            timeout=30,
        )
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail="No se pudo guardar la imagen.")
        return filename

    with (UPLOAD_DIR / filename).open("wb") as out:
        out.write(content)
    return filename


def save_garment_image(file: UploadFile) -> str:
    extension = Path(file.filename or "").suffix or ".jpg"
    return _save(file.file.read(), extension, file.content_type or "application/octet-stream")


def save_garment_cutout(content: bytes) -> str:
    return _save(content, ".png", "image/png")


def read_garment_image(image_path: str) -> bytes:
    if _use_supabase():
        try:
            response = httpx.get(_supabase_object_url(image_path, public=True), timeout=30)
        except httpx.HTTPError:
            raise HTTPException(status_code=502, detail="No se pudo leer la imagen de la prenda.")
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail="No se pudo leer la imagen de la prenda.")
        return response.content
    return (UPLOAD_DIR / image_path).read_bytes()


def image_path_to_url(image_path: str) -> str:
    if _use_supabase():
        return _supabase_object_url(image_path, public=True)
    return f"/uploads/{image_path}"


def _private_bucket_url() -> str:
    return f"{_storage_base()}/object/{settings.supabase_private_bucket}"


def save_body_photo(content: bytes) -> str:
    return _save(content, ".png", "image/png", object_url=_private_bucket_url() if _use_supabase() else None)


def body_photo_url(filename: str) -> str:
    if not _use_supabase():
        return f"/uploads/{filename}"
    try:
        response = httpx.post(
            f"{_storage_base()}/object/sign/{settings.supabase_private_bucket}/{filename}",
            json={"expiresIn": SIGNED_URL_SECONDS},
            headers=_auth_headers(),
            timeout=30,
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="No se pudo obtener tu foto.")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="No se pudo obtener tu foto.")
    return f"{_storage_base()}{response.json()['signedURL']}"


def delete_body_photo(filename: str) -> None:
    if not _use_supabase():
        (UPLOAD_DIR / filename).unlink(missing_ok=True)
        return
    try:
        response = httpx.delete(f"{_private_bucket_url()}/{filename}", headers=_auth_headers(), timeout=30)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="No se pudo borrar tu foto.")
    if response.status_code >= 400 and response.status_code != 404:
        raise HTTPException(status_code=502, detail="No se pudo borrar tu foto.")
