# AI-guided implementation: private access with magic links

## Start here

Give an AI with access to this repository the following prompt:

> Read docs/plans/private-access.md and follow it as the implementation runbook. Implement the feature, keep this file's progress log current, and guide me through account setup, credentials, and any dashboard actions you cannot perform. Start by inspecting the current code and preparing the integration prototype. Give me only the next small batch of manual steps, with the exact URL, setting, expected result, and what I should report back. Continue independent implementation while waiting. Use thiago.rivas0021@gmail.com as the initial approved email; my mother's address will come later. Preserve existing work and scheduling data. Prepare and test a protected preview before production release.

This file is a plan, not evidence that cloud setup or release is complete. Implementation began on 2026-10-09 at the user's request. See the progress log for completed local work and outstanding live checks.

## Agreed result

Keep the existing FastAPI, SQLAlchemy, PostgreSQL, Jinja2, and Spanish interface. Host the app on Vercel and the database on Neon's free plan. Use Neon Managed Better Auth for magic links and sessions; do not introduce Supabase or rewrite the app into another framework.

Users enter their email, receive a single-use link, click it, and use the app. They need only their email inbox, not a Vercel or Neon account. Both approved users have the same app permissions.

Only whitelisted addresses may receive login links or access app data, including through direct calls to the auth provider. Initially allow only `thiago.rivas0021@gmail.com`. The mother's email is pending; do not invent an address, allow an entire domain, or block progress on her address.

Keep setup and maintenance small: one configured email list, no user-management screen, no custom token cryptography. Free database/auth plans have quotas; email delivery and a sender domain may involve separate costs. Verify current terms before proposing any paid resource.

## How the AI should work with the user

- Own repository changes, provider integration, migrations, scripts, automated tests, documentation, deployment preparation, and verification. Do not hand coding or terminal troubleshooting back to the user.
- Guide the user only through actions requiring their identity, MFA, account permissions, credentials, inbox, preferences, or unavailable dashboard access. Use connected tools for authorized actions when available.
- Give at most three closely related manual steps at a time. State the link to open, fields to enter, expected result, and the non-secret information to report. If labels differ, inspect current official documentation and ask for the visible labels rather than guessing.
- Never request credentials in chat. First prepare a gitignored local environment file or identify the provider's secret-entry screen. Tell the user exactly where to paste each secret. Do not print secrets, cookies, full login links, or credential-bearing webhook bodies.
- Treat account setup, domain purchases, paid upgrades, and production changes according to existing user authorization. Prepare a concrete tested result before requesting any missing production authorization; do not repeat permission requests already answered.
- Continue useful work while a manual step is pending. Live integration and release checks remain pending until actually performed; mocked tests do not prove cloud delivery.
- Read and preserve concurrent/local changes. Re-read the relevant code before each implementation phase; this repository is being actively edited.
- Record completed work, validation evidence, current blockers, and the next action below. Resume from that record instead of restarting or asking for supplied information again.
- If Neon cannot satisfy the requirements without substantial extra infrastructure or a framework rewrite, demonstrate the specific limitation and present a concrete alternative before changing the agreed architecture.

## Current state and inputs

Inspected on 2026-10-09; recheck before implementing.

| Item | Current state |
| --- | --- |
| Approved email | `thiago.rivas0021@gmail.com` |
| Mother's email | Pending; not needed for the first release |
| Existing app login | Local password mode preserved; Neon prototype uses email links and disables `/setup`/password access |
| Existing security | Central access guard revalidates live provider sessions/whitelist; CSRF/origin checks retained |
| Database migration system | Alembic already exists; reuse it |
| Neon project/auth | `neon-gestion-guardias`, project `plain-lab-97919633`, Free, AWS US East 1, connected to `gestion-guardias`; main selected, only Magic Link enabled and registration off according to user. Current expiry 5 minutes, target 15. Auth Base URL saved; live JWKS/anonymous-session probe passed |
| Email sender/domain | User reported neither SMTP credentials nor a sender domain; Gmail app-password availability remains to be checked |
| Vercel project/production URL | `https://gestion-guardias-two.vercel.app`; anonymous `/`, `/login`, `/setup`, `/health`, `/personas` all HTTP 500 / FUNCTION_INVOCATION_FAILED on 2026-10-10. Local changes are unpublished; deployed revision/environment remain unresolved |
| Existing data transfer | Ask whether to copy local scheduling data before release |
| Magic-link implementation | Local prototype implemented and tested; real branch API/session/email behavior still pending |

