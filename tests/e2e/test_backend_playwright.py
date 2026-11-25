"""Pruebas de backend (API REST) con Playwright APIRequestContext, contra el servidor en ejecucion."""
import pytest


def test_health(api):
    r = api.get("/api/health")
    assert r.status == 200
    assert r.json() == {"statusCode": 200, "data": {"status": "ok"}}


def test_registro_y_login(api, datos):
    r = api.post("/api/auth/register", data=datos)
    assert r.status == 201
    r = api.post("/api/auth/login", data={"email": datos["email"], "password": datos["password"]})
    assert r.status == 200 and r.json()["data"]["token"]


def test_registro_duplicado(api, datos):
    api.post("/api/auth/register", data=datos)
    assert api.post("/api/auth/register", data=datos).status == 409


@pytest.mark.parametrize("campo,valor", [("nombre", ""), ("email", "malo"), ("password", "123")])
def test_registro_invalido(api, datos, campo, valor):
    assert api.post("/api/auth/register", data={**datos, campo: valor}).status == 400


def test_login_incorrecto(api, sesion):
    assert api.post("/api/auth/login", data={"email": sesion["email"], "password": "mala-12345"}).status == 401


def test_listar_requiere_token(api):
    assert api.get("/api/usuarios").status == 401


def test_listar_con_token(api, sesion):
    r = api.get("/api/usuarios", headers=sesion["headers"])
    assert r.status == 200
    assert any(u["email"] == sesion["email"] for u in r.json()["data"])


def test_ciclo_crud_completo(api, sesion, datos):
    h = sesion["headers"]
    nuevo = {"nombre": "Ciclo", "email": "ciclo." + datos["email"], "password": "Segura12345"}
    creado = api.post("/api/usuarios", data=nuevo, headers=h)
    assert creado.status == 201
    uid = creado.json()["data"]["id"]
    assert api.get(f"/api/usuarios/{uid}", headers=h).json()["data"]["nombre"] == "Ciclo"
    assert api.put(f"/api/usuarios/{uid}", data={"nombre": "Ciclo 2"}, headers=h).json()["data"]["nombre"] == "Ciclo 2"
    assert api.delete(f"/api/usuarios/{uid}", headers=h).status == 200
    assert api.get(f"/api/usuarios/{uid}", headers=h).status == 404


def test_endpoint_inexistente_404(api):
    r = api.get("/api/no-existe")
    assert r.status == 404 and r.json()["statusCode"] == 404


def test_tiempo_de_respuesta_del_health_es_razonable(api):
    import time
    inicio = time.time()
    api.get("/api/health")
    assert time.time() - inicio < 2
