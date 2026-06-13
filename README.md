# Guard Scheduling App

A small web app for managing people availability and generating monthly guard schedules.

## What It Does

- Manage active and inactive people.
- Register each person's monthly availability.
- Generate a monthly guard calendar automatically.
- Assign up to 3 primary people and 1 substitute per day.
- Avoid unavailable days and limit weekly assignments per person.
- Show incomplete days or conflicts after availability changes.

## Tech Stack

- Python 3.12
- FastAPI
- SQLAlchemy
- PostgreSQL
- Jinja2
- Docker Compose

## Installation With Docker

Requirements:

- Git
- Docker
- Docker Compose

Clone the repository:

```bash
git clone <REPOSITORY_URL>
cd gestion-guardias
```

Create the environment file:

```bash
cp .env.example .env
```

Start the app in the background:

```bash
docker-compose up --build -d
```

Open:

```text
http://localhost:8001
```

Check the containers:

```bash
docker-compose ps
```

To stop it:

```bash
docker-compose down
```

To stop it and delete the local database volume:

```bash
docker-compose down -v
```

If you use Docker Compose v2, you can use `docker compose` instead of `docker-compose`.

If legacy `docker-compose` prints a `watch_events` traceback while running in attached mode, use the detached command above. It is a Compose client issue; the containers can still be checked with `docker-compose ps`.

## Local Development

Run PostgreSQL with Docker:

```bash
docker-compose up -d db
```

Install Python dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the app:

```bash
python run.py
```

The app will be available at `http://localhost:8001`. The terminal also prints a LAN URL that can be used from another device on the same network.
