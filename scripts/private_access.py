"""Agent-operated preview tools. Never print provider bodies, URLs or credentials."""

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run import load_env_file
from app.auth_config import AuthSettings, allowed_emails, database_url, normalized_email


async def probe(settings):
    from app.services.neon_auth import NeonAuth

    provider = NeonAuth(settings)
    response = await provider.call(".well-known/jwks.json")
    if response.status_code != 200 or not response.json().get("keys"):
        raise RuntimeError("The branch JWKS endpoint did not return verification keys.")
    response = await provider.call("get-session", params={"disableCookieCache": "true"})
    if response.status_code != 200 or response.json() is not None:
        raise RuntimeError("Anonymous provider session check did not return null.")
    print(
        "Branch JWKS reachable; anonymous provider session denied. Email/callback checks still pending."
    )


def provision(email):
    import httpx
    from sqlalchemy import create_engine, text

    email = normalized_email(email)
    if email not in allowed_emails():
        raise RuntimeError("Provision only an exact approved email.")
    project, branch, key = (
        os.getenv(name, "")
        for name in ("NEON_PROJECT_ID", "NEON_BRANCH_ID", "NEON_API_KEY")
    )
    if not key or not all(
        re.fullmatch(r"[a-z0-9-]{1,60}", value) for value in (project, branch)
    ):
        raise RuntimeError(
            "Enter the project ID, development branch ID and local-only Neon API key in the private file."
        )
    engine = create_engine(database_url(migration=True))
    # Read-only precheck makes repeated provisioning safe and verifies the identity's state.
    query = text(
        'SELECT id, "emailVerified" FROM neon_auth."user" WHERE lower(email) = :email'
    )
    with engine.connect() as connection:
        exists = connection.execute(query, {"email": email}).first()
    if exists:
        print(
            "Approved auth user already exists; no account or verification state changed."
        )
        engine.dispose()
        return
    with httpx.Client(timeout=15, follow_redirects=False) as client:
        response = client.post(
            f"https://console.neon.tech/api/v2/projects/{project}/branches/{branch}/auth/users",
            headers={"Authorization": f"Bearer {key}"},
            json={"email": email},
        )
    if response.status_code != 201:
        raise RuntimeError(
            f"Provider provisioning returned HTTP {response.status_code}; no automatic retry. Inspect account state before repeating."
        )
    with engine.connect() as connection:
        created = connection.execute(query, {"email": email}).first()
    engine.dispose()
    if not created or created[1]:
        raise RuntimeError(
            "Provider provisioning did not produce an unverified user. Resolve the actual provider behavior before live integration."
        )
    print(
        "Approved user provisioned without a password or verified-email shortcut. Inbox proof is still required."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["check", "probe", "migrate", "provision-user", "serve"]
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env.private-access"))
    parser.add_argument("--email", default="thiago.rivas0021@gmail.com")
    args = parser.parse_args()
    if not args.env_file.exists():
        parser.error("The private environment file is missing.")
    load_env_file(args.env_file)
    try:
        settings = AuthSettings.from_env()
        if settings.mode != "neon":
            raise RuntimeError("Preview tools require AUTH_MODE=neon.")
        database_url()
        if args.action == "check":
            print(
                "App/auth/database configuration is valid. Provider delivery and session behavior remain unverified."
            )
        elif args.action == "probe":
            asyncio.run(probe(settings))
        elif args.action == "migrate":
            from alembic import command
            from alembic.config import Config

            command.upgrade(Config("alembic.ini"), "head")
            print("Explicit migrations complete.")
        elif args.action == "provision-user":
            provision(args.email)
        else:
            import uvicorn

            # Separate from migrate; no migrations per startup and no token-bearing access logs.
            uvicorn.run(
                "app.main:app",
                host="127.0.0.1",
                port=int(os.getenv("APP_PORT", "8001")),
                access_log=False,
            )
    except Exception as error:
        # SQL/HTTP exceptions can contain credentials. Only our explicit messages are safe.
        if type(error) is RuntimeError:
            print(str(error), file=sys.stderr)
        else:
            print(
                f"Private-access operation failed ({type(error).__name__}); no credentials printed.",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
