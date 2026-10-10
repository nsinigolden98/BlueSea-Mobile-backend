# BlueSea Mobile Backend (Rust/Axum port)

Rust port of [BlueSea-Mobile-backend](../BlueSea-Mobile-backend) (Django 5 + DRF),
rebuilt one Django app at a time on branch `rust-main`. Local-only until all
ports are tested — **not pushed, not merged**.

## Stack

Axum 0.8 + Tokio · `sqlx` (SQLite in DEBUG, Postgres in prod) · `jsonwebtoken`
· Django-compatible PBKDF2 hashing · RSA-OAEP-SHA256 PIN/BVN decrypt · `reqwest`
· Askama email templates · Brevo transactional email in prod · utoipa
Swagger/Redoc.

## Layout (mirrors Django)

```
src/
  main.rs            manage.py / ASGI entry
  settings.rs        bluesea_mobile/settings.py  (Config::from_env)
  urls.rs            bluesea_mobile/urls.py      (mounts each app)
  docs.rs            drf-spectacular config      (/schema/ /docs/ /redoc/)
  state.rs           shared AppState (db, config, http, wallet_hub)
  error.rs           {"message", "state": false} error envelope
  time.rs            microsecond-truncated timestamps (Django storage format)
  email.rs           mail transport (console in DEBUG, Brevo in prod)
  auth/              jwt.rs, password.rs (PBKDF2), extractor.rs (auth_user)
  accounts/          models, serializers, views/{auth,social,pin,lookup},
                     urls, crypto, pin_security, social_auth, utils
  wallet/            models (credit/debit), serializers, views, consumers,
                     urls, routing, hub (balance pushes)
  transactions/      models (WalletTransaction, FundWallet), serializers,
                     pagination, nomba_gateway (nomba-rs async),
                     views/{history}, nomba_views (funding, DVA, webhook), urls
  notifications/     models, utils (in-app row + email; endpoints later)
  payments/          models (purchase tables, betting, group, withdrawal,
                     transfer, webhook log), serializers (DRF-shaped validation),
                     vtpass client (exams only — WAEC/JAMB stay on VTpass),
                     views/{airtime,data,cable,electricity (Nomba),
                     exam (VTpass), customer (Nomba lookups), betting
                     (fund-only via Nomba), group (Nomba; exams on VTpass),
                     internal,withdrawal (Nomba),status,common},
                     webhook (VTpass transaction-update, exams), urls
  accounts/          + kyc.rs (tier evidence: NIN/BVN RSA-encrypted at rest,
                     address, utility-bill image under MEDIA_ROOT/kyc/),
                     tier.rs (T0 no-phone · T1 phone · T2 +NIN · T3 +BVN ·
                     T4 +address+bill; cumulative in/out caps T0/T1 ₦100k,
                     T2 ₦1M, T3 ₦5M, T4 unlimited; over-cap external inflow
                     freezes the account, admin-only unfreeze at
                     /admin/api/accounts.Profile/{id}/unfreeze/)
  plans_cache/       startup Nomba plans cache (data x4 + cable x4) +
                     `/ws/plans/` websocket (keys: mtn, airtel, glo, 9mobile,
                     dstv, gotv, showmax, startimes; JWT like wallet socket)
  bonus/             utils (referral-flag side effect + award stubs;
                     full app later)
   support/           tickets, messages, attachments, admin views, live chat
   broadcast/         superuser mass mail + in-app fan-out (Tokio task
                      replaces Celery)
   market_place/      vendors/events/tickets/scanning/withdrawals
                      (Tokio tasks replace Celery; `qrcode` renders QR PNGs)
templates/accounts/  Askama ports of accounts/templates/accounts/*.html
templates/notifications/  Askama port of default_notification.html
```

Each app keeps Django's file names (`models`/`serializers`/`views`/`urls`/…),
same table/column names (existing DB works untouched), and same
request/response shapes (existing frontend works untouched).

## Setup (Postgres only)

```bash
# 1. Database: a Postgres. The app runs sqlx migrations on boot
#    (./migrations — baseline dump of the Django-migrated schema plus
#    incremental files), so a fresh database needs no manual step:
#    point DATABASE_URL at it and start the app.
#    Local scratch DB:
#    createdb -h localhost -U postgres bluesea
#    (then `cargo run` migrates it automatically)
#
#    New schema change workflow:
#      sqlx migrate add <name>   # writes migrations/<timestamp>_<name>.sql
#      # ... write the up-migration SQL, update the FromRow struct(s),
#      # ... and the fixture DDL in src/db.rs test_support ...
#      sqlx migrate run          # apply locally (or just `cargo run`)
#    Tests carry their own DDL (isolated scratch DBs per test), so the
#    fixture DDL in src/db.rs must move together with every migration.

# 2. Environment: ./.env holds every setting — there are no silent
#    defaults. A missing var panics at boot naming it; an explicit
#    DATABASE_URL wins, otherwise it is composed from the DATABASE_*
#    parts (same construction as docker-compose):
#    DEBUG=True
#    DATABASE_URL=postgres://bluesea:password@127.0.0.1:5432/bluesea_test
#    (plus SECRET_KEY, PIN_RSA_PRIVATE_KEY, SITE_URL, MEDIA_ROOT,
#    EMAIL_*, VTPASS_*, NOMBA_*, GOOGLE_*, APPLE_CLIENT_ID,
#    CORS_ALLOWED_ORIGINS / CORS_ALLOW_ALL_ORIGINS, SECURE_SSL_REDIRECT —
#    see the full variable list under "Deploy" below)
# NOTE: .env is parsed literally (no $VAR expansion), like Django.
# Do NOT switch the loader to the dotenvy crate: it expands `$...`,
# which silently rewrote SECRET_KEY (it contained a literal `$gvk`) and
# broke every HMAC/JWT cross-check (verified by probe 2026-10-10;
# key since rotated to alphanumeric-only).

cargo run            # serves on :8000 (migrates + enforces env on boot)
```

