from tests.test_cutouts import auth_headers, client, session_factory  # noqa: F401
from tests.test_garment_edit import create


def test_perfil_nuevo_sin_datos(client):  # noqa: F811
    headers = auth_headers(client)

    response = client.get("/me", headers=headers)

    assert response.status_code == 200
    profile = response.json()
    assert profile["email"] == "ana@example.com"
    assert profile["created_at"]
    assert profile["garment_count"] == 0
    assert profile["outfit_count"] == 0
    assert profile["look_count"] == 0
    assert profile["has_body_photo"] is False


def test_perfil_cuenta_solo_las_prendas_propias(client):  # noqa: F811
    headers = auth_headers(client)
    other = auth_headers(client, "otra@example.com")
    create(client, headers)
    create(client, headers)
    create(client, other)

    assert client.get("/me", headers=headers).json()["garment_count"] == 2
    assert client.get("/me", headers=other).json()["garment_count"] == 1


def test_perfil_requiere_sesion(client):  # noqa: F811
    assert client.get("/me").status_code in (401, 403)
