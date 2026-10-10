# Private access: preview setup and verification

The implementation is an integration prototype until the live checks below pass.
The existing local password mode and scheduling data are preserved. Vercel and
`APP_ENV=preview`/`production` require Neon; missing configuration stops startup.
There is no deployed `/setup` or password fallback.

## Current setup

- Owner: `thiago.rivas0021@gmail.com`; mother's address is still pending.
- User prefers creating Neon through the [Vercel Marketplace](https://vercel.com/marketplace/neon/neon).
- Screenshots confirm `neon-gestion-guardias` (`plain-lab-97919633`) is Available on Free, in AWS US East 1 (N. Virginia), and connected to `gestion-guardias`. On 2026-10-10 the user explicitly selected `main` for implementation and declined creating a development branch.
- User reports only Magic Link enabled on `main` and confirms Allow New User Registration is off. The user corrected the expiration to **5 minutes**, so the plan's 15-minute setting is still outstanding. Auth Base URL and project ID are saved in `.env.private-access`. A live read-only probe passed: branch JWKS returned keys and the anonymous session endpoint returned null. Approved-user provisioning, email delivery and authenticated callbacks remain pending.
- User reported having neither SMTP credentials nor a sender domain.
- `.env.private-access` is gitignored and initially created with mode `0600`,
  its own stable session secret; Auth Base URL/project ID are now populated, while database/admin/sender credentials have not been supplied.
  Existing `.env` values were retained. Never paste credentials or login links in chat.
- Deployment URL: `https://gestion-guardias-two.vercel.app`. On 2026-10-10 anonymous GETs to `/`, `/login`, `/setup`, `/health` and `/personas` all returned HTTP 500 with `FUNCTION_INVOCATION_FAILED`; deployed startup/configuration is unresolved. This URL is saved as `APP_BASE_URL` locally with `COOKIE_SECURE=true`.
- User approved committing and pushing the complete reviewed app/auth/scheduling change set to `t-rivas/auth-login-flow` on 2026-10-10. Publication is in progress; GitHub main remains at `132b68f`. The latest Python 3.12 verification passed 87 tests, with one PostgreSQL integration test skipped.
  The deployed revision and exact `main` branch identifier remain to be recorded.
  No live auth/email flow, data transfer, or completed production release is verified.

## Environment settings

Use the existing `main` branch for setup, as explicitly requested on 2026-10-10.
Keep database, Auth Base URL and migrations pointed at this same branch.

| Setting | Preview value / purpose |
| --- | --- |
| `AUTH_MODE` | `neon` |
| `APP_ENV` | `preview` on Vercel; `development` for isolated local tests |
| `APP_BASE_URL` | Exact stable HTTPS preview origin, without a path or trailing slash |
| `NEON_AUTH_BASE_URL` | Selected `main` branch's Auth Base URL ending in `/auth` |
| `ALLOWED_EMAILS` | `thiago.rivas0021@gmail.com`; comma-separated exact addresses only |
| `DATABASE_URL` | Pooled Neon PostgreSQL URL with `sslmode=require` or stronger |
| `MIGRATION_DATABASE_URL` | Direct connection to the same branch, with TLS; local release tool only |
| `SESSION_SECRET` | Stable secret from private file; unrelated to Neon identity verification |
| `COOKIE_SECURE` | `true` for HTTPS preview/production |
| `SQLALCHEMY_ECHO` | `false` |
| `SMTP_HOST`, `SMTP_PORT` | Authenticated sender host and TLS port |
| `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | Sender credentials and address; secret entry only |
| `SMTP_SECURITY` | `starttls` (usually 587) or `ssl` (usually 465); no plaintext SMTP |
| `NEON_PROJECT_ID`, `NEON_BRANCH_ID`, `NEON_API_KEY` | Local provisioning only; never deploy the administrative API key |

The Vercel native integration may supply `DATABASE_URL`; confirm its selected
branch and TLS settings. Integration database creation does not configure magic
links, whitelist webhooks, or the application environment automatically.

For the owner-only initial trial, a Gmail app password may avoid buying a domain
if the account supports it. [Google requires 2-Step Verification and documents
account restrictions](https://support.google.com/accounts/answer/185833).
Verify availability at https://myaccount.google.com/apppasswords before choosing
this path; keep MFA enabled and use an app password rather than the normal mailbox
password. No sender has been selected or configured yet. If available, use
`smtp.gmail.com`, port `587`, `starttls`, and the mailbox address for username/from.
Configure credentials in the app's secret environment, because the signed webhook
is the sole magic-link delivery path. Do not also enable a competing Neon SMTP path.

## Agent-operated local tools

The agent runs these after the user has entered the relevant secrets. Each tool
reads `.env.private-access` without sourcing it in a shell or printing its values.
Environment variables already set in the process take precedence; inspect their
presence before running a tool against another environment.

```sh
python scripts/private_access.py check
python scripts/private_access.py probe
python scripts/private_access.py migrate
python scripts/private_access.py provision-user --email thiago.rivas0021@gmail.com
python scripts/private_access.py serve
```

`check` validates configuration without reaching a provider. `probe` checks JWKS
and the anonymous session response, without sending email. `migrate` is an explicit
Alembic operation. `provision-user` first checks the branch's existing auth user,
creates only an approved email with no password, and checks that provisioning did
not mark it verified. Resolve any actual provider difference before proceeding.
`serve` binds locally, disables access logs, and does not run migrations. Use HTTPS
for browser integration (an HTTPS preview or tunnel); provider cookies always use
Secure and HttpOnly, including their `__Secure-` name.

## Provider configuration before a live login

Use the branch's current dashboard or the official branch APIs, inspected before
making changes. The agent handles authenticated API calls when access is available.

1. Enable Magic Link with `expires_in=15`, `disable_sign_up=true`. Disable
   email/password, OAuth, OTP, anonymous and other unused public login/signup
   mechanisms that the branch actually exposes.
2. Add only the exact app origin to trusted redirect origins; allow localhost only
   on development branches. Provision the approved user without marking email
   verified. The first link must prove inbox ownership.
3. Enable the webhook at `/webhooks/neon-auth` and subscribe to `send.magic_link`
   and `user.before_create`, with a per-attempt timeout that permits TLS SMTP
   delivery (maximum 10 seconds). The latter event returns an exact-email signup
   decision; the former never sends to an unapproved recipient.

References: [magic-link configuration](https://neon.com/docs/auth/guides/plugins/magic-link),
[signed webhook envelope and retries](https://neon.com/docs/auth/guides/webhooks),
[user provisioning API](https://neon.com/docs/reference/api/auth/create-branch-neon-auth-new-user).

The app rewrites a verified branch-owned delivery URL to its fixed callback, then
redeems the token server-side. It follows no upstream redirects and validates the
resulting session before setting host-only cookies. Only the provider's
`__Secure-neon-auth.session_token` cookie crosses the bridge. Cached identity
cookies, authorization headers, arbitrary auth operations and browser email claims
are never accepted as access proof. Every protected request revalidates the live
provider session and current whitelist. The app enforces seven days from provider
session creation; a shorter provider expiry wins. The actual provider lifetime
setting remains to be confirmed live.

Shared tables `auth_rate_limits` and `auth_deliveries` contain counters and hashed
receipt fingerprints, with no raw email links or session credentials. A receipt
is committed before SMTP starts. Successful retries do not resend. If SMTP times
out or a function crashes after claiming the event, delivery is uncertain and that
event is never resent: request a fresh link after the cooldown. This intentionally
trades automatic recovery for duplicate prevention. Keep sender latency below
Neon's blocking webhook timeout; test the real provider's failure behavior.

## Protected Vercel preview

Python 3.12, `app.main:app`, templates and static files are configured. Alembic is
never invoked from the deployed application or a build command. Migrate the chosen
branch explicitly before deployment. Secrets, tests and private backups are excluded
from deployment uploads/bundles. Keep `NEON_API_KEY` out of Vercel environment settings.
[Vercel FastAPI entrypoint documentation](https://vercel.com/docs/frameworks/backend/fastapi).

Keep Vercel Authentication on the preview. Webhook POSTs cannot pass an interactive
platform login. A domain-wide exception or an automation bypass URL can expose more
than the webhook, so do not use either as a purported path-only exception. Inspect
the account's current supported controls; if no suitably scoped route exception
exists, prepare a separate minimal webhook-only deployment using the same isolated
branch. That deployment must expose no scheduling, export, login, or general proxy
routes. Its URL/reachability still needs preparation and verification.
[Vercel protection bypass methods](https://vercel.com/docs/deployment-protection/methods-to-bypass-deployment-protection).

## Verification and release gates

Automated tests use a simulated provider and genuinely signed Ed25519 webhook
fixtures. They prove application behavior against the documented contract, not
Neon's hosted configuration or SMTP delivery. The scheduling workflow suite also
runs under simulated Neon sessions. Browser checks use temporary databases and
local TLS; mobile Chromium and WebKit remain separate from real Safari/device checks.

```sh
pytest -q
python tests/browser_smoke.py
python tests/browser_private_access.py
```

Before release, record live evidence for approved inbox delivery, denied app and
direct-provider requests, unapproved signup, link expiry/reuse, logout/revocation,
whitelist removal, actual cookie names/session fields, provider outages, sender
failures, email-origin navigation, mobile/Safari, and another device. Confirm
webhook coverage and unused auth providers on the actual branch. Disable auth/data
API access paths outside this app unless explicitly required and restricted.

The next cloud action is opening the existing Neon resource from Vercel and
checking Auth, then obtaining only non-secret project/branch identifiers and the Auth Base URL. Deployment, sender
setup and inbox proof remain pending. Verify current resource quotas/costs before
selecting upgrades; no paid resource has been requested.

Before production, ask whether to copy the existing local scheduling data. Create
a private database backup, test the migration/transfer on an isolated branch, and
compare people, availability, assignments and history counts/content. Do not delete
legacy accounts or scheduling records to change authentication.

Rollback: first protect the deployment at the platform and revoke affected provider
sessions; retain the last verified protected deployment. Restore a private database
backup to an isolated branch and verify it before changing production connection
settings. Migration downgrade refuses to delete auth receipts. A legacy password
deployment must remain behind platform protection. Obtain production authorization
after the preview and live checks pass; changing account settings alone is not a release.
