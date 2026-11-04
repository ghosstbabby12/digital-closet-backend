"""Quita el fondo de una imagen con la API de remove.bg.

Se usa un servicio externo porque hacerlo en el servidor requiere más de 1 GB
de memoria (medido con rembg) y el plan gratis de Render solo tiene 512 MB.
"""

import httpx
from fastapi import HTTPException

from app.core.config import settings

REMOVE_BG_URL = "https://api.remove.bg/v1.0/removebg"


def remove_background(content: bytes, content_type: str) -> bytes:
    """Devuelve la imagen como PNG con fondo transparente."""
    if not settings.removebg_api_key:
        raise HTTPException(status_code=503, detail="El recorte de fotos no está configurado en el servidor.")

    try:
        response = httpx.post(
            REMOVE_BG_URL,
            headers={"X-Api-Key": settings.removebg_api_key},
            files={"image_file": ("image", content, content_type)},
            # "preview" es la resolución incluida en el plan gratis.
            data={"size": "preview", "format": "png"},
            timeout=45,
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="No se pudo conectar con el servicio de recorte.")

    if response.status_code == 200:
        return response.content
    if response.status_code == 400:
        raise HTTPException(status_code=422, detail="No se pudo recortar esa foto. Prueba con otra.")
    if response.status_code in (402, 429):
        raise HTTPException(status_code=503, detail="Se agotó el límite de recortes. Intenta más tarde.")
    raise HTTPException(status_code=502, detail="El servicio de recorte no está disponible.")
