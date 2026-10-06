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
                     pagination, paystack, views/{history,funding,webhook,
                     dva_refresh,account_name}, urls
  notifications/     models, utils (in-app row + email; endpoints later)
  payments/          models (14 VTU tables, group, withdrawal, transfer,
                     webhook log), plans (GENERATED catalog), serializers
                     (DRF-shaped validation), vtpass client,
                     views/{airtime,data,cable,electricity,exam,customer,
                     group,internal,withdrawal,status,common},
                     webhook (VTpass transaction-update), urls
  bonus/             utils (referral-flag side effect + award stubs;
                     full app later)
templates/accounts/  Askama ports of accounts/templates/accounts/*.html
templates/notifications/  Askama port of default_notification.html
```

Each app keeps Django's file names (`models`/`serializers`/`views`/`urls`/…),
same table/column names (existing DB works untouched), and same
request/response shapes (existing frontend works untouched).

## Setup

```bash
# 1. Debug database: copy once from the Django backend
cp ../BlueSea-Mobile-backend/db.sqlite3 ./debug.sqlite3

# 2. Environment: copy ../BlueSea-Mobile-backend/.env to ./.env, then ensure:
#    DEBUG=True
#    SQLITE_URL=sqlite://debug.sqlite3?mode=rwc
#    SECRET_KEY=<same as Django, so tokens cross-verify>
#    PIN_RSA_PRIVATE_KEY=<same base64 PEM as Django>
#    EMAIL_BACKEND=console            # DEBUG default (log-only)
#    # prod: EMAIL_BACKEND=brevo + BREVO_API_KEY + EMAIL_HOST_USER sender

cargo run            # serves on :8000
```

## Docs & health

| Route | Purpose |
|---|---|
| `GET /health` | liveness |
| `GET /schema/` | raw OpenAPI JSON (like DRF `/schema/`) |
| `GET /docs/` | Swagger UI |
| `GET /redoc/` | Redoc |
| `WS /ws/wallet/`, `/ws/wallet/balance/` | live balance (`?token=<JWT>`, close `4401` unauthenticated) |

## Tests

```bash
cargo test wallet utils email   # fast: ledger, templates, Brevo payload
cargo test                      # full (PBKDF2 cases take ~1 min)
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

- Password-reset signed tokens are our own HMAC format (900s, single-use);
  Django-issued tokens are not accepted — full flow must run on one backend.
- PIN-reset OTP/token store is in-process memory (600s/300s TTLs), mirroring
  Django's cache usage.
- Wallet read-modify-write runs in one transaction, matching
  Django-on-SQLite semantics (`select_for_update` is a no-op there);
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