Relevant starting files: `app/api/auth.py`, `app/security.py`, `app/main.py`, `app/web.py`, `app/templates/auth.html`, `app/templates/base.html`, `app/db/database.py`, `migrations/`, `.env.example`, `README.md`, and `tests/`.

Do not recreate the old startup schema migration: current code already uses Alembic. Existing password accounts must not remain an alternative route around the approved-email policy in production. Preserve their stored data during migration; do not delete records just to switch login methods.

## Phase 1 — inspect and prepare

**AI implements**

1. Inspect current instructions, git changes, auth, forms, exports, migrations, and tests. Establish the existing test baseline and distinguish pre-existing failures from new ones.
2. Prepare proposed configuration and a gitignored local secret file; verify ignore rules before the user enters anything. Retain existing settings and credentials.
3. Prepare the smallest FastAPI auth integration prototype and isolated tests. Verify current Neon APIs for link requests, verification, sessions, revocation, and signed delivery webhooks from primary documentation.
4. Keep production access denied when the required auth configuration is missing. No public first-user setup flow, localhost database fallback, or randomly changing session secret in deployment.

**User does, only if not already complete**

1. Open [Neon Console](https://console.neon.tech), sign in, and create `gestion-guardias` on the Free plan.
2. Enable managed Auth. In its Magic Link settings, enable links, set expiration to 15 minutes, and turn Allow New User Registration off.
3. Report the project/branch identifiers and Auth Base URL. These are not credentials. Paste the database connection string into the local secret file prepared by the AI, not into chat.

**Done when:** the project/auth settings are confirmed, the local secret location is ready, and the prototype can reach the selected `main` branch services.

## Phase 2 — set up email delivery

**AI guides and implements**

Ask one short setup question: "Do you already have SMTP credentials or a domain you can send email from?"

- If suitable SMTP already exists, use it. Give the exact host, port, username, password, sender-address, and TLS fields to configure.
- If a domain exists but no sender does, guide one transactional-email provider setup, including its current free limits and DNS verification. Prefer a simple supported provider rather than offering a long comparison.
- If neither exists, identify and explain one supported path without silently requiring a domain purchase. An existing mailbox's supported SMTP/app-password option can be considered if available; otherwise explain the domain/provider requirement and its concrete cost before asking for a choice. Never request the user's normal mailbox password or weaken MFA.

The user signs in to the sender, verifies domain ownership if required, and enters credentials in the prepared secret location. The AI handles SMTP/API integration and a simple Spanish email template, and asks the user only to confirm receipt of a test email.

Implement Neon's signed `send.magic_link` delivery webhook. Subscribing replaces Neon's default delivery for that event. Verify the signature and timestamp, handle retries idempotently using shared storage, check the current recipient whitelist, and send only approved sign-in links. Do not accept arbitrary URLs or recipients from an unverified request.

Neon's shared sender is intended for development. Custom SMTP configured directly in Neon does not itself enforce this app's whitelist; the delivery webhook remains necessary unless live evidence proves an equally restrictive provider control. Do not configure two competing delivery paths.

**Done when:** a legitimate webhook reaches the sender, an unapproved recipient causes no email send, and delivery failures cannot grant access.

## Phase 3 — prove the complete login flow

**AI implements**

1. Provision the initial approved Neon auth user through an administrative action/script. Do not mark arbitrary identities verified as a shortcut; first successful magic-link use must prove inbox access. Keep admin credentials out of deployed application runtime where possible.
2. Disable public magic-link signup and other unused public signup/sign-in methods. Confirm direct auth API calls cannot create an unapproved user or bypass delivery restrictions.
3. Prove same-origin auth and cookies in the server-rendered app. If a proxy is needed, limit it to specific auth operations and a fixed upstream, preserve multiple cookie headers, and configure cookie scope and trusted redirects explicitly. Do not add React/Next.js solely for authentication.
4. Validate the live provider session, verified identity, and current whitelist. Use secure HttpOnly cookies in production with a SameSite policy tested for an email-origin navigation. Never trust an email supplied by a form or unsigned browser cookie.
5. Verify logout/revocation, link expiry and reuse, mobile/Safari behavior, and an email opened on a different device. Aim for a seven-day maximum session lifetime if supported; document the actual supported setting.

**User does**

Open the genuine login email and confirm successful access on their usual device. The AI should not ask the user to paste the link/token into chat.

**Done when:** the approved inbox logs in through the real provider and both expired/reused links and unapproved users fail. If this phase reveals an architectural limitation, resolve it before broad implementation.

## Phase 4 — finish app integration

**AI implements**

- Adapt the existing Spanish login template to an email input, send-link action, generic check-email confirmation, resend cooldown, and expired-link recovery.
- Use the same response for approved and unapproved emails: "Si el correo tiene acceso, recibirás un enlace."
- Update the existing central access guard for every page, write route, export, and future app route. Check the current whitelist on every protected request so removal blocks an existing session on its next request.
- Redirect unauthenticated page navigation to login; reject unauthorized writes before accessing/changing scheduling data.
- Disable the old production password login and first-user `/setup` path once magic-link login is verified. Preserve scheduling, history, and existing security behavior during the change.
- Retain/adapt CSRF and origin checks for login, logout, existing forms, and fetch requests. The provider callback and webhook use their respective verification mechanisms.
- Validate return URLs as local paths. Prevent public caching of private pages/auth responses.
- Rate-limit requests using shared storage, not function process memory. Avoid storing credentials in browser localStorage or logs.

Proposed new configuration names: `ALLOWED_EMAILS`, `NEON_AUTH_BASE_URL`, and `APP_BASE_URL`, plus documented sender settings. Keep `DATABASE_URL`, `SESSION_SECRET`, `COOKIE_SECURE`, and existing configuration where appropriate. Finalize exact names in code, `.env.example`, and README together. Never commit real values.

**Done when:** normal scheduling workflows work for approved users and every unauthorized access path is blocked.

## Phase 5 — prepare Vercel and data

**AI implements and prepares**

1. Configure SQLAlchemy/psycopg for Neon's pooled PostgreSQL URL with TLS. Use a direct connection for migration/backup operations when required; document the chosen URLs without exposing credentials.
2. Reuse and extend Alembic migrations without deleting scheduling/history data. Run migrations as an explicit setup/release operation, not from a request or every function startup.
3. Verify the Python version, FastAPI entry point, and template/static inclusion on Vercel. Ensure serverless starts and multiple instances share stable configuration.
4. Use `main` for the initial setup per the user's explicit 2026-10-10 instruction; keep database and auth configuration aligned to that branch. The earlier development-branch prerequisite is superseded.
5. Prepare exact CLI commands or dashboard fields for environment settings, user provisioning, migrations, provider callbacks/trusted origins, webhook configuration, and backups. The user should not have to invent commands.

**User does, only for unavailable account actions**

1. Sign in to [Vercel](https://vercel.com), connect the repository/account, and select the intended project. The AI prepares deployment configuration first.
2. Enter secrets in Vercel's environment settings when the AI cannot do so through authorized tools.
3. Confirm whether local scheduling data should be copied. The AI creates a private backup and validates any transfer.

Use a protected preview first. Webhook endpoints must be reachable by Neon while enforcing signature verification; account for Vercel preview protection explicitly. Do not remove all preview protection just to make a webhook work. Use a narrowly scoped supported exception or a separately reachable minimal integration test endpoint, and verify what becomes accessible.

**Done when:** the protected deployment uses the selected branch, actual emails work, and the user can review the feature.

## Phase 6 — test and release

**AI verifies**

Automated tests must cover:

- Anonymous page/export access and writes; rejected writes leave data unchanged.
- Approved and unapproved email requests through both app and provider paths.
- Tampered, stale, and replayed webhook requests; retries do not duplicate emails.
- Expired/reused links, tampered/expired sessions, provider outages, and sender failures.
- CSRF, hostile return URLs, logout/revocation, and whitelist removal with an existing session.
- Existing people, availability, calendar generation, editing, history, and exports.

Use isolated test data and maintained validation libraries. Run appropriate existing tests and browser checks, including mobile/Safari where available. Record any browser/provider checks the AI cannot perform and guide the user through those specific checks.

Before production, provide the tested preview, test results, selected resource plans/costs, data-transfer result, and protected rollback procedure. Obtain production authorization only if not already given; account setup alone is not authorization to publish an unfinished app.

For the live release, configure exact production origins and sender settings, apply migrations, provision approved users, and verify anonymous access is denied. Production uses app authentication; Vercel Authentication on the production URL would require the mother's Vercel account. Keep old deployments protected too. Removing a platform gate must happen only after app-level protection has passed verification.

**Done when:** the approved user can log in on the live app, strangers cannot access data or receive login links, and restoration/rollback instructions are documented.

## Phase 7 — add the mother's email later

When supplied, the AI adds the normalized exact address to the correct environment's whitelist, provisions that auth user, applies any required configuration redeployment, and tests delivery/access. Guide the user only through the inbox confirmation or unavailable dashboard action. No new signup screen or provider account is needed for the mother.

## Progress log

Update this table after meaningful progress. Record evidence without credentials.

| Phase | Status | Evidence / next action |
| --- | --- | --- |
| 1. Inspect and prepare | Prototype prepared; first live Auth probe passed | Inspected and preserved substantial concurrent/uncommitted work. Baseline: 16 passed, 1 skipped. Verified official provider contracts. Gitignored mode-0600 `.env.private-access` retains its secret; main Auth Base URL/project ID saved. Live JWKS returned keys and anonymous session returned null. User reports only Magic Link enabled, registration off, expiry 5 minutes; change to planned 15 minutes. Main branch ID/database credentials remain pending. |
| 2. Email delivery | Handler implemented; sender pending | Real Ed25519 signature fixtures verify raw body + bound timestamp, approved recipients, URL/expiry checks, shared delivery receipts, cooldown and duplicate prevention. User answered "Neither" for SMTP/domain. No email has been sent; next evaluate supported Gmail app-password option after account setup. |
| 3. Login prototype | Isolated tests passed; live proof pending | Fixed upstream operations, callback redemption, provider-backed verified identity, host-only Secure/HttpOnly/Lax cookies, app seven-day session cap, logout and recovery implemented. Chromium/WebKit HTTPS mobile tests passed with a simulated provider, including another browser context. Actual provider cookie/session contract, expiry/reuse and inbox navigation need live proof. |
| 4. App integration | Neon mode wired for prototype | Spanish email form and generic confirmation; per-request whitelist/session check; unauthorized writes/exports blocked before scheduling access; CSRF/origins/local return paths/no-store retained. Scheduling workflow tests run in local-password and simulated-Neon modes. Production config refuses password fallback. No cloud login cutover yet. |
| 5. Vercel/data | Deployment preparation complete; preview pending | Python 3.12/FastAPI entrypoint, bundle exclusions, pooled TLS URL handling, direct migration URL and explicit Alembic 0003 prepared. Local tooling supports configuration check, read-only probe, migration, approved-user provisioning and serving without access logs. No live migrations/transfer/deployment. Protected-preview webhook reachability needs a supported scoped control or a separate minimal webhook-only deployment. |
| 6. Tests/release | Local verification passed; release pending | Latest Python 3.12 suite: 87 passed, 1 skipped (PostgreSQL row-lock integration). Python 3.14 suite previously passed 74 tests before concurrent tests were added. Existing Chromium scheduling smoke passed; Chromium and WebKit mobile HTTPS auth checks passed with simulated provider. Live sender/provider, PostgreSQL concurrency, real Safari/device, costs, data-transfer decision, protected preview and production authorization remain pending. |
| 7. Mother's email | Waiting for address | Initial release can proceed with the owner's email |

Implementation details and prepared setup/rollback commands are in
[docs/private-access-setup.md](../private-access-setup.md). The user now reports
database creation and connection complete, and has opened the Neon Console.
The user explicitly chose `main` on 2026-10-10 and reports disabling every auth
method except Magic Link. Registration off is confirmed by the user; expiration
was corrected to 5 minutes. The Auth Base URL is saved and its read-only JWKS and
anonymous-session probes passed. Next change expiration to the planned 15 minutes
and obtain the deployment URL and remaining configuration. Request only
non-secret identifiers; enter credentials in
the private file or provider secret-entry screen. The user asked to be notified
when local preparation is ready; avoid sending more setup questions before that.

Setup resumed after the user said "Ok let's do it". The local Vercel CLI reports
logged out; no project is linked in this checkout and no cloud credential fields
are populated in `.env.private-access`. The installed Neon CLI has no default
configuration file. The user subsequently confirmed that Neon is already installed
in their Vercel project; do not ask them to install it again or create a duplicate.
No live branch configuration, credential access, or preview deployment is confirmed.
The user subsequently reported "I just deployed it". A pending question requests
only the normal deployment URL without tokens/query parameters. This checkout
still has no local Vercel project link, no populated cloud credential fields, and
substantial uncommitted work including the auth prototype; do not assume the
deployment contains this implementation. Next verify the deployed revision,
anonymous access and platform protection. Keep Vercel Authentication protecting
all deployments during setup until app-level protection has passed live checks.
The reported deployment does not establish working Neon auth, email delivery,
data transfer, or completion of the production-release gate.
The user reports "everything's ok" with their deployment. Their subsequent Storage
screenshot clarifies that Neon is available to the team but no database is connected
to this project. The listed `onboarding-db`, `neon-amethyst-basket` and
`neon-cinnabar-diamond` resources have unknown purposes; use a dedicated Free
resource for this app. Preserve the reported deployment state and avoid repeating
installation/deployment steps.
The deployment URL request remains unanswered, so remote verification is pending.
The user subsequently reports "done, and it's already connected" after the
dedicated database creation instructions. Record creation/connection as reported
complete and proceed to Auth configuration; do not repeat database creation.
The next screenshot confirms `neon-gestion-guardias` is Available on Free and
connected to `gestion-guardias`. The provider-console button is labeled **Open in
Neon**. The subsequent Neon Console screenshot identifies project
`plain-lab-97919633` in AWS US East 1 (N. Virginia), with only the default `main`
branch. The auth navigation label is **Better Auth** and the branch action is
**Create child branch**. Next create `private-access-dev` and inspect its Auth
status; development branch credentials and identifiers remain pending.
The user opened Better Auth on `main`: no users are listed; **Configure Auth** is
available. A banner states that anyone can sign up and restricted-signup support
is coming soon. Actual magic-link registration controls and signed whitelist
webhooks remain to be verified in configuration; do not assume restrictions have
been applied. Create the isolated development branch before changing Auth settings.
On 2026-10-10 the user explicitly instructed "let's do it on main". This supersedes
the preceding child-branch instructions: use the existing `main` branch and do
not ask the user to create `private-access-dev`. Next click **Configure Auth**
and inspect the available settings. Exact-email access and the requested magic-link
implementation remain the objective.
The user subsequently reports "disabled everything except for the magic link".
Record Magic Link as the sole enabled method according to the user, without
asking them to disable providers again. Confirm only the outstanding expiration
and new-registration options, then obtain the non-secret Auth Base URL for `main`.
At that point no live provider probe, approved-user provisioning or email send had occurred.
The user then supplied `main`'s Auth Base URL and corrected expiration to 5 minutes.
Saved the supplied URL and known project ID in the private file without printing
its contents. On 2026-10-10, the existing `NeonAuth` bridge's read-only probe
returned branch verification keys and HTTP 200/null for an anonymous session.
No credentials, auth users or emails were used; authenticated-session/callback,
delivery and deployment checks still remain. User confirmation applies to
registration off; 15-minute expiration is not configured yet.
The user supplied `https://gestion-guardias-two.vercel.app/`. Saved the normalized
origin locally and set COOKIE_SECURE=true without changing the remote environment.
Anonymous GETs to `/`, `/login`, `/setup`, `/health` and `/personas` returned HTTP
500 / FUNCTION_INVOCATION_FAILED; no functioning app login or access control is
established by those responses. The user pointed out that the changes have not
been pushed, correctly: all implementation and prior scheduling changes are
uncommitted on `t-rivas/auth-login-flow`. `git ls-remote --heads origin` shows only
`main` at `132b68f`. Re-ran Python 3.12 validation for a publication candidate:
87 passed, 1 skipped. Prepare a complete reviewable change set and resolve the
scope of publishing the earlier scheduling work alongside the auth implementation.
The complete publication candidate contains 72 paths; its review and patch are
saved privately under `.local-backups/private-access-publication/`. The user
explicitly approved committing and pushing that full tested app change set to
`t-rivas/auth-login-flow`. Stage only those reviewed paths, retain ignored secrets
and backups locally, and verify the branch publication. GitHub main integration
and the remote runtime configuration remain separate outstanding work.
Committed the reviewed 72-path app change set as `c4acd90` and pushed
`t-rivas/auth-login-flow`; verified GitHub's branch SHA matches the local commit.
GitHub main remains `132b68f`. Vercel attempted a preview build
(`dpl_F7SxJqFAx757bcz3a2ZBQ3z6eC6Q`) and failed: uv treated `pyproject.toml` as
the dependency manifest but it lacked a `[project]` table. Added metadata and
runtime pins matching requirements.txt, and generated uv.lock with the exact
builder uv version (0.10.11). Fresh locked Python 3.12 installation: 87 passed,
1 skipped. Manifest fix publication and subsequent build verification are next.
The user explicitly restricts investigation to their `7h146os-projects` team and
`gestion-guardias` project; always pass that scope and an explicit project or
deployment ID. Vercel CLI authenticated during inspection and now gives access
to this project's build logs. The computer-use helper could not run because
`Unable to determine Orca.app path from symlink: /usr/local/bin/orca`; no GUI
actions were performed. Scoped project inspection identifies
`prj_BSh43i1g68RoUwN9tS4mHlP5koMs`, FastAPI preset, and runtime variables from
Neon only. App origin, whitelist, session secret and secure-cookie variables are
missing. Automatic approval review rejected pulling the full production secret
payload to a local file, citing unapproved production credential copying and
its broad blast radius. No production credentials were downloaded; continue
with the manifest fix and scoped non-secret deployment checks. Credentials,
migrations, sender, user provisioning and authenticated login remain pending.

Browser verification caught and corrected a real form-origin regression:
`Referrer-Policy: no-referrer` caused browsers to post `Origin: null`. Normal pages
now use `same-origin`; token callbacks use `no-referrer`. Delivery receipts are
committed before SMTP and never resent after an uncertain acknowledgement or
crash; users request a fresh link after cooldown. These behaviors are documented
and require live provider/sender verification before release.

## Official references

Verify current documentation before cloud/API changes. Dashboard labels and plan limits can change.

- [Neon magic-link configuration](https://github.com/neondatabase/website/blob/main/content/docs/auth/guides/plugins/magic-link.md)
- [Neon signed webhooks and delivery replacement](https://github.com/neondatabase/website/blob/main/content/docs/auth/guides/webhooks.md)
- [Neon production email configuration](https://github.com/neondatabase/website/blob/main/content/docs/auth/production-checklist.md)
- [Neon managed-auth API and user administration](https://github.com/neondatabase/website/blob/main/content/docs/auth/guides/manage-auth-api.md)
- [Neon on Vercel](https://vercel.com/marketplace/neon/neon)
- [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi)
