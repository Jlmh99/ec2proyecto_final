"""
Observabilidad con OpenTelemetry (OTLP/HTTP) hacia OpenObserve.

Se activa solo si existe la variable OPENOBSERVE_URL; sin ella la aplicacion funciona igual
(por ejemplo, durante las pruebas). Emite:
  - Trazas:   cada peticion HTTP (Flask) y cada consulta a la base de datos (SQLAlchemy).
  - Metricas: latencia, volumen y errores por endpoint + recursos del servidor (CPU, RAM, swap, disco, red).
  - Logs:     eventos estructurados (JSON en consola y OTLP), con trace_id para correlacionarlos.

Variables: OPENOBSERVE_URL (p. ej. http://localhost:5080), OPENOBSERVE_ORG (default), OPENOBSERVE_USER,
OPENOBSERVE_PASSWORD, SERVICE_NAME, DEPLOY_ENV, METRICS_INTERVAL_MS.
"""
import base64
import json
import logging
import os
import socket
import time

import psutil
from flask import g, request
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.metrics import CallbackOptions, Observation
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

log = logging.getLogger("app.observabilidad")
_aviso_temperatura = {"emitido": False}

_CAMPOS_ESTANDAR = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime", "taskName"}


class FormatoJSON(logging.Formatter):
    """Logs estructurados en una linea JSON (consola de Docker)."""

    def format(self, record: logging.LogRecord) -> str:
        datos = {"timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"), "level": record.levelname,
                 "logger": record.name, "message": record.getMessage()}
        datos.update({k: v for k, v in record.__dict__.items() if k not in _CAMPOS_ESTANDAR})
        if record.exc_info:
            datos["exception"] = self.formatException(record.exc_info)
        return json.dumps(datos, ensure_ascii=False, default=str)


def _cabeceras() -> dict:
    usuario, clave = os.getenv("OPENOBSERVE_USER", ""), os.getenv("OPENOBSERVE_PASSWORD", "")
    token = base64.b64encode(f"{usuario}:{clave}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def configurar_observabilidad(app) -> bool:
    """Devuelve True si la telemetria quedo activa."""
    base = os.getenv("OPENOBSERVE_URL", "").rstrip("/")
    if not base:
        return False

    org = os.getenv("OPENOBSERVE_ORG", "default")
    destino = f"{base}/api/{org}"
    cabeceras = _cabeceras()
    recurso = Resource.create({"service.name": os.getenv("SERVICE_NAME", "gestion-usuarios"),
                               "service.version": os.getenv("APP_VERSION", "1.0.0"),
                               "deployment.environment": os.getenv("DEPLOY_ENV", "produccion"),
                               "host.name": socket.gethostname()})

    # ---- trazas
    proveedor_trazas = TracerProvider(resource=recurso)
    proveedor_trazas.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{destino}/v1/traces", headers=cabeceras)))
    trace.set_tracer_provider(proveedor_trazas)

    # ---- metricas
    intervalo = int(os.getenv("METRICS_INTERVAL_MS", "15000"))
    lector = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=f"{destino}/v1/metrics", headers=cabeceras),
                                           export_interval_millis=intervalo)
    metrics.set_meter_provider(MeterProvider(resource=recurso, metric_readers=[lector]))

    # ---- logs
    proveedor_logs = LoggerProvider(resource=recurso)
    proveedor_logs.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{destino}/v1/logs", headers=cabeceras)))
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.addHandler(LoggingHandler(level=logging.INFO, logger_provider=proveedor_logs))
    consola = logging.StreamHandler()
    consola.setFormatter(FormatoJSON())
    raiz.handlers = [h for h in raiz.handlers if not (isinstance(h, logging.StreamHandler) and type(h) is logging.StreamHandler)]
    raiz.addHandler(consola)

    # ---- instrumentacion automatica
    FlaskInstrumentor().instrument_app(app)
    from .models import db
    with app.app_context():
        SQLAlchemyInstrumentor().instrument(engine=db.engine)

    _instrumentos_de_endpoint(app)
    _metricas_del_servidor()
    log.info("observabilidad_activa", extra={"destino": destino, "intervalo_metricas_ms": intervalo})
    return True


