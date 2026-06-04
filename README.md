# Gestión de Guardias

Aplicación web interna para administrar personas, registrar disponibilidad mensual y generar un calendario equilibrado de guardias.

## Stack

- Python 3.12
- FastAPI
- SQLAlchemy
- PostgreSQL 16
- Jinja2
- HTML, CSS y JavaScript vanilla
- Docker Compose para la base de datos

## Documentación

- [Guía de instalación](INSTALLATION.md)
- [Descripción del sistema](SYSTEM_DESCRIPTION.md)

## Inicio rápido

```bash
docker compose up -d db
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Abrir `http://localhost:8001`.
