import logging
import os

from flask import Flask, jsonify

from .models import db


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-cambiar-en-produccion"),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///" + os.path.join(app.instance_path, "app.db")),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_EXP_MIN=int(os.getenv("JWT_EXP_MIN", "60")),
    )
    if test_config:
        app.config.update(test_config)

    logging.basicConfig(level=logging.INFO)
    db.init_app(app)

    from .api import api
    from .web import web
    app.register_blueprint(api)
    app.register_blueprint(web)

    @app.errorhandler(404)
    def no_encontrado(_e):
        return jsonify({"statusCode": 404, "data": {"error": "Recurso no encontrado"}}), 404

    @app.errorhandler(405)
    def metodo_no_permitido(_e):
        return jsonify({"statusCode": 405, "data": {"error": "Metodo no permitido"}}), 405

    @app.errorhandler(500)
    def error_interno(e):
        app.logger.exception("error_interno")
        return jsonify({"statusCode": 500, "data": {"error": "Error interno del servidor"}}), 500

    with app.app_context():
        db.create_all()
    return app