def _instrumentos_de_endpoint(app) -> None:
    medidor = metrics.get_meter("app.http")
    peticiones = medidor.create_counter("app_requests_total", unit="1", description="Peticiones HTTP por endpoint")
    errores = medidor.create_counter("app_errors_total", unit="1", description="Respuestas HTTP con codigo >= 400")
    latencia = medidor.create_histogram("app_request_duration_ms", unit="ms", description="Latencia por endpoint")
    logger_http = logging.getLogger("app.http")

    @app.before_request
    def _inicio():
        g._inicio = time.perf_counter()

    @app.after_request
    def _fin(respuesta):
        duracion = (time.perf_counter() - getattr(g, "_inicio", time.perf_counter())) * 1000
        endpoint = request.url_rule.rule if request.url_rule else "no_encontrado"
        atributos = {"endpoint": endpoint, "method": request.method, "status_code": respuesta.status_code}
        peticiones.add(1, atributos)
        latencia.record(duracion, atributos)
        if respuesta.status_code >= 400:
            errores.add(1, atributos)
        contexto = trace.get_current_span().get_span_context()
        nivel = logging.ERROR if respuesta.status_code >= 500 else logging.INFO
        logger_http.log(nivel, "peticion_http", extra={
            "endpoint": endpoint, "method": request.method, "status_code": respuesta.status_code,
            "duration_ms": round(duracion, 2), "trace_id": format(contexto.trace_id, "032x") if contexto.is_valid else None})
        return respuesta


def _metricas_del_servidor() -> None:
    """Recursos de la instancia. En Docker con network_mode: host, la red es la de la instancia."""
    medidor = metrics.get_meter("host")
    psutil.cpu_percent(None)  # primera lectura de referencia

    def obs(valor, **atributos):
        return [Observation(valor, atributos)]

    medidor.create_observable_gauge("system_cpu_percent", callbacks=[lambda o: obs(psutil.cpu_percent(None))], unit="%",
                                    description="Uso de CPU de la instancia")
    medidor.create_observable_gauge("system_load_1m", callbacks=[lambda o: obs(psutil.getloadavg()[0])], unit="1",
                                    description="Carga promedio a 1 minuto")
    medidor.create_observable_gauge("system_memory_percent", callbacks=[lambda o: obs(psutil.virtual_memory().percent)], unit="%",
                                    description="Uso de memoria RAM")
    medidor.create_observable_gauge("system_memory_used_bytes", callbacks=[lambda o: obs(psutil.virtual_memory().used)], unit="By",
                                    description="Memoria RAM usada")
    medidor.create_observable_gauge("system_swap_percent", callbacks=[lambda o: obs(psutil.swap_memory().percent)], unit="%",
                                    description="Uso de swap")
    medidor.create_observable_gauge("system_disk_percent", callbacks=[lambda o: obs(psutil.disk_usage("/").percent)], unit="%",
                                    description="Uso del disco raiz")
    medidor.create_observable_counter("system_network_sent_bytes_total", callbacks=[lambda o: obs(psutil.net_io_counters().bytes_sent)],
                                      unit="By", description="Bytes enviados por la red")
    medidor.create_observable_counter("system_network_recv_bytes_total", callbacks=[lambda o: obs(psutil.net_io_counters().bytes_recv)],
                                      unit="By", description="Bytes recibidos por la red")

    def temperatura(_: CallbackOptions):
        try:
            sensores = psutil.sensors_temperatures()
        except (AttributeError, OSError):
            sensores = {}
        lecturas = [Observation(s.current, {"sensor": nombre}) for nombre, lista in sensores.items() for s in lista]
        if not lecturas and not _aviso_temperatura["emitido"]:
            _aviso_temperatura["emitido"] = True
            log.warning("temperatura_no_disponible", extra={"motivo": "la instancia no expone sensores"})
        return lecturas

    medidor.create_observable_gauge("system_temperature_celsius", callbacks=[temperatura], unit="Cel",
                                    description="Temperatura (solo si la instancia expone sensores)")
