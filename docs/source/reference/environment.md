# Environment variables

This page mirrors the runtime settings defined in `src/gatekeeper/config.py`.

## Application

| Variable | Default | Notes |
|---|---|---|
| `APP_NAME` | `Gatekeeper` | Branding/display name |
| `APP_URL` | `http://localhost:8000` | Public auth/backend URL |
| `FRONTEND_URL` | `http://localhost:4321` | Frontend URL |
| `SECRET_KEY` | required | 32+ chars |

## Database

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./gatekeeper.db` | SQLite or PostgreSQL DSN |

## Email

| Variable | Default | Notes |
|---|---|---|
| `EMAIL_PROVIDER` | `ses` | `ses` or `smtp` |
| `EMAIL_FROM_NAME` | `Gatekeeper` | Display name |
| `AWS_ACCESS_KEY_ID` | empty | SES only |
| `AWS_SECRET_ACCESS_KEY` | empty | SES only |
| `AWS_REGION` | `us-east-1` | SES only |
| `SES_FROM_EMAIL` | empty | SES sender |
| `SMTP_HOST` | empty | SMTP only |
| `SMTP_PORT` | `587` | SMTP only |
| `SMTP_USER` | empty | SMTP only |
| `SMTP_PASSWORD` | empty | SMTP only |
| `SMTP_FROM_EMAIL` | empty | SMTP sender |

## Auth and user policy

| Variable | Default | Notes |
|---|---|---|
| `ACCEPTED_DOMAINS` | empty | Comma-separated trusted domains |
| `OTP_EXPIRY_MINUTES` | `5` | OTP lifetime |
| `SESSION_EXPIRY_DAYS` | `30` | Session lifetime |
| `OTP_SEND_LIMIT_PER_EMAIL_IP` | `3` | Max OTP send attempts per email+IP within the auth failure window |
| `OTP_VERIFY_FAIL_LIMIT_PER_EMAIL_IP` | `8` | Max failed OTP verify attempts per email+IP within the auth failure window |
| `AUTH_FAILURE_WINDOW_MINUTES` | `15` | Rolling window used for OTP throttling and automatic IP bans |
| `AUTO_IP_BAN_FAILURE_THRESHOLD` | `10` | Failed auth attempts from one IP before an automatic temporary ban |
| `AUTO_IP_BAN_DURATION_HOURS` | `1` | Automatic IP ban duration |
| `COOKIE_DOMAIN` | unset | Use `.example.com` for sibling-subdomain SSO |
| `DEFAULT_APP_ACCESS` | `allow` | Behavior for unregistered apps: `allow` or `deny` |

## WebAuthn

| Variable | Default | Notes |
|---|---|---|
| `WEBAUTHN_RP_ID` | `localhost` | Must match public auth domain |
| `WEBAUTHN_RP_NAME` | `Gatekeeper` | Friendly display name |
| `WEBAUTHN_ORIGIN` | `http://localhost:4321` | Full origin |

## OAuth

| Variable | Default | Notes |
|---|---|---|
| `GOOGLE_CLIENT_ID` | empty | Enables Google when paired with secret |
| `GOOGLE_CLIENT_SECRET` | empty | Enables Google when paired with ID |
| `GITHUB_CLIENT_ID` | empty | Enables GitHub when paired with secret |
| `GITHUB_CLIENT_SECRET` | empty | Enables GitHub when paired with ID |

## Server

| Variable | Default | Notes |
|---|---|---|
| `SERVER_HOST` | `0.0.0.0` | Bind address |
| `SERVER_PORT` | `8000` | Listen port |
| `SERVER_RELOAD` | `true` | Development convenience; disable in production |
| `PUBLIC_API_DOCS` | `false` | Controls `/api/v1` Swagger UI and `/api/v1/openapi.json` |
| `TRUSTED_PROXY_IPS` | `127.0.0.1,::1` | Comma-separated proxy IPs or CIDRs allowed to supply forwarded client IP headers |

## Derived behavior

- `ACCEPTED_DOMAINS` is split into a normalized lowercase list on startup.
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` together enable Google sign-in.
- `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` together enable GitHub sign-in.
- `EMAIL_PROVIDER` determines whether Gatekeeper uses `SES_FROM_EMAIL` or `SMTP_FROM_EMAIL`.
- `PUBLIC_API_DOCS=false` makes `/` redirect to `/health` instead of the Swagger UI.
- `X-Forwarded-For` and `X-Real-IP` are only trusted when the immediate peer IP matches `TRUSTED_PROXY_IPS`.

For setup examples and deployment recommendations, see [Configuration](../getting-started/configuration.md).
