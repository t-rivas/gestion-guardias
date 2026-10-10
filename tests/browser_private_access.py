"""HTTPS browser contract check with a simulated provider and disposable database."""

import ipaddress
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def serve(base, cert, key):
    import pytest
    import uvicorn
    from tests.neon_provider import configure_neon

    configure_neon(SimpleNamespace(), pytest.MonkeyPatch(), base)
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=int(base.rsplit(":", 1)[1]),
        ssl_certfile=cert,
        ssl_keyfile=key,
        access_log=False,
        log_level="error",
    )


def certificate(directory):
    from datetime import datetime, timedelta, timezone
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = directory / "cert.pem", directory / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return str(cert_path), str(key_path)


def main():
    from playwright.sync_api import expect, sync_playwright

    with tempfile.TemporaryDirectory() as temp:
        directory = Path(temp)
        environment = dict(
            os.environ,
            DATABASE_URL=f"sqlite:///{temp}/auth-browser.db",
            MIGRATION_DATABASE_URL="",
            AUTH_MODE="password",
            APP_ENV="development",
            SESSION_SECRET="isolated-test-secret",
            COOKIE_SECURE="true",
            SQLALCHEMY_ECHO="false",
        )
        environment.pop("VERCEL", None)
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=environment,
            check=True,
        )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"https://127.0.0.1:{port}"
        cert, key = certificate(directory)
        with sync_playwright() as playwright:
            for engine in (playwright.chromium, playwright.webkit):
                server = subprocess.Popen(
                    [sys.executable, __file__, "--serve", base, cert, key],
                    env=environment,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                browser = None
                try:
                    context = ssl._create_unverified_context()
                    for _ in range(100):
                        try:
                            urllib.request.urlopen(
                                base + "/health", context=context, timeout=1
                            )
                            break
                        except Exception:
                            time.sleep(0.1)
                    else:
                        raise RuntimeError("Isolated HTTPS auth server did not start.")
                    browser = engine.launch()
                    browser_context = browser.new_context(
                        ignore_https_errors=True, viewport={"width": 390, "height": 844}
                    )
                    page = browser_context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(base + "/personas")
                    expect(
                        page.get_by_role("heading", name="Ingresar", exact=True)
                    ).to_be_visible()
                    page.get_by_label("Correo electrónico").fill(
                        "thiago.rivas0021@gmail.com"
                    )
                    page.get_by_role("button", name="Enviar enlace", exact=True).click()
                    expect(page.get_by_role("status")).to_have_text(
                        "Si el correo tiene acceso, recibirás un enlace."
                    )
                    # Another device/context can redeem the simulated email token without login-page cookies.
                    other = browser.new_context(
                        ignore_https_errors=True, viewport={"width": 390, "height": 844}
                    )
                    signed_page = other.new_page()
                    signed_page.goto(
                        base + "/auth/callback?token=valid-token&next=/personas"
                    )
                    expect(
                        signed_page.get_by_role("link", name="Inicio", exact=True)
                    ).to_be_visible()
                    auth_cookie = next(
                        item
                        for item in other.cookies()
                        if item["name"].endswith(".session_token")
                    )
                    assert (
                        auth_cookie["secure"]
                        and auth_cookie["httpOnly"]
                        and auth_cookie["sameSite"] == "Lax"
                    )
                    person_name = f"Persona {engine.name}"
                    signed_page.get_by_label("Nombre completo", exact=True).fill(
                        person_name
                    )
                    signed_page.get_by_role(
                        "button", name="Agregar persona", exact=True
                    ).click()
                    expect(
                        signed_page.get_by_text(person_name, exact=True)
                    ).to_be_visible()
                    signed_page.get_by_role(
                        "button", name="Cerrar sesión", exact=True
                    ).click()
                    expect(
                        signed_page.get_by_role("heading", name="Ingresar", exact=True)
                    ).to_be_visible()
                    signed_page.goto(base + "/auth/callback?token=valid-token")
                    expect(signed_page.get_by_role("alert")).to_contain_text(
                        "El enlace venció o ya se usó"
                    )
                    signed_page.goto(base + "/personas")
                    expect(
                        signed_page.get_by_role("heading", name="Ingresar", exact=True)
                    ).to_be_visible()
                    assert not errors
                    print(
                        f"{engine.name}: mobile email form, HTTPS cookies, cross-device callback, protected write, logout, reused-link recovery passed with simulated provider."
                    )
                finally:
                    if browser:
                        browser.close()
                    server.terminate()
                    server.wait(timeout=10)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        serve(*sys.argv[2:])
    else:
        main()
