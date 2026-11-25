#!/usr/bin/env python3
"""
Registra un evento del pipeline (resultado de pruebas, despliegue, etc.) en OpenObserve por HTTP/JSON.

Uso:
  python scripts/registrar_evento.py --evento pruebas --estado success --junit "reportes/*.xml"
  python scripts/registrar_evento.py --evento despliegue --estado failure --extra imagen=jlmh99/proyecto-usuarios:abc123

Variables: OO_URL (p. ej. http://HOST:5080), OO_USER, OO_PASS, OO_ORG (default), OO_STREAM (ci_cd).
Toma commit, rama y usuario de las variables que define GitHub Actions. Nunca hace fallar el pipeline:
si OpenObserve no responde, escribe una advertencia y termina con codigo 0 (salvo --estricto).
"""
import argparse
import base64
import glob
import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


def resumen_junit(patron: str) -> dict:
    total = fallos = errores = omitidas = 0
    archivos = glob.glob(patron)
    for ruta in archivos:
        raiz = ET.parse(ruta).getroot()
        suites = [raiz] if raiz.tag == "testsuite" else raiz.findall("testsuite")
        for s in suites:
            total += int(s.get("tests", 0))
            fallos += int(s.get("failures", 0))
            errores += int(s.get("errors", 0))
            omitidas += int(s.get("skipped", 0))
    return {"pruebas_total": total, "pruebas_fallidas": fallos + errores, "pruebas_omitidas": omitidas,
            "pruebas_aprobadas": total - fallos - errores - omitidas, "archivos_junit": len(archivos)}


def construir_evento(args) -> dict:
    e = os.environ
    repo, run_id = e.get("GITHUB_REPOSITORY", ""), e.get("GITHUB_RUN_ID", "")
    evento = {
        "_timestamp": int(datetime.now(timezone.utc).timestamp() * 1_000_000),
        "evento": args.evento,
        "estado": args.estado,
        "commit": e.get("GITHUB_SHA", ""),
        "commit_corto": e.get("GITHUB_SHA", "")[:7],
        "rama": e.get("GITHUB_REF_NAME", ""),
        "usuario": e.get("GITHUB_ACTOR", ""),
        "repositorio": repo,
        "workflow": e.get("GITHUB_WORKFLOW", ""),
        "run_id": run_id,
        "run_attempt": e.get("GITHUB_RUN_ATTEMPT", ""),
        "disparador": e.get("GITHUB_EVENT_NAME", ""),
        "url_ejecucion": f"https://github.com/{repo}/actions/runs/{run_id}" if repo and run_id else "",
    }
    if args.junit:
        evento.update(resumen_junit(args.junit))
    for par in args.extra or []:
        clave, _, valor = par.partition("=")
        evento[clave] = valor
    return evento


def enviar(evento: dict) -> int:
    base = os.environ.get("OO_URL", "").rstrip("/")
    if not base:
        print("[registrar_evento] Falta OO_URL; no se envia el evento.", file=sys.stderr)
        return 1
    org, flujo = os.environ.get("OO_ORG", "default"), os.environ.get("OO_STREAM", "ci_cd")
    token = base64.b64encode(f"{os.environ.get('OO_USER', '')}:{os.environ.get('OO_PASS', '')}".encode()).decode()
    peticion = urllib.request.Request(f"{base}/api/{org}/{flujo}/_json", data=json.dumps([evento]).encode(),
                                      headers={"Content-Type": "application/json", "Authorization": f"Basic {token}"}, method="POST")
    try:
        with urllib.request.urlopen(peticion, timeout=15) as r:
            print(f"[registrar_evento] OpenObserve respondio {r.status}: {r.read().decode()[:200]}")
        return 0
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"[registrar_evento] No se pudo enviar el evento: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--evento", required=True)
    p.add_argument("--estado", required=True)
    p.add_argument("--junit", help="patron de archivos JUnit XML, p. ej. 'reportes/*.xml'")
    p.add_argument("--extra", nargs="*", help="pares clave=valor adicionales")
    p.add_argument("--estricto", action="store_true", help="devolver error si no se pudo enviar")
    args = p.parse_args()
    evento = construir_evento(args)
    print("[registrar_evento] " + json.dumps({k: v for k, v in evento.items() if k != "_timestamp"}, ensure_ascii=False))
    codigo = enviar(evento)
    return codigo if args.estricto else 0


if __name__ == "__main__":
    sys.exit(main())
