# Private access: setup and verification

Preview inbox delivery and login are verified by the owner. Production is now
configured and published; owner inbox delivery and login are also verified.
The existing local password mode and scheduling data are preserved. Vercel and
`APP_ENV=preview`/`production` require Neon; missing configuration stops startup.
There is no deployed `/setup` or password fallback.

## Verified preview integration (2026-10-11)

- Neon CLI access was restored by the owner. Selected `main` branch:
  `br-curly-dust-b7h0t1tj`, project `plain-lab-97919633`.
- Magic Link is enabled, expiry is 15 minutes and public signup is disabled.
  The exact stable preview HTTPS origin is trusted; localhost is disabled.
  Email/password and phone login are disabled; the unused shared Google OAuth
  configuration was removed, with no user records deleted.
- The owner manually created the approved user. The live magic-link attempts
  subsequently verified the email through Neon; no manual verification shortcut
  was used.
- The replacement Gmail app password passed a real SMTP login (235), without
  sending a diagnostic email. Gmail credentials are saved as sensitive variables
  only for `t-rivas/auth-login-flow` preview. TLS uses SSL on port 465.
- A separate delivery-only preview was deployed in the same Vercel project.
  It registers only POST `/webhooks/neon-auth`. Its source bundle excludes the
  normal app entrypoint, scheduling routes, templates and static files.
  Tests prove all other routes return 404, unsigned messages cannot send, signed
  deliveries work and repeated events send once. Latest full suite: 99 passed,
  1 skipped. Mobile Chromium and WebKit simulated-provider browser checks pass.
- Webhook-only deployment `dpl_2SxVtudAFXD3j9VWsjz1Su7e1SW6` is READY at
  `https://gestion-guardias-pdey7vpuw-7h146os-projects.vercel.app`. Verified its
  route exclusions behind temporary access, revoked that access, then applied an
  exception only to this minimal deployment. Anonymous unsigned webhook is 400;
  login, people and home are 404. Full app preview remains platform protected.
- Neon webhook is enabled for `send.magic_link` and `user.before_create`, with
  timeout 10 seconds. No project-wide automation bypass or competing mail path.
- Protected app `dpl_HUHeGsvyjk61JSqsJzRBSjaUAYHS` (commit `5920944`) is READY.
  Hosted startup, canonical login redirect, disabled setup and anonymous write
  rejection pass; temporary verification access was revoked.
