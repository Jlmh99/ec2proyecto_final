"""
Configuracion de las pruebas E2E (Playwright).

- Por defecto levanta la aplicacion en un puerto libre con una base SQLite temporal.
- Si existe la variable E2E_BASE_URL (por ejemplo la URL de la EC2) prueba contra ese servidor.
"""
import base64
import os
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def base_url(tmp_path_factory):
    externo = os.getenv("E2E_BASE_URL")
    if externo:
        yield externo.rstrip("/")
        return
    puerto = _puerto_libre()
    base_datos = tmp_path_factory.mktemp("e2e") / "e2e.db"
    entorno = {**os.environ, "PORT": str(puerto), "DATABASE_URL": f"sqlite:///{base_datos}",
               "SECRET_KEY": "clave-e2e-con-al-menos-32-caracteres-ok"}
    proceso = subprocess.Popen([sys.executable, "run.py"], cwd=RAIZ, env=entorno,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{puerto}"
    limite = time.time() + 30
    while time.time() < limite:
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=1):
                break
        except Exception:
            time.sleep(0.3)
    else:
        proceso.kill()
        raise RuntimeError("La aplicacion no arranco para las pruebas E2E")
    yield url
    proceso.terminate()
    proceso.wait(timeout=10)


@pytest.fixture
def datos():
    """Datos unicos por prueba para que las pruebas no dependan unas de otras."""
    sufijo = uuid.uuid4().hex[:8]
    return {"nombre": f"Usuario {sufijo}", "email": f"u{sufijo}@example.com", "password": "Segura12345"}


@pytest.fixture
def api(playwright, base_url):
    contexto = playwright.request.new_context(base_url=base_url)
    yield contexto
    contexto.dispose()


@pytest.fixture
def sesion(api, datos):
    """Usuario registrado, con token, para pruebas que necesitan sesion."""
    api.post("/api/auth/register", data=datos)
    r = api.post("/api/auth/login", data={"email": datos["email"], "password": datos["password"]})
    return {**datos, "token": r.json()["data"]["token"], "headers": {"Authorization": "Bearer " + r.json()["data"]["token"]}}


@pytest.fixture
def pagina_con_sesion(page, base_url, sesion):
    page.goto(base_url + "/login")
    page.fill("#email", sesion["email"])
    page.fill("#password", sesion["password"])
    page.click("#btn-login")
    page.wait_for_url("**/usuarios")
    return page


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Adjunta una captura ligera (JPEG) de cada prueba al reporte HTML."""
    resultado = yield
    reporte = resultado.get_result()
    if reporte.when != "call":
        return
    pagina = item.funcargs.get("page")
    if pagina is None or pagina.is_closed():
        return
    try:
        imagen = base64.b64encode(pagina.screenshot(type="jpeg", quality=45)).decode()
        extra = getattr(reporte, "extras", [])
        from pytest_html import extras
        extra.append(extras.image(imagen, mime_type="image/jpeg", extension="jpg"))
        reporte.extras = extra
    except Exception:
        pass
