import json

import httpx
import pytest

from app.core.config import settings
from app.services import garment_autofill
from tests.test_cutouts import auth_headers, client, session_factory  # noqa: F401

VALID = {"name": "Suéter de punto", "color": "verde", "category": "top", "warmth": "heavy"}


class FakeGemini:
    def __init__(self):
        self.calls = []
        self.status_code = 200
        self.status = "completed"
        self.text = json.dumps(VALID)

    def __call__(self, url, **kwargs):
        self.calls.append(kwargs)
        return httpx.Response(
            self.status_code,
            json={
                "status": self.status,
                "steps": [
                    {"type": "thought", "content": []},
                    {"type": "model_output", "content": [{"type": "text", "text": self.text}]},
                ],
            },
        )


@pytest.fixture
def gemini(monkeypatch):
    fake = FakeGemini()
    monkeypatch.setattr(garment_autofill.httpx, "post", fake)
    monkeypatch.setattr(settings, "gemini_api_key", "clave-de-prueba")
    return fake


def suggest(client, headers, content=b"jpeg", content_type="image/jpeg"):  # noqa: F811
    return client.post(
        "/garments/suggest", headers=headers, files={"image": ("prenda.jpg", content, content_type)}
    )


def test_propone_los_datos_y_no_crea_la_prenda(client, gemini):  # noqa: F811
    headers = auth_headers(client)

    response = suggest(client, headers)

    assert response.status_code == 200
    assert response.json() == VALID
    assert client.get("/garments", headers=headers).json() == []


def test_envia_la_imagen_y_los_valores_permitidos(client, gemini):  # noqa: F811
    suggest(client, auth_headers(client), content=b"abc")

    request = gemini.calls[0]
    image = request["json"]["input"][1]
    assert image == {"type": "image", "data": "YWJj", "mime_type": "image/jpeg"}
    assert request["headers"]["x-goog-api-key"] == "clave-de-prueba"
    schema = request["json"]["response_format"]["schema"]["properties"]
    assert "outerwear" in schema["category"]["enum"]
    assert schema["warmth"]["enum"] == ["light", "medium", "heavy"]


def test_requiere_sesion(client, gemini):  # noqa: F811
    response = client.post("/garments/suggest", files={"image": ("p.jpg", b"x", "image/jpeg")})

    assert response.status_code in (401, 403)
    assert gemini.calls == []


def test_rechaza_formato_no_soportado(client, gemini):  # noqa: F811
    response = suggest(client, auth_headers(client), content_type="application/pdf")

    assert response.status_code == 400
    assert gemini.calls == []


def test_rechaza_foto_demasiado_grande(client, gemini):  # noqa: F811
    response = suggest(client, auth_headers(client), content=b"x" * (12 * 1024 * 1024 + 1))

    assert response.status_code == 413
    assert gemini.calls == []


def test_limite_agotado(client, gemini):  # noqa: F811
    gemini.status_code = 429

    response = suggest(client, auth_headers(client))

    assert response.status_code == 503
    assert "límite" in response.json()["detail"]


@pytest.mark.parametrize(
    "text",
    [
        "esto no es json",
        "",
        json.dumps({**VALID, "category": "sombrero"}),
        json.dumps({"name": "Falta casi todo"}),
    ],
)
def test_respuesta_invalida_da_un_error_claro(client, gemini, text):  # noqa: F811
    gemini.text = text

    response = suggest(client, auth_headers(client))

    assert response.status_code == 502
    assert isinstance(response.json()["detail"], str)


def test_respuesta_incompleta_da_un_error_claro(client, gemini):  # noqa: F811
    gemini.status = "incomplete"

    assert suggest(client, auth_headers(client)).status_code == 502


def test_sin_clave_responde_con_un_mensaje_claro(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "gemini_api_key", "")

    response = suggest(client, auth_headers(client))

    assert response.status_code == 503
    assert "autocompletado" in response.json()["detail"]
