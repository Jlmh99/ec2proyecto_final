"""Pruebas de backend (API REST) con pytest y el cliente de pruebas de Flask."""
import time

import jwt
import pytest


# ------------------------------------------------------------------ salud y errores
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json() == {"statusCode": 200, "data": {"status": "ok"}}


def test_ruta_inexistente_devuelve_404_con_formato(client):
    r = client.get("/api/no-existe")
    assert r.status_code == 404
    assert r.get_json()["statusCode"] == 404


def test_metodo_no_permitido_devuelve_405(client):
    r = client.put("/api/health")
    assert r.status_code == 405
    assert r.get_json()["statusCode"] == 405


# ------------------------------------------------------------------ register
def test_register_crea_usuario(client, datos_usuario):
    r = client.post("/api/auth/register", json=datos_usuario)
    assert r.status_code == 201
    data = r.get_json()["data"]
    assert data["email"] == "ana@example.com" and data["id"] == 1
    assert "password" not in data and "password_hash" not in data


def test_register_normaliza_email_a_minusculas(client):
    r = client.post("/api/auth/register", json={"nombre": "X", "email": "MAYUS@Example.COM", "password": "Segura123"})
    assert r.get_json()["data"]["email"] == "mayus@example.com"


def test_register_correo_duplicado_409(client, datos_usuario):
    client.post("/api/auth/register", json=datos_usuario)
    r = client.post("/api/auth/register", json=datos_usuario)
    assert r.status_code == 409


@pytest.mark.parametrize("cambio", [
    {"nombre": ""}, {"nombre": "   "}, {"nombre": "x" * 81}, {"email": "sin-arroba"}, {"email": "a@b"},
    {"email": ""}, {"password": "corta"}, {"password": ""}, {"password": "x" * 129},
])
def test_register_valida_campos(client, datos_usuario, cambio):
    r = client.post("/api/auth/register", json={**datos_usuario, **cambio})
    assert r.status_code == 400
    assert "error" in r.get_json()["data"]


def test_register_sin_cuerpo_json_400(client):
    assert client.post("/api/auth/register", data="no es json").status_code == 400


def test_password_se_guarda_cifrada(app, client, datos_usuario):
    from app.models import Usuario
    client.post("/api/auth/register", json=datos_usuario)
    with app.app_context():
        u = Usuario.query.first()
        assert u.password_hash != datos_usuario["password"]
        assert u.check_password(datos_usuario["password"])


# ------------------------------------------------------------------ login
def test_login_correcto_devuelve_token(client, datos_usuario):
    client.post("/api/auth/register", json=datos_usuario)
    r = client.post("/api/auth/login", json={"email": datos_usuario["email"], "password": datos_usuario["password"]})
    assert r.status_code == 200
    assert r.get_json()["data"]["token"].count(".") == 2


def test_login_password_incorrecta_401(client, datos_usuario):
    client.post("/api/auth/register", json=datos_usuario)
    r = client.post("/api/auth/login", json={"email": datos_usuario["email"], "password": "otra-cosa"})
    assert r.status_code == 401


def test_login_usuario_inexistente_401(client):
    assert client.post("/api/auth/login", json={"email": "nadie@x.com", "password": "Segura123"}).status_code == 401


def test_login_sin_datos_401(client):
    assert client.post("/api/auth/login", json={}).status_code == 401


def test_login_no_distingue_correo_de_password(client, datos_usuario):
    client.post("/api/auth/register", json=datos_usuario)
    a = client.post("/api/auth/login", json={"email": datos_usuario["email"], "password": "mala"}).get_json()
    b = client.post("/api/auth/login", json={"email": "otro@x.com", "password": "mala"}).get_json()
    assert a == b


# ------------------------------------------------------------------ protección
@pytest.mark.parametrize("metodo,ruta", [("get", "/api/usuarios"), ("get", "/api/usuarios/1"), ("post", "/api/usuarios"),
                                         ("put", "/api/usuarios/1"), ("delete", "/api/usuarios/1"), ("get", "/api/auth/me")])
def test_rutas_protegidas_sin_token_401(client, metodo, ruta):
    assert getattr(client, metodo)(ruta).status_code == 401


def test_token_invalido_401(client):
    r = client.get("/api/usuarios", headers={"Authorization": "Bearer abc.def.ghi"})
    assert r.status_code == 401


def test_token_expirado_401(app, client, datos_usuario):
    client.post("/api/auth/register", json=datos_usuario)
    vencido = jwt.encode({"sub": "1", "exp": int(time.time()) - 10}, app.config["SECRET_KEY"], algorithm="HS256")
    assert client.get("/api/usuarios", headers={"Authorization": f"Bearer {vencido}"}).status_code == 401


