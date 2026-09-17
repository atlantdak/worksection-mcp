"""A short-lived HTTPS listener on 127.0.0.1 that catches the OAuth redirect.

It binds the loopback interface only, serves one fixed page, and shuts down as
soon as the browser has been redirected back. It is never the MCP transport.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import ipaddress
import socket
import ssl
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from urllib.parse import parse_qs, urlparse

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from worksection_mcp.logging_setup import get_logger
from worksection_mcp.secure_io import ensure_private_dir, write_secret_file

logger = get_logger("auth.callback")

LOOPBACK = "127.0.0.1"
CERT_VALID_DAYS = 365
RESPONSE_BODY = (
    "<!doctype html><html><head><meta charset='utf-8'><title>Worksection</title></head>"
    "<body style='font-family:sans-serif;padding:3rem'>"
    "<h1>Authorization complete</h1>"
    "<p>You can close this window and return to your terminal.</p>"
    "</body></html>"
)


@dataclass(frozen=True)
class CallbackResult:
    """What came back on the redirect."""

    code: str | None
    state: str | None
    error: str | None


def parse_callback_target(target: str) -> CallbackResult:
    """Pull ``code``, ``state`` and ``error`` out of the request target."""
    query = parse_qs(urlparse(target).query)

    def first(key: str) -> str | None:
        values = query.get(key)
        return values[0] if values else None

    return CallbackResult(code=first("code"), state=first("state"), error=first("error"))


def _certificate_is_current(cert_path: Path) -> bool:
    try:
        certificate = x509.load_pem_x509_certificate(cert_path.read_bytes())
    except (OSError, ValueError):
        return False
    return certificate.not_valid_after_utc > dt.datetime.now(dt.UTC)


def ensure_self_signed_cert(cert_dir: Path) -> tuple[Path, Path]:
    """Return (cert, key) for 127.0.0.1, creating them if needed."""
    ensure_private_dir(cert_dir)
    cert_path = cert_dir / "callback-cert.pem"
    key_path = cert_dir / "callback-key.pem"
    if cert_path.is_file() and key_path.is_file() and _certificate_is_current(cert_path):
        return cert_path, key_path

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, LOOPBACK)])
    now = dt.datetime.now(dt.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=CERT_VALID_DAYS))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(LOOPBACK))]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    write_secret_file(cert_path, certificate.public_bytes(serialization.Encoding.PEM))
    write_secret_file(
        key_path,
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ),
    )
    return cert_path, key_path


class LocalCallbackServer:
    """Accepts exactly the OAuth redirect, on the loopback interface, over TLS."""

    def __init__(
        self,
        *,
        port: int,
        cert_path: Path,
        key_path: Path,
        host: str = LOOPBACK,
    ) -> None:
        if host not in (LOOPBACK, "localhost"):
            raise ValueError("the callback listener may only bind the loopback interface")
        self._host = LOOPBACK
        self._port = port
        self._cert_path = cert_path
        self._key_path = key_path
        self._server: asyncio.Server | None = None
        self._future: asyncio.Future[CallbackResult] | None = None

    async def start(self) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=str(self._cert_path), keyfile=str(self._key_path))
        self._future = asyncio.get_running_loop().create_future()
        self._server = await asyncio.start_server(
            self._handle, host="127.0.0.1", port=self._port, ssl=context
        )
        logger.info("OAuth callback listener ready on %s", self.redirect_uri)

    async def aclose(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def __aenter__(self) -> LocalCallbackServer:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    @property
    def sockets(self) -> tuple[socket.socket, ...]:
        return tuple(self._server.sockets) if self._server and self._server.sockets else ()

    @property
    def actual_port(self) -> int:
        if not self._server or not self._server.sockets:
            raise RuntimeError("callback server is not running")
        return int(self._server.sockets[0].getsockname()[1])

    @property
    def redirect_uri(self) -> str:
        return f"https://{self._host}:{self.actual_port}/callback"

    async def wait_for_callback(self, timeout: float = 300.0) -> CallbackResult:  # noqa: ASYNC109
        """Block until the browser is redirected back, or raise TimeoutError."""
        if self._future is None:
            raise RuntimeError("callback server is not running")
        return await asyncio.wait_for(asyncio.shield(self._future), timeout=timeout)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=10.0)
            target = request_line.decode("latin-1").split(" ")[1] if b" " in request_line else "/"
            body = RESPONSE_BODY.encode("utf-8")
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/html; charset=utf-8\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"Connection: close\r\n\r\n" + body
            )
            await writer.drain()
            if self._future is not None and not self._future.done():
                self._future.set_result(parse_callback_target(target))
                # The one callback we were waiting for has arrived; stop
                # accepting further connections rather than leaving the
                # listener open as an attack surface for the rest of the
                # process lifetime.
                if self._server is not None:
                    self._server.close()
        except (TimeoutError, OSError, IndexError, UnicodeDecodeError) as exc:
            logger.warning("callback connection failed: %s", type(exc).__name__)
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
