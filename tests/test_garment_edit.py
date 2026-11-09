import httpx
import pytest

from app.core.config import settings
from app.services import background_removal
from tests.test_cutouts import auth_headers, client, session_factory  # noqa: F401


@pytest.fixture
def removebg(monkeypatch):
    monkeypatch.setattr(background_removal.httpx, "post", lambda url, **kwargs: httpx.Response(200, content=b"png"))
    monkeypatch.setattr(settings, "removebg_api_key", "clave")


def create(client, headers):  # noqa: F811
    return client.post(
        "/garments",
        headers=headers,
        data={"category": "top", "color": "azul", "warmth": "light", "name": "Camisa"},
        files={"image": ("p.jpg", b"jpeg", "image/jpeg")},
    ).json()


def test_editar_cambia_solo_lo_enviado(client):  # noqa: F811
    headers = auth_headers(client)
    garment = create(client, headers)

    response = client.patch(
        f"/garments/{garment['id']}", headers=headers, json={"name": "  Camisa de lino ", "warmth": "medium"}
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Camisa de lino"
    assert updated["warmth"] == "medium"
    assert updated["color"] == "azul"
    assert updated["category"] == "top"
    assert client.get("/garments", headers=headers).json()[0]["name"] == "Camisa de lino"


@pytest.mark.parametrize(
    "payload",
    [{"category": "sombrero"}, {"warmth": "tibio"}, {"name": "x" * 121}, {"color": "y" * 61}, {"category": None}],
)
def test_editar_rechaza_valores_invalidos(client, payload):  # noqa: F811
    headers = auth_headers(client)
    garment = create(client, headers)

    response = client.patch(f"/garments/{garment['id']}", headers=headers, json=payload)

    assert response.status_code == 422
    assert client.get("/garments", headers=headers).json()[0]["category"] == "top"


def test_no_se_puede_editar_ni_borrar_una_prenda_ajena(client):  # noqa: F811
    garment = create(client, auth_headers(client))
    other = auth_headers(client, "otra@example.com")

    assert client.patch(f"/garments/{garment['id']}", headers=other, json={"name": "mía"}).status_code == 404
    assert client.delete(f"/garments/{garment['id']}", headers=other).status_code == 404


def test_borrar_elimina_la_foto_y_el_recorte(client, removebg, tmp_path):  # noqa: F811
    headers = auth_headers(client)
    garment = create(client, headers)
    client.post(f"/garments/{garment['id']}/cutout", headers=headers)
    assert len(list(tmp_path.iterdir())) == 2

    assert client.delete(f"/garments/{garment['id']}", headers=headers).status_code == 204

    assert client.get("/garments", headers=headers).json() == []
    assert list(tmp_path.iterdir()) == []