- Real request produced a signed webhook HTTP 200 and a `sent` receipt; owner
  confirmed inbox receipt. Neon now records the email as verified. Before the
  correction, the app callback redirected to the expired-link error. Live
  diagnostics show a provider redirect with no Set-Cookie headers; two provider
  sessions were created. Server redemption now omits callbackURL to select Better
  Auth's documented JSON response with session cookies, and still validates the
  resulting session before issuing app cookies. Correction commit `05755f4` is
  active on the stable preview as READY deployment `dpl_EWC2JgSTpSBEbgVoHpN9Wtbwqs43`.
  Source reference: [Better Auth server JSON redemption](https://github.com/better-auth/better-auth/blob/main/packages/better-auth/src/plugins/magic-link/index.ts).
  The owner confirmed successful login with a fresh emailed link after the
  correction: “Ahora si pude entrar”. Inbox delivery and authenticated callback
  are now verified live for the approved owner on the preview.
  Production was subsequently configured as recorded below.

## Setup history

- Owner: `thiago.rivas0021@gmail.com`; mother's address is still pending.
- User prefers creating Neon through the [Vercel Marketplace](https://vercel.com/marketplace/neon/neon).
- Screenshots confirm `neon-gestion-guardias` (`plain-lab-97919633`) is Available on Free, in AWS US East 1 (N. Virginia), and connected to `gestion-guardias`. On 2026-10-10 the user explicitly selected `main` for implementation and declined creating a development branch.
- User reports only Magic Link enabled on `main` and confirms Allow New User Registration is off. The user corrected the expiration to **5 minutes**, so the plan's 15-minute setting is still outstanding. Auth Base URL and project ID are saved in `.env.private-access`. A live read-only probe passed: branch JWKS returned keys and the anonymous session endpoint returned null. Approved-user provisioning, email delivery and authenticated callbacks remain pending.
- User initially reported having neither SMTP credentials nor a sender domain. On 2026-10-11 they confirmed Gmail's App passwords form is available for the approved owner's mailbox. Gmail SMTP host/port/TLS and sender fields are prepared locally; the app password was subsequently replaced and successfully authenticated, as recorded above.
- `.env.private-access` is gitignored and initially created with mode `0600`,
  its own stable session secret; Auth Base URL/project ID and database credentials are now populated. CLI administrative access and sender credentials were subsequently configured, as recorded above.
  Existing `.env` values were retained. Never paste credentials or login links in chat.
- Deployment URL: `https://gestion-guardias-two.vercel.app`. On 2026-10-10 anonymous GETs to `/`, `/login`, `/setup`, `/health` and `/personas` all returned HTTP 500 with `FUNCTION_INVOCATION_FAILED`; deployed startup/configuration is unresolved. The private setup file now uses the stable preview origin with `COOKIE_SECURE=true`.
- Published the complete reviewed app/auth/scheduling change set to `t-rivas/auth-login-flow` at `c4acd90`, then the manifest fix at `23604f3`. GitHub main remains at `132b68f`. Fixed the missing `[project]` table, added matching runtime dependency pins and `uv.lock`; a fresh Python 3.12 environment installed by Vercel's uv 0.10.11 passes 87 tests, with one PostgreSQL integration test skipped. Vercel reports the corrected preview deployment READY at `https://gestion-guardias-pty8ytvpb-7h146os-projects.vercel.app`; anonymous `/` and `/login` redirect to Vercel SSO. This verifies the build and platform protection, not app startup or authenticated login.
- User restricts cloud inspection to `gestion-guardias` in `7h146os-projects` and Git changes to its existing `t-rivas/gestion-guardias` repository. Vercel CLI is authenticated and scoped project inspection confirms FastAPI and project ID `prj_BSh43i1g68RoUwN9tS4mHlP5koMs`. Initial environment-name inspection showed Neon integration variables but no app origin/whitelist/session-secret/secure-cookie configuration. Automatic approval review rejected downloading the full production secret payload; no full environment download occurred.
- On 2026-10-11 the user explicitly approved retrieving only `DATABASE_URL` and `DATABASE_URL_UNPOOLED` into `.env.private-access` and running a read-only database check. This supersedes the earlier lack of authorization for these two credentials only; full environment downloads remain outside scope.
  Vercel's sensitive variables returned no readable values. The user supplied the pooled URL instead; it was saved without echoing it, and the matching direct URL was derived by removing the documented `-pooler` hostname suffix. Both connections passed a read-only check with client TLS enabled.
  Under the requested setup on Neon `main`, explicit Alembic migrations completed. A subsequent read-only check confirms revision `0004`, the expected public tables and role-availability constraints, and the initial planning revision `(1, 0)`. The public schema was empty before migration; no existing scheduling data was transferred. The approved email has no Neon Auth user yet.
  Automatic approval review initially rejected uploading nine prepared preview settings without explicit destination approval. The user subsequently approved the exact preview destination and authorized necessary implementation within this project. All nine settings were uploaded individually and metadata confirms only the `t-rivas/auth-login-flow` preview target: auth mode, environment, stable origin, whitelist, secure cookies, disabled SQL logging, Auth Base URL, session secret and database URL. Database/session credentials are sensitive variables. Production settings remain unchanged.
  A local TestClient startup smoke using that exact preview payload and main database passed: `/health` and `/login` returned 200, anonymous `/` and `/personas` returned 303, and `/setup` returned 404. This sent no email and did not test a hosted authenticated session.
  Rebuilt revision `23604f3` as preview `dpl_96bjS12FcNG5Vu8nhxQHsBRvbG6B`, READY at `https://gestion-guardias-43jp5wsp1-7h146os-projects.vercel.app`. Stable origin: `https://gestion-guardias-git-t-rivas-auth-login-flow-7h146os-projects.vercel.app`. Hosted checks using a temporary verification-only Vercel token passed: health/login 200, anonymous app pages 303, setup 404, anonymous write 401, unsigned webhook 400. The exact temporary token was revoked after these checks; platform authentication remains enabled. This does not establish webhook reachability from Neon or an authenticated login.
  The previously skipped PostgreSQL racing-save test was exercised directly against an isolated temporary schema on the selected main database and passed: the first writer commits and the racing stale writer receives 409. Removed only that task-created schema afterward; app tables were not modified. The earlier full-suite result remains 87 passed, 1 skipped, with this separate live PostgreSQL check now passing.
  Published the setup progress as `6ee0139`; GitHub's Vercel deployment check succeeded. Scoped Neon CLI branch lookup returned an authorization error, so administrative Auth configuration still requires restored CLI access or the user's console action. No other projects were queried.
  The exact Neon `main` branch identifier is now confirmed above.
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
password. Availability is confirmed and Gmail connection fields are prepared;
the replacement app password now authenticates, while live delivery remains pending. Use
`smtp.gmail.com`, port `465`, `ssl`, and the mailbox address for username/from.
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
routes. Run `python scripts/deploy_webhook.py` to create this source-only preview in the existing project, without deploying administrative keys. It does not change protection or Neon configuration. Verify the deployment before adding a domain/deployment exception; never reuse that exception on a full app deployment. Its URL/reachability still needs verification.
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

Webhook reachability, owner inbox delivery and the corrected authenticated callback are verified live. Complete the remaining release checks listed above before a production release. Verify current resource quotas/costs before
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

## Production configured and published (2026-10-11)

The owner authorized merging to main and configuring production. PR #1 merged
as `19f5894`; the stable production origin is
`https://gestion-guardias-two.vercel.app`. The same selected Neon main database
is retained. Production has the tested secure auth/SMTP settings, while
preview keeps its own origin. No local scheduling data is copied or deleted.

The shared delivery-only webhook uses `AUTH_EMAIL_ORIGINS` to admit exactly the
production and stable preview origins. It builds the emailed callback on the
verified event's approved origin, rejecting other origins and repeated callback
parameters. This setting belongs to the minimal webhook deployment, not a public
auth proxy or an application CSRF bypass. The default still accepts only its
configured `APP_BASE_URL`. Neon must trust both exact HTTPS app origins.


PR #2 merged the shared-origin delivery change as `9893197`. Full test suite:
112 passed, 1 skipped (the PostgreSQL race test was previously verified separately).
Production deployment `dpl_HsjViStvazELQKdvsMMbfjdQS2Yj` is READY at the stable
production origin. Hosted anonymous checks passed: health/login 200, private
pages 303 to login, exports/writes 401, disabled setup 404, wrong-origin login
POST 403, unsigned webhook POST 400. A fresh login response sets the session
cookie with Secure, HttpOnly and SameSite=Lax. No email was sent by these probes.
The owner confirmed a fresh production email arrived and successfully opened
an authenticated app session: “Recibí el correo y pude entrar”. This verifies
the real inbox/callback flow on the production origin as well as the preview.

The shared delivery-only deployment is now `dpl_5g8rh98rqD7SJV7KjMENZuLDFa1G`,
`https://gestion-guardias-o2w72yshr-7h146os-projects.vercel.app`. Its temporary
verification token was revoked, its public exception applies only to this minimal
deployment, and anonymous route/signature checks passed (other app routes 404,
unsigned webhook 400). Neon now targets it for both events with timeout 10.
The old delivery-only deployment's public exception was revoked. The full app
preview remains platform protected. Neon trusts the exact production and preview
origins, with localhost disabled. No project-wide bypass was introduced.
