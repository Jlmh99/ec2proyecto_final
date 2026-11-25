# Proyecto Parcial 2 – CI/CD, pruebas y observabilidad

Aplicación web con **Login, Register y CRUD de usuarios** (Flask + SQLite + JWT) y pruebas automatizadas.

## Ejecutar en local
```bash
python -m venv .venv && source .venv/bin/activate      # en Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
playwright install chromium
python run.py                                          # http://localhost:5000
```

## Pruebas
```bash
pytest tests/api --cov=app --cov-fail-under=70         # backend (pytest + cliente de Flask)
pytest tests/e2e                                       # frontend y backend (Playwright); levanta la app sola
E2E_BASE_URL=http://IP_EC2 pytest tests/e2e            # contra un servidor ya desplegado
```

## API
| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| GET | /api/health | No | Estado del servicio |
| POST | /api/auth/register | No | Crea una cuenta |
| POST | /api/auth/login | No | Devuelve un token JWT |
| GET | /api/auth/me | Sí | Usuario de la sesión |
| GET/POST | /api/usuarios | Sí | Listar / crear |
| GET/PUT/DELETE | /api/usuarios/<id> | Sí | Consultar / actualizar / eliminar |

Respuestas con el formato `{"statusCode": N, "data": ...}`. Las rutas protegidas piden `Authorization: Bearer <token>`.

## Variables de entorno
`SECRET_KEY` (obligatoria en producción), `DATABASE_URL` (por defecto SQLite en `instance/`), `JWT_EXP_MIN`, `PORT`.