def test_token_firmado_con_otra_clave_401(client, datos_usuario):
    client.post("/api/auth/register", json=datos_usuario)
    falso = jwt.encode({"sub": "1", "exp": int(time.time()) + 60}, "clave-falsa-de-prueba-0123456789", algorithm="HS256")
    assert client.get("/api/usuarios", headers={"Authorization": f"Bearer {falso}"}).status_code == 401


def test_me_devuelve_usuario_actual(client, auth):
    r = client.get("/api/auth/me", headers=auth)
    assert r.status_code == 200 and r.get_json()["data"]["email"] == "ana@example.com"


# ------------------------------------------------------------------ CRUD
def test_listar_usuarios(client, auth):
    r = client.get("/api/usuarios", headers=auth)
    assert r.status_code == 200 and len(r.get_json()["data"]) == 1


def test_crear_usuario(client, auth):
    r = client.post("/api/usuarios", headers=auth, json={"nombre": "Luis", "email": "luis@example.com", "password": "Segura123"})
    assert r.status_code == 201
    assert client.get("/api/usuarios", headers=auth).get_json()["data"][-1]["nombre"] == "Luis"


def test_crear_usuario_duplicado_409(client, auth, datos_usuario):
    r = client.post("/api/usuarios", headers=auth, json=datos_usuario)
    assert r.status_code == 409


def test_crear_usuario_invalido_400(client, auth):
    assert client.post("/api/usuarios", headers=auth, json={"nombre": "", "email": "x", "password": "1"}).status_code == 400


def test_obtener_usuario(client, auth):
    r = client.get("/api/usuarios/1", headers=auth)
    assert r.status_code == 200 and r.get_json()["data"]["id"] == 1


def test_obtener_usuario_inexistente_404(client, auth):
    assert client.get("/api/usuarios/999", headers=auth).status_code == 404


def test_actualizar_nombre(client, auth):
    r = client.put("/api/usuarios/1", headers=auth, json={"nombre": "Ana Nueva"})
    assert r.status_code == 200 and r.get_json()["data"]["nombre"] == "Ana Nueva"


def test_actualizar_email(client, auth):
    r = client.put("/api/usuarios/1", headers=auth, json={"email": "nuevo@example.com"})
    assert r.get_json()["data"]["email"] == "nuevo@example.com"


def test_actualizar_password_permite_nuevo_login(client, auth):
    client.put("/api/usuarios/1", headers=auth, json={"password": "NuevaClave456"})
    r = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "NuevaClave456"})
    assert r.status_code == 200


def test_actualizar_con_email_de_otro_409(client, auth):
    client.post("/api/usuarios", headers=auth, json={"nombre": "Luis", "email": "luis@example.com", "password": "Segura123"})
    assert client.put("/api/usuarios/1", headers=auth, json={"email": "luis@example.com"}).status_code == 409


def test_actualizar_invalido_400(client, auth):
    assert client.put("/api/usuarios/1", headers=auth, json={"email": "malo"}).status_code == 400


def test_actualizar_inexistente_404(client, auth):
    assert client.put("/api/usuarios/999", headers=auth, json={"nombre": "X"}).status_code == 404


def test_eliminar_usuario(client, auth):
    client.post("/api/usuarios", headers=auth, json={"nombre": "Luis", "email": "luis@example.com", "password": "Segura123"})
    assert client.delete("/api/usuarios/2", headers=auth).status_code == 200
    assert client.get("/api/usuarios/2", headers=auth).status_code == 404


def test_no_puede_eliminar_su_propia_cuenta(client, auth):
    assert client.delete("/api/usuarios/1", headers=auth).status_code == 400


def test_eliminar_inexistente_404(client, auth):
    assert client.delete("/api/usuarios/999", headers=auth).status_code == 404


def test_token_de_usuario_eliminado_deja_de_servir(client, auth):
    r = client.post("/api/usuarios", headers=auth, json={"nombre": "Luis", "email": "luis@example.com", "password": "Segura123"})
    client.post("/api/auth/login", json={"email": "luis@example.com", "password": "Segura123"})
    tok = client.post("/api/auth/login", json={"email": "luis@example.com", "password": "Segura123"}).get_json()["data"]["token"]
    client.delete(f"/api/usuarios/{r.get_json()['data']['id']}", headers=auth)
    assert client.get("/api/usuarios", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


# ------------------------------------------------------------------ páginas web
@pytest.mark.parametrize("ruta", ["/login", "/register", "/usuarios"])
def test_paginas_web_responden(client, ruta):
    r = client.get(ruta)
    assert r.status_code == 200
    assert b"<form" in r.data


def test_raiz_redirige_a_login(client):
    r = client.get("/")
    assert r.status_code == 302 and r.headers["Location"].endswith("/login")
