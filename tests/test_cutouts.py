import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.session import Base, get_db
from app.main import app
from app.models.user import User
from app.services import background_removal, storage

PNG = b"\x89PNG-recorte"


class FakeRemoveBg:
    def __init__(self):
        self.calls = 0
        self.status = 200

    def __call__(self, url, **kwargs):
        self.calls += 1
        return httpx.Response(self.status, content=PNG)


@pytest.fixture
def removebg(monkeypatch):
    fake = FakeRemoveBg()
    monkeypatch.setattr(background_removal.httpx, "post", fake)
    monkeypatch.setattr(settings, "removebg_api_key", "clave-de-prueba")
    return fake


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def client(session_factory, tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_service_key", "")

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth_headers(client, email="ana@example.com"):
    response = client.post("/auth/register", json={"email": email, "password": "secret123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def upload_garment(client, headers):
    response = client.post(
        "/garments",
        headers=headers,
        data={"category": "top"},
        files={"image": ("prenda.jpg", b"jpeg", "image/jpeg")},
    )
    return response.json()


def upload_body_photo(client, headers, content=b"jpeg", content_type="image/jpeg"):
    return client.put(
        "/me/body-photo", headers=headers, files={"image": ("yo.jpg", content, content_type)}
    )


def test_guarda_solo_el_recorte_de_la_foto(client, removebg, tmp_path):
    response = upload_body_photo(client, auth_headers(client))

    assert response.status_code == 200
    assert response.json()["image_url"].endswith(".png")
    saved = list(tmp_path.iterdir())
    assert [path.read_bytes() for path in saved] == [PNG]


def test_cambiar_la_foto_borra_la_anterior(client, removebg, tmp_path):
    headers = auth_headers(client)
    upload_body_photo(client, headers)
    upload_body_photo(client, headers)

    assert len(list(tmp_path.iterdir())) == 1


def test_borrar_la_foto(client, removebg, tmp_path):
    headers = auth_headers(client)
    upload_body_photo(client, headers)

    assert client.delete("/me/body-photo", headers=headers).status_code == 204
    assert client.get("/me/body-photo", headers=headers).json() == {"image_url": None}
    assert list(tmp_path.iterdir()) == []


def test_la_foto_es_de_cada_usuario(client, removebg):
    upload_body_photo(client, auth_headers(client))
    other = auth_headers(client, "otra@example.com")

    assert client.get("/me/body-photo", headers=other).json() == {"image_url": None}


def test_la_foto_requiere_sesion(client):
    assert client.get("/me/body-photo").status_code in (401, 403)


def test_rechaza_formato_no_soportado_sin_gastar_recorte(client, removebg):
    response = upload_body_photo(client, auth_headers(client), content_type="application/pdf")

    assert response.status_code == 400
    assert removebg.calls == 0


def test_rechaza_foto_demasiado_grande_sin_gastar_recorte(client, removebg):
    response = upload_body_photo(client, auth_headers(client), content=b"x" * (12 * 1024 * 1024 + 1))

    assert response.status_code == 413
    assert removebg.calls == 0


@pytest.mark.parametrize("status", [402, 429])
def test_limite_agotado_conserva_la_foto_anterior(client, removebg, status):
    headers = auth_headers(client)
    url = upload_body_photo(client, headers).json()["image_url"]

    removebg.status = status
    response = upload_body_photo(client, headers)

    assert response.status_code == 503
    assert client.get("/me/body-photo", headers=headers).json()["image_url"] == url


def test_sin_clave_responde_con_un_mensaje_claro(client, monkeypatch):
    monkeypatch.setattr(settings, "removebg_api_key", "")

    response = upload_body_photo(client, auth_headers(client))

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)


def test_recorte_de_prenda_no_se_repite(client, removebg):
    headers = auth_headers(client)
    garment = upload_garment(client, headers)
    assert garment["cutout_url"] is None

    first = client.post(f"/garments/{garment['id']}/cutout", headers=headers)
    second = client.post(f"/garments/{garment['id']}/cutout", headers=headers)

    assert first.status_code == 200
    assert first.json()["cutout_url"].endswith(".png")
    assert second.json()["cutout_url"] == first.json()["cutout_url"]
    assert removebg.calls == 1


def test_no_se_puede_recortar_una_prenda_ajena(client, removebg):
    garment = upload_garment(client, auth_headers(client))
    other = auth_headers(client, "otra@example.com")

    response = client.post(f"/garments/{garment['id']}/cutout", headers=other)

    assert response.status_code == 404
    assert removebg.calls == 0
