"""Full browser workflow using a disposable SQLite DB, never the live app."""

import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from playwright.sync_api import sync_playwright, expect


def main():
    with tempfile.TemporaryDirectory() as temp:
        environment = dict(
            os.environ,
            DATABASE_URL=f"sqlite:///{temp}/browser.db",
            SESSION_SECRET="isolated-browser-test-secret",
        )
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=environment,
            check=True,
        )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            base = f"http://127.0.0.1:{port}"
            for attempt in range(100):
                try:
                    urllib.request.urlopen(base + "/health", timeout=1)
                    break
                except Exception:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Isolated browser server did not start")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                context = browser.new_context(viewport={"width": 1440, "height": 1000})
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base)
                expect(
                    page.get_by_role("heading", name="Configurá tu cuenta")
                ).to_be_visible()
                page.get_by_label("Usuario", exact=True).fill("admin")
                page.get_by_label("Contraseña", exact=True).fill("browser-password-123")
                page.get_by_label("Confirmar contraseña", exact=True).fill(
                    "browser-password-123"
                )
                page.get_by_role("button", name="Crear cuenta").click()
                page.get_by_role("link", name="Personas", exact=True).first.click()
                for i in range(14):
                    page.get_by_label("Nombre completo", exact=True).fill(
                        f"Persona {i:02}"
                    )
                    page.get_by_role(
                        "button", name="Agregar persona", exact=True
                    ).click()
                    expect(page.locator(".summary-pill strong")).to_have_text(
                        str(i + 1)
                    )
                page.goto(base + "/disponibilidad?year=2026&month=3")
                page.locator("[data-bulk-weekday]").select_option("weekends")
                page.get_by_role(
                    "button", name="Marcar disponibles", exact=True
                ).click()
                expect(
                    page.get_by_role("button", name="Guardar cambios", exact=True)
                ).to_be_enabled()
                page.get_by_role("button", name="Guardar cambios", exact=True).click()
                expect(page.get_by_role("status").first).to_contain_text(
                    "Disponibilidad guardada"
                )
                page.goto(base + "/calendario?year=2026&month=3")
                page.get_by_role("button", name="Generar borrador", exact=True).click()
                expect(
                    page.get_by_role(
                        "heading", name="Borrador para revisar", exact=True
                    )
                ).to_be_visible()
                expect(
                    page.locator(".summary-stat").nth(1).locator("strong")
                ).to_have_text("0")
                page.get_by_role("button", name="Aplicar borrador", exact=True).click()
                expect(page.get_by_role("status")).to_contain_text(
                    "Calendario guardado"
                )
                editor = page.locator(".assignment-cell details").first
                editor.locator("summary").click()
                editor.get_by_label("Conservar al generar").check()
                editor.get_by_role(
                    "button", name="Guardar asignación", exact=True
                ).click()
                expect(page.locator(".lock-label").first).to_be_visible()
                page.get_by_role("button", name="Generar borrador", exact=True).click()
                expect(page.locator(".lock-label").first).to_be_visible()
                page.get_by_role("link", name="Volver al guardado", exact=True).click()
                artifacts=Path(".local-backups/ui-checks"); artifacts.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(artifacts/"calendar-desktop.png"),full_page=False)
                for name in ("Descargar CSV", "Exportar al calendario"):
                    with page.expect_download() as download:
                        page.get_by_role("link", name=name, exact=True).click()
                    assert download.value.suggested_filename.startswith(
                        "guardias-2026-03"
                    )
                page.get_by_role("row").filter(has_text="Guardada").get_by_role("link", name="Revisar versión", exact=True).last.click()
                expect(
                    page.get_by_role("heading", name="Versión anterior", exact=True)
                ).to_be_visible()
                page.on("dialog", lambda dialog: dialog.accept())
                page.get_by_role("button", name="Restaurar versión", exact=True).click()
                expect(
                    page.locator(".summary-stat").nth(0).locator("strong")
                ).to_have_text("0")
                page.goto(base + "/personas")
                person_editor = page.locator("details.editor").first
                person_editor.locator("summary").click()
                person_editor.get_by_label("Nombre", exact=True).fill("Persona editada")
                person_editor.get_by_label("Vie", exact=True).check()
                person_editor.get_by_role(
                    "button", name="Guardar persona", exact=True
                ).click()
                expect(page.get_by_text("Persona editada", exact=True)).to_be_visible()
                # Check scrolling stays inside tables and mobile layout keeps page controls reachable.
                for width in (1440, 390):
                    page.set_viewport_size({"width": width, "height": 1000})
                    for path in (
                        "/",
                        "/personas",
                        "/disponibilidad?year=2026&month=3",
                        "/calendario?year=2026&month=3",
                    ):
                        page.goto(base + path)
                        assert page.evaluate(
                            "document.documentElement.scrollWidth <= window.innerWidth + 1"
                        ), path
                page.screenshot(path=str(artifacts/"calendar-mobile.png"),full_page=False)
                page.get_by_role("button", name="Activar modo nocturno", exact=True).click()
                assert page.locator("html").get_attribute("data-theme") == "dark"
                page.get_by_role("button", name="Cerrar sesión", exact=True).click()
                expect(
                    page.get_by_role("heading", name="Ingresar", exact=True)
                ).to_be_visible()
                assert not errors, errors
                browser.close()
                print(
                    "Browser smoke passed: setup, 14 people, bulk availability, full draft, apply, locks, exports, history restore, editing, mobile layout, theme, logout."
                )
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
