import pytest

from app import create_app
from app.models import db


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
                      "SECRET_KEY": "clave-de-pruebas-con-al-menos-32-caracteres", "JWT_EXP_MIN": 5})
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def datos_usuario():
    return {"nombre": "Ana Prueba", "email": "ana@example.com", "password": "Segura123"}


@pytest.fixture
def token(client, datos_usuario):
    client.post("/api/auth/register", json=datos_usuario)
    r = client.post("/api/auth/login", json={"email": datos_usuario["email"], "password": datos_usuario["password"]})
    return r.get_json()["data"]["token"]


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}