## Docs & health

| Route | Purpose |
|---|---|
| `GET /health` | liveness |
| `GET /schema/` | raw OpenAPI JSON (like DRF `/schema/`) |
| `GET /docs/` | Swagger UI |
| `GET /redoc/` | Redoc |
| `WS /ws/wallet/`, `/ws/wallet/balance/` | live balance (`?token=<JWT>`, close `4401` unauthenticated) |

## Admin panel

Staff-only React + TypeScript panel (Vite) served by the backend at
`/admin`, API under `/admin/api/*` (full model CRUD driven by a
`GET /admin/api/models/` registry, plus vendor approve/reject).

```bash
cd admin-panel && npm install && npm run build   # outputs admin-panel/dist/
```

Backend: `src/admin/` mirrors the app layout — `mod.rs` holds the staff
gate, generic CRUD executor, registry/dashboard, and the `/admin` SPA
serving; each `admin/<app>.rs` registers that app's models (column types
generated from the live Postgres schema). The Docker image builds the
panel (`node` stage) and serves it; local dev uses the Vite proxy
(`npm run dev`, `/admin/api` → `:8000`).

## Nomba

Wallet funding, dedicated virtual accounts, and bank withdrawals over the
Nomba rail, via the async `nomba-rs` SDK (same crate family as this
project). Mirrors `transactions/nomba_views.py`,
`transactions/nomba_gateway.py`, and `payments/nomba_views.py`.

| Route | Purpose |
|---|---|
| `POST /transactions/nomba/fund-wallet/` | hosted-checkout funding (min ₦100, DRF validation shapes) |
| `POST /transactions/nomba/account-name/` | bank account lookup |
| `POST /transactions/nomba/dva/assign/` | dedicated virtual account (idempotent) |
| `POST /transactions/nomba/dva/confirm/` | reconfirm by `sessionId` |
| `POST /transactions/nomba/webhook/` | public; `payment_success/failed`, `payout_success/refund` |
| `POST /payments/withdrawal/nomba/` | bank withdrawal (min ₦500, PIN, DVA routing) |

Setup:

```bash
# .env
NOMBA_CLIENT_ID=...
NOMBA_ACCOUNT_ID=...
NOMBA_SECRET_KEY=...
NOMBA_SIGNATURE_KEY=...   # webhook HMAC key (nomba-signature/nomba-timestamp)
# NOMBA_SANDBOX=1         # defaults to DEBUG, like Django's sandbox=NOMBA_DEBUG

# Database table (sqlx-owned schema, auto-migrated on boot):
# `accounts_nombadedicatedaccount` ships in the baseline migration.
```

Register `https://<SITE_URL>/transactions/nomba/webhook/` as the Nomba
webhook URL. Checkout funding credits on `payment_success` (idempotent on
the order reference); DVA inflows credit by destination account number;
payout refunds re-credit via `REV-<reference>` (idempotent); withdrawal
rows carry `provider="nomba"` so Paystack records are never touched.

## Tests

```bash
# DATABASE_URL comes from .env (exported value still wins).
# Each test gets an isolated scratch database; real tables are never touched.
cargo test
```

Live flows (signup → verify → login → PIN → reset → logout, wallet
REST + WS) are exercised against the running server with throwaway users
that are cleaned up afterwards.

## Email

Askama templates in `templates/accounts/` render **byte-identical** HTML to
Django (verified by diffing against Django's own renderer; only deliberate
difference: the footer year is the real year, Django hardcodes 2025).
`EMAIL_BACKEND=console` logs in DEBUG; `brevo` posts to
`https://api.brevo.com/v3/smtp/email` in prod. Missing `BREVO_API_KEY`
fails sends so handlers return 500, exactly like Django's send failure.

## Notes / deliberate divergences

