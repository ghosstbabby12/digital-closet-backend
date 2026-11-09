import httpx
import pytest

from app.core.config import settings
from app.services import weather_service
from tests.test_cutouts import auth_headers, client, session_factory  # noqa: F401

PLACES = [
    {"name": "Bogota", "local_names": {"es": "Bogotá, Distrito Capital"}, "lat": 4.71, "lon": -74.07, "country": "CO"},
    {"name": "Bogotá", "local_names": {"es": "Bogotá"}, "lat": 4.66, "lon": -74.1, "country": "CO"},
    {"name": "Bogota", "lat": 40.88, "lon": -74.03, "country": "US", "state": "New Jersey"},
]


@pytest.fixture
def geocoding(monkeypatch):
    calls = []

    async def fake_get(self, url, params=None):
        calls.append((url, params))
        return httpx.Response(200, json=PLACES, request=httpx.Request("GET", url))

    monkeypatch.setattr(weather_service.httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(settings, "openweather_api_key", "clave-de-prueba")
    return calls


def test_busca_ciudades_y_junta_duplicados(client, geocoding):  # noqa: F811
    response = client.get("/weather/cities", params={"q": "Bogota"}, headers=auth_headers(client))

    assert response.status_code == 200
    assert response.json() == [
        {"name": "Bogotá", "state": None, "country": "CO", "lat": 4.71, "lon": -74.07},
        {"name": "Bogota", "state": "New Jersey", "country": "US", "lat": 40.88, "lon": -74.03},
    ]
    url, params = geocoding[0]
    assert url == weather_service.GEOCODING_URL
    assert params["q"] == "Bogota" and params["limit"] == 5


def test_quita_espacios_de_la_busqueda(client, geocoding):  # noqa: F811
    client.get("/weather/cities", params={"q": "  Cali "}, headers=auth_headers(client))

    assert geocoding[0][1]["q"] == "Cali"


@pytest.mark.parametrize("query", ["", "a", "x" * 101])
def test_rechaza_busquedas_invalidas(client, geocoding, query):  # noqa: F811
    response = client.get("/weather/cities", params={"q": query}, headers=auth_headers(client))

    assert response.status_code == 422
    assert geocoding == []


def test_requiere_sesion(client, geocoding):  # noqa: F811
    assert client.get("/weather/cities", params={"q": "Cali"}).status_code in (401, 403)


def test_error_del_servicio_da_un_mensaje_claro(client, monkeypatch):  # noqa: F811
    async def failing_get(self, url, params=None):
        return httpx.Response(500, request=httpx.Request("GET", url))

    monkeypatch.setattr(weather_service.httpx.AsyncClient, "get", failing_get)
    monkeypatch.setattr(settings, "openweather_api_key", "clave-de-prueba")

    response = client.get("/weather/cities", params={"q": "Cali"}, headers=auth_headers(client))

    assert response.status_code == 502
    assert response.json()["detail"] == "No se pudo buscar la ciudad."
