import base64
import io

import httpx
import pytest
from PIL import Image

from app.core.config import settings
from app.services import background_removal, try_on_generation
from tests.test_cutouts import auth_headers, client, session_factory  # noqa: F401


def png(color: tuple[int, int, int, int], size=(8, 12)) -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", size, color).save(out, format="PNG")
    return out.getvalue()


CUTOUT = png((200, 120, 90, 255))


class FakeApis:
    """Simula remove.bg (recortes) y la API de FASHN (run + status)."""

    def __init__(self):
        self.runs = []
        self.outputs = []
        self.run_status = 200
        self.run_error = None
        self.failure = None

    def post(self, url, **kwargs):
        if "remove.bg" in url:
            return httpx.Response(200, content=CUTOUT)
        self.runs.append(kwargs["json"]["inputs"])
        if self.run_status != 200:
            return httpx.Response(self.run_status, json={"error": self.run_error})
        return httpx.Response(200, json={"id": f"pred-{len(self.runs)}", "error": None})

    def get(self, url, **kwargs):
        prediction_id = url.rsplit("/", 1)[1]
        if self.failure:
            return httpx.Response(200, json={"id": prediction_id, "status": "failed", "error": self.failure})
        # Cada paso devuelve una imagen distinta, para seguir el encadenado.
        output = "data:image/png;base64," + base64.b64encode(png((len(self.outputs) * 40, 0, 0, 255))).decode()
        self.outputs.append(output)
        return httpx.Response(200, json={"id": prediction_id, "status": "completed", "output": [output], "error": None})


