"""Verify role selection and scheduling in a browser against disposable data."""

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
            DATABASE_URL=f"sqlite:///{temp}/role-browser.db",
            SESSION_SECRET="isolated-role-browser-test",
            AUTH_MODE="password",
            APP_ENV="development",
            COOKIE_SECURE="false",
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
                raise RuntimeError("Role test server did not start")
            with sync_playwright() as p:
                chrome = os.getenv("CHROME_EXECUTABLE")
                browser = p.chromium.launch(
                    **({"executable_path": chrome} if chrome else {})
                )
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base + "/setup")
                page.get_by_label("Usuario", exact=True).fill("admin")
                page.get_by_label("Contraseña", exact=True).fill(
                    "role-test-password-123"
                )
                page.get_by_label("Confirmar contraseña", exact=True).fill(
                    "role-test-password-123"
                )
                page.get_by_role("button", name="Crear cuenta", exact=True).click()
                page.goto(base + "/personas")
                for i in range(4):
                    page.get_by_label("Nombre completo", exact=True).fill(
                        f"Persona {i+1}"
                    )
                    page.get_by_role(
                        "button", name="Agregar persona", exact=True
                    ).click()
                    expect(page.locator(".summary-pill strong")).to_have_text(
                        str(i + 1)
                    )
                url = base + "/disponibilidad?year=2026&month=3"
                page.goto(url)
                expect(page.locator("[data-availability-toggle]")).to_have_count(
                    4 * 31 * 2
                )
                page.get_by_role(
                    "button", name="Marcar no disponibles", exact=True
                ).click()
                page.get_by_role("button", name="Guardar cambios", exact=True).click()
                expect(page.get_by_role("status").first).to_contain_text(
                    "Disponibilidad guardada"
                )
                page.locator("[data-bulk-start]").fill("2026-03-02")
                page.locator("[data-bulk-end]").fill("2026-03-02")
                for i in range(4):
                    page.locator("[data-bulk-person]").select_option(
                        label=f"Persona {i+1}"
                    )
                    page.locator("[data-bulk-role]").select_option(
                        "primary" if i < 3 else "substitute"
                    )
                    page.get_by_role(
                        "button", name="Marcar disponibles", exact=True
                    ).click()
                page.get_by_role("button", name="Guardar cambios", exact=True).click()
                expect(page.get_by_role("status").first).to_contain_text(
                    "Disponibilidad guardada"
                )
                # Changing primary does not accidentally change substitute for the same date/person.
                for i in range(4):
                    for role in ("primary", "substitute"):
                        expected = (
                            "true"
                            if (i < 3 and role == "primary")
                            or (i == 3 and role == "substitute")
                            else "false"
                        )
                        toggle = page.locator(
                            f'[data-person-id="{i+1}"][data-day="2026-03-02"][data-role="{role}"]'
                        )
                        expect(toggle).to_have_attribute("data-available", expected)
                artifacts = Path(".local-backups/ui-checks")
                artifacts.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(artifacts / "role-availability-desktop.png"))
                page.set_viewport_size({"width": 390, "height": 1000})
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth + 1"
                )
                page.screenshot(path=str(artifacts / "role-availability-mobile.png"))
                page.set_viewport_size({"width": 1440, "height": 1000})
                page.goto(base + "/calendario?year=2026&month=3")
                page.get_by_role("button", name="Generar borrador", exact=True).click()
                expect(
                    page.get_by_role(
                        "heading", name="Borrador para revisar", exact=True
                    )
                ).to_be_visible()
                expect(
                    page.locator(".summary-stat").first.locator("strong")
                ).to_have_text("4")
                row = page.locator(".schedule-table tbody tr").nth(1)
                for i in range(4):
                    expect(row.locator(".assignment-cell").nth(i)).to_contain_text(
                        f"Persona {i+1}" if i == 3 else "Persona"
                    )
                assert (
                    "Persona 4"
                    not in row.locator(".assignment-cell").nth(0).inner_text()
                )
                page.get_by_role("button", name="Aplicar borrador", exact=True).click()
                expect(page.get_by_role("status")).to_contain_text(
                    "Calendario guardado"
                )
                # A real single-cell edit persists only that role.
                page.goto(url)
                page.locator(
                    '[data-person-id="1"][data-day="2026-03-03"][data-role="substitute"]'
                ).click()
                page.get_by_role("button", name="Guardar cambios", exact=True).click()
                expect(
                    page.locator(
                        '[data-person-id="1"][data-day="2026-03-03"][data-role="substitute"]'
                    )
                ).to_have_attribute("data-available", "true")
                expect(
                    page.locator(
                        '[data-person-id="1"][data-day="2026-03-03"][data-role="primary"]'
                    )
                ).to_have_attribute("data-available", "false")
                assert not errors, errors
                browser.close()
                print(
                    "Role browser passed: independent row toggles, role-specific bulk edits, persistence, correct 3+1 draft, apply, desktop and mobile layout."
                )
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
