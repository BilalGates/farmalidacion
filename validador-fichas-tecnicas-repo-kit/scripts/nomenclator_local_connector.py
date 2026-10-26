"""Conector local: lee dbo.nomenclatur con la identidad SQL del usuario.

Se escucha exclusivamente en 127.0.0.1. La contraseña, cuando se usa, sólo
atraviesa la llamada local y no se escribe a disco ni se envía a Farmalidación.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import import_module
from pathlib import Path
from urllib.parse import urlparse

EXPECTED_COLUMNS = {
    0: "ID_ASSERTA", 1: "cod_nacion", 2: "nro_definitivo", 5: "cod_dcsa",
    6: "cod_dcp", 7: "cod_dcpf", 20: "url_fictec", 23: "sw_generico",
    26: "sw_uso_hospitalario", 43: "biosimilar", 48: "cod_atc",
    59: "formafarmaceutica", 62: "FECHA_ACTUALIZACIÓN", 63: "estado",
    65: "principioactivo",
}
MAX_ROWS = 200_000
MAX_BYTES = 100_000_000
VERSION = "2"
ROUTES = {"/snapshot", "/shutdown"}


def _text(value: object) -> str:
    result = "" if value is None else str(value)
    if any(character in result for character in ("\t", "\r", "\n")):
        raise ValueError("La tabla contiene tabuladores o saltos de línea.")
    return result


def _connection_options(payload: dict[str, object]) -> dict[str, object]:
    server = str(payload.get("server", "")).strip()
    database = str(payload.get("database", "")).strip()
    auth = payload.get("auth")
    port = payload.get("port", 0)
    if not server or len(server) > 255 or not database or len(database) > 128:
        raise ValueError("Indique servidor y base de datos.")
    if not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("El puerto debe estar entre 0 y 65535.")
    if auth not in ("windows", "sql"):
        raise ValueError("Elija autenticación de Windows o de SQL Server.")
    options: dict[str, object] = {
        "server": f"{server},{port}" if port else server,
        "database": database,
        "encrypt": "no" if payload.get("encrypt") is False else "yes",
        "applicationintent": "ReadOnly", "timeout": 15,
        "trust_server_certificate": (
            "yes" if payload.get("trust_server_certificate") is True else "no"
        ),
    }
    if auth == "windows":
        options["trusted_connection"] = "yes"
    else:
        username = str(payload.get("username", "")).strip()
        password = payload.get("password")
        if not username or len(username) > 128 or not isinstance(password, str) or not password:
            raise ValueError("Indique usuario y contraseña de SQL Server.")
        options.update(uid=username, pwd=password)
    return options


def export_snapshot(payload: dict[str, object], destination: Path) -> tuple[str, int]:
    """Consulta únicamente la tabla pactada y falla si cambia su estructura."""
    options = _connection_options(payload)
    connection = import_module("mssql_python").connect(**options)
    digest = hashlib.sha256()
    rows = 0
    size = 0
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(
                "SELECT * FROM [dbo].[nomenclatur] "
                "ORDER BY [cod_nacion], [ID_ASSERTA]"
            )
            description = cursor.description
            if not description or len(description) != 73:
                raise ValueError("El esquema de dbo.nomenclatur no tiene 73 columnas.")
            names = [str(column[0]).casefold() for column in description]
            for index, expected in EXPECTED_COLUMNS.items():
                if names[index] != expected.casefold():
                    raise ValueError(f"Cambió la columna {index + 1} de dbo.nomenclatur.")
            with destination.open("wb") as output:
                while batch := cursor.fetchmany(1000):
                    for record in batch:
                        if len(record) != 73:
                            raise ValueError("Una fila de Nomenclátor no tiene 73 columnas.")
                        line = ("\t".join(_text(value) for value in record) + "\n").encode("utf-8")
                        rows += 1
                        size += len(line)
                        if rows > MAX_ROWS or size > MAX_BYTES:
                            raise ValueError("La tabla excede el límite de sincronización.")
                        output.write(line)
                        digest.update(line)
            if rows == 0:
                raise ValueError("La tabla de Nomenclátor está vacía.")
            return digest.hexdigest(), rows
        finally:
            cursor.close()
    finally:
        connection.close()


class ConnectorHandler(BaseHTTPRequestHandler):
    allowed_origin = ""
    # Una sola lectura a la vez: evita consultas paralelas sobre SQL Server.
    export_lock = threading.Lock()

    def log_message(self, format: str, *args: object) -> None:
        # No registrar peticiones: pueden contener configuraciones sensibles.
        pass

    def _origin_allowed(self) -> bool:
        return self.headers.get("Origin") == self.allowed_origin

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", self.allowed_origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, status: int, body: dict[str, object]) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        if self._origin_allowed():
            self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_OPTIONS(self) -> None:
        if self.path not in ROUTES or not self._origin_allowed():
            self._json(403, {"detail": "Origen no autorizado."})
            return
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path != "/health" or not self._origin_allowed():
            self._json(403, {"detail": "Origen no autorizado."})
            return
        self._json(200, {
            "ready": True, "version": VERSION, "busy": self.export_lock.locked(),
        })

    def _shutdown(self) -> None:
        if self.export_lock.locked():
            self._json(409, {"detail": "Hay una lectura en curso; espere a que termine."})
            return
        self._json(200, {"closing": True})
        # shutdown() bloquea hasta salir de serve_forever: se lanza fuera del handler.
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def do_POST(self) -> None:
        if self.path not in ROUTES or not self._origin_allowed():
            self._json(403, {"detail": "Origen no autorizado."})
            return
        if self.path == "/shutdown":
            self._shutdown()
            return
        if not self.export_lock.acquire(blocking=False):
            self._json(409, {"detail": "Ya hay una lectura en curso en este equipo."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError("Configuración de conexión demasiado grande o vacía.")
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("La petición debe contener JSON.")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise TypeError("La configuración no es válida.")
            with tempfile.TemporaryDirectory(prefix="farmalidacion-nomenclator-") as folder:
                path = Path(folder) / "snapshot.tsv"
                _, rows = export_snapshot(payload, path)
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "text/tab-separated-values; charset=utf-8")
                self.send_header("Content-Length", str(path.stat().st_size))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                with path.open("rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        self.wfile.write(chunk)
                del rows
        except (TypeError, ValueError) as error:
            self._json(422, {"detail": str(error)})
        except Exception:  # noqa: BLE001 - El controlador SQL expone errores propios.
            self._json(502, {"detail": (
                "No se pudo consultar SQL Server desde este equipo. "
                "Revise servidor, puerto, autenticación y cifrado."
            )})
        finally:
            self.export_lock.release()


def main() -> None:
    parser = argparse.ArgumentParser(description="Conector local de Nomenclátor")
    parser.add_argument("--origin", required=True, help="Origen HTTPS exacto de Farmalidación")
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()
    parsed = urlparse(arguments.origin)
    if parsed.scheme not in ("https", "http") or not parsed.netloc or parsed.path != "":
        parser.error("--origin debe ser el origen web, sin ruta final")
    ConnectorHandler.allowed_origin = arguments.origin.rstrip("/")
    server = ThreadingHTTPServer(("127.0.0.1", arguments.port), ConnectorHandler)
    print(f"Conector Nomenclátor listo en 127.0.0.1:{arguments.port}.")
    print("Puede cerrarlo desde Farmalidación al terminar; los datos ya sincronizados se conservan.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
