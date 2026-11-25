from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from .models import Usuario, db
from .schemas import validar_email, validar_nombre, validar_password

api = Blueprint("api", __name__, url_prefix="/api")


def respuesta(data, codigo=200):
    return jsonify({"statusCode": codigo, "data": data}), codigo


def error(mensaje, codigo):
    return respuesta({"error": mensaje}, codigo)


def crear_token(usuario: Usuario) -> str:
    ahora = datetime.now(timezone.utc)
    carga = {"sub": str(usuario.id), "email": usuario.email, "iat": ahora,
             "exp": ahora + timedelta(minutes=current_app.config["JWT_EXP_MIN"])}
    return jwt.encode(carga, current_app.config["SECRET_KEY"], algorithm="HS256")


def token_requerido(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        cabecera = request.headers.get("Authorization", "")
        if not cabecera.startswith("Bearer "):
            return error("Falta el token de autenticacion", 401)
        try:
            carga = jwt.decode(cabecera[7:], current_app.config["SECRET_KEY"], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return error("El token ha expirado", 401)
        except jwt.InvalidTokenError:
            return error("Token invalido", 401)
        usuario = db.session.get(Usuario, int(carga["sub"]))
        if usuario is None:
            return error("El usuario del token ya no existe", 401)
        g.usuario = usuario
        return vista(*args, **kwargs)
    return envoltura


def _cuerpo():
    cuerpo = request.get_json(silent=True)
    return cuerpo if isinstance(cuerpo, dict) else {}


# ---------------------------------------------------------------- salud
@api.get("/health")
def health():
    return respuesta({"status": "ok"})


# ---------------------------------------------------------------- auth
@api.post("/auth/register")
def register():
    c = _cuerpo()
    for fallo in (validar_nombre(c.get("nombre")), validar_email(c.get("email")), validar_password(c.get("password"))):
        if fallo:
            return error(fallo, 400)
    email = c["email"].strip().lower()
    if Usuario.query.filter_by(email=email).first():
        return error("El correo ya esta registrado", 409)
    usuario = Usuario(nombre=c["nombre"].strip(), email=email)
    usuario.set_password(c["password"])
    db.session.add(usuario)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error("El correo ya esta registrado", 409)
    return respuesta(usuario.to_dict(), 201)


@api.post("/auth/login")
def login():
    c = _cuerpo()
    email = str(c.get("email", "")).strip().lower()
    usuario = Usuario.query.filter_by(email=email).first()
    if usuario is None or not usuario.check_password(str(c.get("password", ""))):
        current_app.logger.warning("login_fallido", extra={"email": email})
        return error("Credenciales incorrectas", 401)
    current_app.logger.info("login_exitoso", extra={"usuario_id": usuario.id})
    return respuesta({"token": crear_token(usuario), "usuario": usuario.to_dict()})


@api.get("/auth/me")
@token_requerido
def me():
    return respuesta(g.usuario.to_dict())


# ---------------------------------------------------------------- CRUD usuarios
@api.get("/usuarios")
@token_requerido
def listar():
    return respuesta([u.to_dict() for u in Usuario.query.order_by(Usuario.id).all()])


@api.get("/usuarios/<int:uid>")
@token_requerido
def obtener(uid):
    usuario = db.session.get(Usuario, uid)
    if usuario is None:
        return error("Usuario no encontrado", 404)
    return respuesta(usuario.to_dict())


@api.post("/usuarios")
@token_requerido
def crear():
    c = _cuerpo()
    for fallo in (validar_nombre(c.get("nombre")), validar_email(c.get("email")), validar_password(c.get("password"))):
        if fallo:
            return error(fallo, 400)
    email = c["email"].strip().lower()
    if Usuario.query.filter_by(email=email).first():
        return error("El correo ya esta registrado", 409)
    usuario = Usuario(nombre=c["nombre"].strip(), email=email)
    usuario.set_password(c["password"])
    db.session.add(usuario)
    db.session.commit()
    return respuesta(usuario.to_dict(), 201)


@api.put("/usuarios/<int:uid>")
@token_requerido
def actualizar(uid):
    usuario = db.session.get(Usuario, uid)
    if usuario is None:
        return error("Usuario no encontrado", 404)
    c = _cuerpo()
    if "nombre" in c and (fallo := validar_nombre(c["nombre"])):
        return error(fallo, 400)
    if "email" in c and (fallo := validar_email(c["email"])):
        return error(fallo, 400)
    if c.get("password") and (fallo := validar_password(c["password"])):
        return error(fallo, 400)
    if "email" in c:
        nuevo = c["email"].strip().lower()
        otro = Usuario.query.filter(Usuario.email == nuevo, Usuario.id != uid).first()
        if otro:
            return error("El correo ya esta registrado", 409)
        usuario.email = nuevo
    if "nombre" in c:
        usuario.nombre = c["nombre"].strip()
    if c.get("password"):
        usuario.set_password(c["password"])
    db.session.commit()
    return respuesta(usuario.to_dict())


@api.delete("/usuarios/<int:uid>")
@token_requerido
def eliminar(uid):
    usuario = db.session.get(Usuario, uid)
    if usuario is None:
        return error("Usuario no encontrado", 404)
    if usuario.id == g.usuario.id:
        return error("No puedes eliminar tu propia cuenta", 400)
    db.session.delete(usuario)
    db.session.commit()
    return respuesta({"eliminado": uid})
