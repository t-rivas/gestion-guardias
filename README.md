# Gestión de guardias

FastAPI, SQLAlchemy, PostgreSQL and Jinja2 app for monthly guard schedules.

## Run with Docker

```sh
cp .env.example .env
python3 -c 'import secrets; from pathlib import Path; p=Path(".env"); p.write_text(p.read_text().replace("SESSION_SECRET=", "SESSION_SECRET=" + secrets.token_urlsafe(48), 1))'
docker compose up --build -d
```

Open http://localhost:8001 and create your administrator account (minimum 12-character password). Passwords are stored as salted PBKDF2 hashes. All pages and write routes require a signed session; POST forms require CSRF tokens. The application and PostgreSQL ports bind to localhost by default. `docker compose down` stops the application and preserves the database volume.

## Workflow

1. Add/edit people and their recurring blocked weekdays. Notes are informational and never interpreted as rules.
2. Review monthly availability. Each person has separate **Guardia principal** and **Suplente** rows. Mark the days when they may serve in each role; the scheduler chooses among those days. Bulk changes can target either role or both. Existing availability initially applies to both roles. Weekdays are available by default; weekends and recurring blocked weekdays are unavailable, with monthly role exceptions taking precedence.
3. Generate a draft. Saved assignments remain unchanged until you apply the preview. Locked assignments survive generation.
4. Apply, edit, or swap assignments. Validation checks availability, duplicate assignments, and the two-per-ISO-week limit across month boundaries. Simultaneous changes are serialized and stale forms are rejected with a reload message.
5. Review and restore prior versions. Restoration rechecks current availability and weekly limits. A version referring to a deleted person cannot be restored ; prefer deactivation when preserving history matters.
6. Download CSV or all-day iCalendar events, or print the month. Exports contain the saved schedule; previews can be printed.

Coverage is maximized independently for each ISO week with min-cost max-flow. Reverse edges reconsider early choices so scarce availability does not cause avoidable gaps. The flow includes separate role capacities and a shared person/day capacity so main-only days never become substitute assignments and nobody occupies both roles on one day. Adjacent-month assignments and locks consume weekly capacity. Monthly workload and substitute counts guide balancing; consecutive-day avoidance is a soft preference, not a guaranteed rest rule.

## Migrations and backups

Versioned Alembic migrations run before the Docker server starts; they also adopt the existing unversioned schema without deleting scheduling records. Duplicate legacy availability records cause migration to stop with an actionable message rather than discarding data. Reconcile duplicates only after backing up and reviewing them. Downgrades intentionally refuse to destroy account/history data; restore a backup instead.

```sh
# Database backup (keep this private)
docker compose exec -T db pg_dump -U guardias guardias > backup.sql
# Local migration
alembic upgrade head
```

Password setup is retained for local development. Vercel and `APP_ENV=preview` or `production` require `AUTH_MODE=neon`, a stable `SESSION_SECRET`, secure cookies, an exact application origin, an approved-email list and a TLS Neon database connection. Missing configuration stops deployment startup. PostgreSQL supports transaction locks across workers; SQLite is used for isolated tests.

## Private access preview

The magic-link integration prototype retains FastAPI/Jinja2 and the Spanish interface. It checks live provider sessions and the current exact-email whitelist on every private request, uses CSRF/origin checks for forms, and verifies signed Neon delivery webhooks before sending mail. Rate limits and delivery receipts use shared database storage. The existing administrator record and scheduling data are preserved; password login and `/setup` are unavailable in Neon mode.

Read [the setup and verification guide](docs/private-access-setup.md) for environment settings, agent-operated provisioning/migration tools, protected-preview requirements and rollback. `.env.private-access` holds isolated preview secrets; `.env` remains the local environment. Live Neon login and email delivery must pass before production release. Vercel uses `app.main:app` on Python 3.12 and does not run migrations at function startup.

## Local development

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
docker compose up -d db
python run.py
```

`run.py` loads `.env`, runs Alembic migrations and starts the server. The default local bind address is 127.0.0.1.

## Tests

```sh
pytest -q
# Browser smoke tests run against an isolated temporary SQLite database:
python -m playwright install --with-deps chromium
python tests/browser_smoke.py
python tests/browser_role_availability.py
python tests/browser_private_access.py
```

The regression suite covers scheduling workflows under both local password and simulated Neon sessions, migration preservation, CSRF/origins, unauthorized writes/exports, whitelist removal, provider failures, callback cookies, signed webhooks, replay rejection, duplicate prevention and shared rate limits. Browser tests use disposable scheduling data; the auth browser test uses local HTTPS and a simulated provider. Live provider/inbox tests are recorded separately in [the implementation plan](docs/plans/private-access.md).