- CORS mirrors Django (`CORS_ALLOW_ALL_ORIGINS = DEBUG`, allowlist from
  `CORS_ALLOWED_ORIGINS` via `tower_http::cors::CorsLayer`; methods match
  Django's `CORS_ALLOW_METHODS`, headers are `Any`). Env is read with
  `std::env` over a literal `.env` parser — never the `dotenvy` crate.
- SSL mirrors Django (`SECURE_SSL_REDIRECT` + `X-Forwarded-Proto` trust):
  plain-http hits get a 301 to `https://` unless the proxy header says
  `https` (nginx sets it; the Docker healthcheck sends it). Django's
  secure-cookie flags have no equivalent — the API is stateless Bearer
  JWT, it sets no cookies — and CSRF middleware is likewise N/A.
- Nomba runs on the async `nomba-rs` SDK: `create_order` takes a
  `redirectUrl` the Django call omits, so `SITE_URL` is sent (the customer
  email is passed as both email and name, per Nomba's checkout docs). The
  `accounts_nombadedicatedaccount` table ships in the sqlx baseline
  migration; fresh databases get it automatically on boot.
- Password-reset signed tokens are our own HMAC format (900s, single-use);
  Django-issued tokens are not accepted — full flow must run on one backend.
- PIN-reset OTP/token store is in-process memory (600s/300s TTLs), mirroring
  Django's cache usage.
- Wallet read-modify-write runs in one transaction, matching
  Django semantics without row locking (`select_for_update` not ported);
  add `FOR UPDATE` when the prod pool moves to Postgres.
- `pin_reset_success.html` exists in Django but is unreferenced; copied
  over unused for completeness.
- Payments mirrors Django's quirks exactly: DSTV debits with a `showmax`
  description, ShowMax never sends its notification (Django `KeyError`),
  group splits use full decimal precision (Django `₦1000/3`), duplicate
  checkout webhooks 404, and `updated_at` echoes `completed_at` on the
  internal-transfer status view.
- Django's payments celery tasks (`call_vtpass_task`,
  `call_group_vtpass_task`) and `process_payment` are never called — the
  views hit VTpass synchronously, so no worker is ported.

## Deploy (VPS cutover: Django stops, Rust starts)

`Dockerfile` (multi-stage release build), `docker-compose.yml` (complete
stack: `app` + `db` + `nginx` + `certbot`), `nginx.conf`, single `.env`
file (never committed). No docker daemon is needed locally; build on VPS.

```bash
# .env (only env file; keep dev and prod values apart — prod needs
# DEBUG=False, the VPS DATABASE_URL, SITE_URL=https://..., brevo keys):
DEBUG=False
DATABASE_NAME=bluesea_mobile
DATABASE_USER=bluesea_user
DATABASE_PASSWORD=...
SECRET_KEY=<same as Django, so tokens cross-verify>
SITE_URL=https://api.blueseamobile.com
MEDIA_ROOT=/app/media
APPLE_CLIENT_ID=...
CORS_ALLOWED_ORIGINS=https://blueseamobile.com,https://www.blueseamobile.com
# CORS_ALLOW_ALL_ORIGINS=True   # dev only; defaults to DEBUG (Django parity)
SECURE_SSL_REDIRECT=True        # Django parity (http→https 301); 0 disables
PIN_RSA_PRIVATE_KEY=<same base64 PEM as Django>
EMAIL_BACKEND=brevo
BREVO_API_KEY=...
EMAIL_HOST_USER=noreply@bluesea.com
VTPASS_BASE_URL=https://vtpass.com/api
VTPASS_API_KEY=...
VTPASS_SECRET_KEY=...
VTPASS_PUBLIC_KEY=...
NOMBA_CLIENT_ID=...
NOMBA_ACCOUNT_ID=...
NOMBA_SECRET_KEY=...
NOMBA_SIGNATURE_KEY=...
# NOMBA_SANDBOX=1   # defaults to DEBUG (Django uses sandbox=NOMBA_DEBUG)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
APPLE_CLIENT_ID=...

# fresh database: nothing to do — the app runs sqlx migrations on boot
# (./migrations). Existing Django-migrated databases were marked with the
# baseline row in _sqlx_migrations at cutover, so boot is a no-op for them.

docker compose up -d --build db
docker compose up -d nginx          # serve HTTP first for ACME
docker compose run --rm certbot certonly --webroot -w /var/www/certbot \
  -d api.blueseamobile.com --email you@example.com --agree-tos --no-eff-email
docker compose up -d --build        # app + nginx + renew loop
curl https://api.blueseamobile.com/health
```

- Cutover: stop the Django compose project on the VPS, then start this
  stack. Rollback is the reverse (Django compose back up).
- Single `app` replica: set `AUTOTOPUP_SCHEDULER=0` and
  `MARKETPLACE_SCHEDULER=0` on any extra replicas.
- Backups: `pg_dump $DATABASE_URL | gzip > backup.sql.gz` on a cron.
- Schema history: Django migrations are retired. The single baseline file
  `migrations/20261010000000_baseline.sql` absorbed the full Django-migrated
  schema (so the old `payments.0007` fake-apply quirk is gone); new changes
  are incremental `sqlx migrate add` files run automatically on boot.