@pytest.fixture
def apis(monkeypatch):
    fake = FakeApis()
    monkeypatch.setattr(background_removal.httpx, "post", fake.post)
    monkeypatch.setattr(try_on_generation.httpx, "get", fake.get)
    monkeypatch.setattr(try_on_generation.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(settings, "removebg_api_key", "clave-removebg")
    monkeypatch.setattr(settings, "fashn_api_key", "clave-fashn")
    monkeypatch.setattr(settings, "try_on_daily_limit", 10)
    return fake


def new_garment(client, headers, category="top", cutout=True):  # noqa: F811
    garment = client.post(
        "/garments",
        headers=headers,
        data={"category": category, "name": f"mi {category}"},
        files={"image": ("p.jpg", b"jpeg", "image/jpeg")},
    ).json()
    if cutout:
        client.post(f"/garments/{garment['id']}/cutout", headers=headers)
    return garment["id"]


def ready_user(client, email="ana@example.com"):  # noqa: F811
    headers = auth_headers(client, email)
    client.put("/me/body-photo", headers=headers, files={"image": ("yo.jpg", b"jpeg", "image/jpeg")})
    return headers


def test_encadena_las_prendas_en_orden_de_vestir(client, apis, tmp_path):  # noqa: F811
    headers = ready_user(client)
    jacket = new_garment(client, headers, "outerwear")
    top = new_garment(client, headers, "top")
    pants = new_garment(client, headers, "bottom")

    response = client.post("/looks", headers=headers, json={"garment_ids": [jacket, top, pants]})

    assert response.status_code == 201
    # Pantalón primero, luego la blusa y la chaqueta encima.
    assert response.json()["garment_ids"] == [pants, top, jacket]
    assert [run["category"] for run in apis.runs] == ["bottoms", "tops", "tops"]
    # La foto de cada paso es el resultado del anterior.
    assert apis.runs[0]["model_image"].startswith("data:image/jpeg;base64,")
    assert apis.runs[1]["model_image"] == apis.outputs[0]
    assert apis.runs[2]["model_image"] == apis.outputs[1]
    # Se guarda el resultado del último paso, en privado.
    final = base64.b64decode(apis.outputs[-1].split(",", 1)[1])
    assert final in [path.read_bytes() for path in tmp_path.iterdir()]


def test_pasos_intermedios_en_jpeg_y_el_final_en_png(client, apis, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "fashn_mode", "performance")
    headers = ready_user(client)
    top = new_garment(client, headers, "top")
    pants = new_garment(client, headers, "bottom")

    client.post("/looks", headers=headers, json={"garment_ids": [top, pants]})

    assert [run["output_format"] for run in apis.runs] == ["jpeg", "png"]
    assert {run["mode"] for run in apis.runs} == {"performance"}


def test_repetir_la_combinacion_no_gasta_creditos(client, apis):  # noqa: F811
    headers = ready_user(client)
    top = new_garment(client, headers, "top")
    pants = new_garment(client, headers, "bottom")
    first = client.post("/looks", headers=headers, json={"garment_ids": [top, pants]}).json()

    # Mismas prendas en otro orden: es el mismo look.
    again = client.post("/looks", headers=headers, json={"garment_ids": [pants, top]})

    assert again.status_code in (200, 201)
    assert again.json()["id"] == first["id"]
    assert len(apis.runs) == 2
    assert len(client.get("/looks", headers=headers).json()) == 1


def test_con_otra_foto_del_cuerpo_se_genera_de_nuevo(client, apis):  # noqa: F811
    headers = ready_user(client)
    top = new_garment(client, headers)
    first = client.post("/looks", headers=headers, json={"garment_ids": [top]}).json()

    client.put("/me/body-photo", headers=headers, files={"image": ("yo2.jpg", b"jpeg", "image/jpeg")})
    again = client.post("/looks", headers=headers, json={"garment_ids": [top]}).json()

    assert again["id"] != first["id"]
    assert len(apis.runs) == 2


def test_envia_imagenes_sin_transparencia(client, apis):  # noqa: F811
    headers = ready_user(client)
    top = new_garment(client, headers)

    client.post("/looks", headers=headers, json={"garment_ids": [top]})

    run = apis.runs[0]
    assert run["garment_photo_type"] == "flat-lay"
    for field in ("model_image", "garment_image"):
        image = Image.open(io.BytesIO(base64.b64decode(run[field].split(",", 1)[1])))
        assert image.mode == "RGB"


def test_calzado_y_accesorios_no_se_pueden_probar(client, apis):  # noqa: F811
    headers = ready_user(client)
    shoes = new_garment(client, headers, "shoes")

    response = client.post("/looks", headers=headers, json={"garment_ids": [shoes]})

    assert response.status_code == 400
    assert apis.runs == []


def test_sin_foto_del_cuerpo_no_gasta_creditos(client, apis):  # noqa: F811
    headers = auth_headers(client)
    top = new_garment(client, headers)

    assert client.post("/looks", headers=headers, json={"garment_ids": [top]}).status_code == 400
    assert apis.runs == []


def test_no_se_pueden_usar_prendas_ajenas(client, apis):  # noqa: F811
    foreign = new_garment(client, ready_user(client, "otra@example.com"))
    headers = ready_user(client)

    assert client.post("/looks", headers=headers, json={"garment_ids": [foreign]}).status_code == 404
    assert apis.runs == []


def test_prenda_sin_recorte_se_rechaza(client, apis):  # noqa: F811
    headers = ready_user(client)
    top = new_garment(client, headers, cutout=False)

    assert client.post("/looks", headers=headers, json={"garment_ids": [top]}).status_code == 400
    assert apis.runs == []


@pytest.mark.parametrize("garment_ids", [[], list(range(1, 8))])
def test_cantidad_de_prendas_invalida(client, apis, garment_ids):  # noqa: F811
    assert client.post("/looks", headers=ready_user(client), json={"garment_ids": garment_ids}).status_code == 422


def test_limite_diario_cuenta_prendas(client, apis, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "try_on_daily_limit", 3)
    headers = ready_user(client)
    top = new_garment(client, headers, "top")
    pants = new_garment(client, headers, "bottom")
    jacket = new_garment(client, headers, "outerwear")

    first = client.post("/looks", headers=headers, json={"garment_ids": [top, pants]})
    # Otra combinación: 2 prendas más superarían el límite de 3.
    second = client.post("/looks", headers=headers, json={"garment_ids": [top, jacket]})

    assert first.status_code == 201
    assert second.status_code == 429
    assert "prendas" in second.json()["detail"]
    assert len(apis.runs) == 2


def test_sin_creditos_da_un_mensaje_claro(client, apis):  # noqa: F811
    apis.run_status, apis.run_error = 429, "OutOfCredits"
    headers = ready_user(client)
    top = new_garment(client, headers)

    response = client.post("/looks", headers=headers, json={"garment_ids": [top]})

    assert response.status_code == 503
    assert "créditos" in response.json()["detail"]
    assert client.get("/looks", headers=headers).json() == []


def test_contenido_rechazado_no_guarda_nada(client, apis):  # noqa: F811
    apis.failure = {"name": "ContentModerationError", "message": "bloqueado"}
    headers = ready_user(client)
    top = new_garment(client, headers)

    response = client.post("/looks", headers=headers, json={"garment_ids": [top]})

    assert response.status_code == 422
    assert "revisión de contenido" in response.json()["detail"]
    assert client.get("/looks", headers=headers).json() == []


def test_sin_clave_responde_con_un_mensaje_claro(client, apis, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "fashn_api_key", "")
    headers = ready_user(client)
    top = new_garment(client, headers)

    response = client.post("/looks", headers=headers, json={"garment_ids": [top]})

    assert response.status_code == 503
    assert apis.runs == []


def test_listar_y_borrar_solo_los_propios(client, apis):  # noqa: F811
    headers = ready_user(client)
    top = new_garment(client, headers)
    look_id = client.post("/looks", headers=headers, json={"garment_ids": [top]}).json()["id"]
    other = auth_headers(client, "otra@example.com")

    assert client.get("/looks", headers=other).json() == []
    assert client.delete(f"/looks/{look_id}", headers=other).status_code == 404
    assert client.delete(f"/looks/{look_id}", headers=headers).status_code == 204
    assert client.get("/looks", headers=headers).json() == []
