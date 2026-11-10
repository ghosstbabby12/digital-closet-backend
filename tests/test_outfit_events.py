import pytest

from app.api.routes import outfits as outfits_route
from app.schemas.weather import WeatherOut
from tests.test_cutouts import auth_headers, client, session_factory  # noqa: F401
from tests.test_garment_edit import create


@pytest.fixture(autouse=True)
def weather(monkeypatch):
    async def fake_weather(lat, lon):
        return WeatherOut(temp_c=18, feels_like_c=18, condition="nublado", condition_main="Clouds", city="Bogotá")

    monkeypatch.setattr(outfits_route, "get_current_weather", fake_weather)


def closet(client, headers):  # noqa: F811
    create(client, headers)
    client.post(
        "/garments",
        headers=headers,
        data={"category": "bottom", "color": "negro", "warmth": "medium", "name": "Pantalón"},
        files={"image": ("p.jpg", b"jpeg", "image/jpeg")},
    )


def generate(client, headers, **extra):  # noqa: F811
    return client.post("/outfits/generate", headers=headers, json={"occasion": "fiesta", "lat": 4.6, "lon": -74.1, **extra})


def test_outfit_para_un_evento_guarda_nombre_y_fecha(client):  # noqa: F811
    headers = auth_headers(client)
    closet(client, headers)

    response = generate(client, headers, event_title="  Boda de Ana ", event_date="2026-12-05")

    assert response.status_code == 201
    outfit = response.json()
    assert outfit["event_title"] == "Boda de Ana"
    assert outfit["event_date"] == "2026-12-05"
    assert outfit["garments"]
    assert client.get("/outfits", headers=headers).json()[0]["event_date"] == "2026-12-05"


def test_outfit_del_dia_no_tiene_evento(client):  # noqa: F811
    headers = auth_headers(client)
    closet(client, headers)

    outfit = generate(client, headers).json()

    assert outfit["event_title"] is None
    assert outfit["event_date"] is None


@pytest.mark.parametrize(
    "extra",
    [{"event_title": "Boda"}, {"event_date": "2026-12-05"}, {"event_title": "   ", "event_date": "2026-12-05"}],
)
def test_el_evento_necesita_nombre_y_fecha(client, extra):  # noqa: F811
    headers = auth_headers(client)
    closet(client, headers)

    assert generate(client, headers, **extra).status_code == 422
    assert client.get("/outfits", headers=headers).json() == []


def test_borrar_un_outfit_solo_el_propio(client):  # noqa: F811
    headers = auth_headers(client)
    closet(client, headers)
    outfit = generate(client, headers, event_title="Boda", event_date="2026-12-05").json()
    other = auth_headers(client, "otra@example.com")

    assert client.delete(f"/outfits/{outfit['id']}", headers=other).status_code == 404
    assert client.delete(f"/outfits/{outfit['id']}", headers=headers).status_code == 204
    assert client.get("/outfits", headers=headers).json() == []
    # Las prendas siguen en el clóset.
    assert len(client.get("/garments", headers=headers).json()) == 2
