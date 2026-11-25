"""Validaciones de entrada. Cada funcion devuelve un mensaje de error o None."""
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validar_nombre(nombre) -> str | None:
    if not isinstance(nombre, str) or not nombre.strip():
        return "El nombre es obligatorio"
    if len(nombre.strip()) > 80:
        return "El nombre no puede superar 80 caracteres"
    return None


def validar_email(email) -> str | None:
    if not isinstance(email, str) or not EMAIL_RE.match(email.strip()):
        return "El correo no es valido"
    if len(email.strip()) > 120:
        return "El correo no puede superar 120 caracteres"
    return None


def validar_password(password) -> str | None:
    if not isinstance(password, str) or len(password) < 8:
        return "La contrasena debe tener al menos 8 caracteres"
    if len(password) > 128:
        return "La contrasena no puede superar 128 caracteres"
    return None
