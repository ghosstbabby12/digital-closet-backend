import pytest

from tests.test_cutouts import auth_headers, client, session_factory  # noqa: F401


def login(client, email, password="secret123"):  # noqa: F811
    return client.post("/auth/login", json={"email": email, "password": password})


def test_actualiza_nombre_y_telefono_y_se_guardan(client):  # noqa: F811
    headers = auth_headers(client)

    response = client.patch("/me", headers=headers, json={"name": "  Ana   María ", "phone": "+57 300 123 4567"})

    assert response.status_code == 200
    assert response.json()["name"] == "Ana María"
    profile = client.get("/me", headers=headers).json()
    assert profile["name"] == "Ana María"
    assert profile["phone"] == "+57 300 123 4567"
    assert profile["email"] == "ana@example.com"


def test_solo_cambia_lo_enviado_y_vacio_borra_el_telefono(client):  # noqa: F811
    headers = auth_headers(client)
    client.patch("/me", headers=headers, json={"name": "Ana", "phone": "3001234567"})

    client.patch("/me", headers=headers, json={"phone": "  "})

    profile = client.get("/me", headers=headers).json()
    assert profile["name"] == "Ana"
    assert profile["phone"] is None


@pytest.mark.parametrize("payload", [{"phone": "llámame"}, {"phone": "12"}, {"name": "x" * 81}, {"email": "no-es-correo"}])
def test_rechaza_datos_invalidos(client, payload):  # noqa: F811
    headers = auth_headers(client)

    assert client.patch("/me", headers=headers, json=payload).status_code == 422


def test_cambiar_el_correo_pide_la_contrasena(client):  # noqa: F811
    headers = auth_headers(client)

    sin = client.patch("/me", headers=headers, json={"email": "nueva@example.com"})
    mala = client.patch("/me", headers=headers, json={"email": "nueva@example.com", "current_password": "otra"})

    assert sin.status_code == 400
    assert mala.status_code == 400
    assert client.get("/me", headers=headers).json()["email"] == "ana@example.com"


def test_cambiar_el_correo_devuelve_un_token_que_sirve(client):  # noqa: F811
    headers = auth_headers(client)

    response = client.patch("/me", headers=headers, json={"email": "nueva@example.com", "current_password": "secret123"})

    assert response.status_code == 200
    new_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/me", headers=new_headers).json()["email"] == "nueva@example.com"
    assert login(client, "nueva@example.com").status_code == 200
    assert login(client, "ana@example.com").status_code == 401


def test_no_se_puede_usar_un_correo_de_otra_cuenta(client):  # noqa: F811
    headers = auth_headers(client)
    auth_headers(client, "otra@example.com")

    response = client.patch("/me", headers=headers, json={"email": "otra@example.com", "current_password": "secret123"})

    assert response.status_code == 400


def test_cambiar_la_contrasena(client):  # noqa: F811
    headers = auth_headers(client)

    mala = client.put("/me/password", headers=headers, json={"current_password": "otra", "new_password": "nueva1234"})
    corta = client.put("/me/password", headers=headers, json={"current_password": "secret123", "new_password": "123"})
    ok = client.put("/me/password", headers=headers, json={"current_password": "secret123", "new_password": "nueva1234"})

    assert mala.status_code == 400
    assert corta.status_code == 422
    assert ok.status_code == 204
    assert login(client, "ana@example.com", "nueva1234").status_code == 200
    assert login(client, "ana@example.com").status_code == 401


def test_subir_cambiar_y_borrar_la_foto_de_perfil(client, tmp_path):  # noqa: F811
    headers = auth_headers(client)

    first = client.put("/me/avatar", headers=headers, files={"image": ("a.jpg", b"jpeg1", "image/jpeg")})
    second = client.put("/me/avatar", headers=headers, files={"image": ("b.png", b"png2", "image/png")})

    assert first.status_code == 200
    assert second.json()["avatar_url"].endswith(".png")
    assert client.get("/me", headers=headers).json()["avatar_url"] == second.json()["avatar_url"]
    # La foto anterior se borra al reemplazarla.
    assert [p.suffix for p in tmp_path.iterdir()] == [".png"]

    assert client.delete("/me/avatar", headers=headers).status_code == 204
    assert client.get("/me", headers=headers).json()["avatar_url"] is None
    assert list(tmp_path.iterdir()) == []


def test_la_foto_de_perfil_debe_ser_una_imagen(client):  # noqa: F811
    headers = auth_headers(client)

    response = client.put("/me/avatar", headers=headers, files={"image": ("a.gif", b"gif", "image/gif")})

    assert response.status_code == 400
