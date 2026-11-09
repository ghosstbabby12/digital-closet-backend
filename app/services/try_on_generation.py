"""Prueba virtual con la API de FASHN: dibuja al usuario con sus prendas puestas.

FASHN viste una prenda por llamada (1 crédito, unos USD 0.075; las llamadas que
fallan no se cobran). Para un outfit se encadenan las llamadas en orden de
vestir, usando cada resultado como la foto de la persona en la siguiente.
"""

import base64
import io
import logging
import time

import httpx
from fastapi import HTTPException
from PIL import Image

from app.core.config import settings
from app.models.garment import Garment, GarmentCategory

FASHN_URL = "https://api.fashn.ai/v1"
POLL_SECONDS = 1
MAX_WAIT_SECONDS = 90

# El logger de uvicorn es el que aparece en los logs de Render.
logger = logging.getLogger("uvicorn.error")

# Categorías que FASHN sabe vestir y orden en que se ponen: lo de abajo primero,
# la chaqueta al final para que quede encima de todo.
FASHN_CATEGORIES = {
    GarmentCategory.bottom: ("bottoms", 0),
    GarmentCategory.dress: ("one-pieces", 1),
    GarmentCategory.top: ("tops", 2),
    GarmentCategory.outerwear: ("tops", 3),
}


def can_try_on(category: GarmentCategory) -> bool:
    return category in FASHN_CATEGORIES


def wearing_order(garments: list[Garment]) -> list[Garment]:
    return sorted(garments, key=lambda g: FASHN_CATEGORIES[g.category][1])


def _flatten(png: bytes, background: tuple[int, int, int]) -> bytes:
    """Pone el recorte transparente sobre un fondo liso y lo devuelve como JPEG."""
    image = Image.open(io.BytesIO(png)).convert("RGBA")
    canvas = Image.new("RGB", image.size, background)
    canvas.paste(image, mask=image.getchannel("A"))
    out = io.BytesIO()
    canvas.save(out, format="JPEG", quality=92)
    return out.getvalue()


def _data_uri(content: bytes, mime_type: str) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(content).decode('ascii')}"


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.fashn_api_key}"}


def _raise_for_api_error(response: httpx.Response) -> None:
    if response.status_code == 200:
        return
    if response.status_code == 401:
        raise HTTPException(status_code=503, detail="La clave de FASHN no es válida. Revisa FASHN_API_KEY.")
    if response.status_code == 429:
        name = ""
        try:
            name = response.json().get("error", "")
        except ValueError:
            pass
        if "OutOfCredits" in str(name):
            raise HTTPException(status_code=503, detail="Se acabaron los créditos de FASHN. Recarga para seguir.")
        raise HTTPException(status_code=503, detail="El servicio de prueba está saturado. Intenta en un minuto.")
    raise HTTPException(status_code=502, detail="El servicio de prueba no está disponible.")


def _run_one(model_image: str, garment: Garment, garment_png: bytes, *, final: bool) -> str:
    """Viste una prenda y devuelve la imagen resultante como data URI."""
    category, _ = FASHN_CATEGORIES[garment.category]
    started = time.monotonic()
    try:
        response = httpx.post(
            f"{FASHN_URL}/run",
            headers=_headers(),
            json={
                "model_name": "tryon-v1.6",
                "inputs": {
                    "model_image": model_image,
                    "garment_image": _data_uri(_flatten(garment_png, (255, 255, 255)), "image/jpeg"),
                    "category": category,
                    "garment_photo_type": "flat-lay",
                    "mode": settings.fashn_mode,
                    # Los pasos intermedios se reenvían como entrada del siguiente:
                    # en JPEG pesan mucho menos y el envío es más rápido.
                    "output_format": "png" if final else "jpeg",
                    "return_base64": True,
                },
            },
            timeout=30,
        )
        _raise_for_api_error(response)
        prediction_id = response.json()["id"]

        waited = 0.0
        while waited < MAX_WAIT_SECONDS:
            time.sleep(POLL_SECONDS)
            waited += POLL_SECONDS
            status = httpx.get(f"{FASHN_URL}/status/{prediction_id}", headers=_headers(), timeout=30)
            _raise_for_api_error(status)
            prediction = status.json()
            if prediction.get("status") == "completed":
                logger.info("FASHN %s (%s) listo en %.1f s", category, settings.fashn_mode, time.monotonic() - started)
                return _as_data_uri(prediction["output"][0])
            if prediction.get("status") == "failed":
                _raise_for_failed(prediction.get("error") or {})
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="No se pudo conectar con el servicio de prueba.")
    raise HTTPException(status_code=504, detail="La prueba tardó demasiado. Intenta de nuevo.")


def _as_data_uri(output: str) -> str:
    """Con return_base64 la salida ya es base64; si llega una URL, se descarga."""
    if output.startswith("data:"):
        return output
    if output.startswith("http"):
        downloaded = httpx.get(output, timeout=30)
        downloaded.raise_for_status()
        return _data_uri(downloaded.content, "image/png")
    return _data_uri(base64.b64decode(output), "image/png")


def _raise_for_failed(error: dict) -> None:
    name = error.get("name", "")
    if name == "ContentModerationError":
        raise HTTPException(status_code=422, detail="La foto o la prenda no pasó la revisión de contenido.")
    if name == "ImageLoadError":
        raise HTTPException(status_code=422, detail="El servicio no pudo leer una de las imágenes.")
    raise HTTPException(status_code=422, detail="No se pudo probar esta prenda. Intenta con otra foto o prenda.")


def generate_try_on(body_photo: bytes, garments: list[tuple[Garment, bytes]]) -> tuple[bytes, str, str]:
    """Viste las prendas una a una sobre la foto. Devuelve (imagen, extensión, tipo MIME)."""
    if not settings.fashn_api_key:
        raise HTTPException(status_code=503, detail="La prueba con IA no está configurada en el servidor.")

    current = _data_uri(_flatten(body_photo, (236, 233, 226)), "image/jpeg")
    for index, (garment, garment_png) in enumerate(garments):
        current = _run_one(current, garment, garment_png, final=index == len(garments) - 1)

    header, _, data = current.partition(",")
    image = base64.b64decode(data)
    if "image/jpeg" in header:
        return image, ".jpg", "image/jpeg"
    return image, ".png", "image/png"
