import os
import socket
from pathlib import Path

import uvicorn


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def get_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    load_env_file(Path(".env"))

    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8001"))
    reload = env_bool("APP_RELOAD", True)

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")

    print(f"Local: http://127.0.0.1:{port}")
    if host == "0.0.0.0":
        print(f"LAN:   http://{get_lan_ip()}:{port}")

    uvicorn.run("app.main:app", host=host, port=port, reload=reload)
