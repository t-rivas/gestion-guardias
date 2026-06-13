# Guía de instalación

La guía principal de instalación está en el [README](README.md).

## Instalación recomendada

```bash
git clone <URL_DEL_REPOSITORIO>
cd gestion-guardias
cp .env.example .env
docker-compose up --build
```

Abrir:

```text
http://localhost:8001
```

En Docker Compose v2, el comando equivalente es:

```bash
docker compose up --build
```

## Ejecución local para desarrollo

```bash
docker-compose up -d db
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python run.py
```

La aplicación imprime una URL local y una URL LAN para usarla desde otros dispositivos de la red.
