# Configuration

Gatekeeper is configured through environment variables loaded from `.env`.

## Minimum working config

```bash
SECRET_KEY="$(openssl rand -hex 32)"
APP_NAME="Gatekeeper"
APP_URL="https://auth.example.com"
FRONTEND_URL="https://auth.example.com"
DATABASE_URL="sqlite+aiosqlite:///./data/gatekeeper.db"

EMAIL_PROVIDER="smtp"
SMTP_HOST="smtp.example.com"
SMTP_PORT=587
SMTP_USER="smtp-user"
SMTP_PASSWORD="smtp-password"
SMTP_FROM_EMAIL="auth@example.com"

WEBAUTHN_RP_ID="auth.example.com"
WEBAUTHN_RP_NAME="Gatekeeper"
WEBAUTHN_ORIGIN="https://auth.example.com"
```

## Core settings

### `SECRET_KEY`

Required. Must be at least 32 characters.

```bash
SECRET_KEY="$(openssl rand -hex 32)"
```

### `APP_URL`

Public URL for the Gatekeeper backend/auth host.

```bash
APP_URL="https://auth.example.com"
```

### `FRONTEND_URL`

Public URL for the frontend. In most deployments it matches `APP_URL`.

```bash
FRONTEND_URL="https://auth.example.com"
```

### `DATABASE_URL`

SQLite is the default/simple option. PostgreSQL is appropriate if you need an external database.

```bash
DATABASE_URL="sqlite+aiosqlite:///./data/gatekeeper.db"
DATABASE_URL="postgresql+asyncpg://user:pass@db.example.com/gatekeeper"
```

## Email delivery

Gatekeeper uses email for OTP sign-in and admin notifications.

### SMTP

```bash
EMAIL_PROVIDER="smtp"
SMTP_HOST="smtp.example.com"
SMTP_PORT=587
SMTP_USER="smtp-user"
SMTP_PASSWORD="smtp-password"
SMTP_FROM_EMAIL="auth@example.com"
EMAIL_FROM_NAME="Gatekeeper"
```

### AWS SES

```bash
EMAIL_PROVIDER="ses"
AWS_ACCESS_KEY_ID="AKIA..."
AWS_SECRET_ACCESS_KEY="..."
AWS_REGION="us-east-1"
SES_FROM_EMAIL="auth@example.com"
EMAIL_FROM_NAME="Gatekeeper"
```

## User approval and access defaults

### `ACCEPTED_DOMAINS`

Comma-separated list of domains that should be treated as internal.

```bash
ACCEPTED_DOMAINS="example.com,subsidiary.example"
```

Behavior:

- users from accepted domains are auto-approved
- accepted-domain users are considered internal
- internal users get broad app access behavior without needing per-app grants

### `DEFAULT_APP_ACCESS`

Controls behavior when nginx asks for an app slug that is not registered in Gatekeeper.

```bash
DEFAULT_APP_ACCESS="allow"
DEFAULT_APP_ACCESS="deny"
```

Use `deny` if you want all protected apps to be explicitly registered.

## Sessions and cross-subdomain SSO

### `COOKIE_DOMAIN`

Required for SSO across multiple subdomains.

```bash
COOKIE_DOMAIN=".example.com"
```

If you only use the auth host itself, you can leave it unset.

### `SESSION_EXPIRY_DAYS`

```bash
SESSION_EXPIRY_DAYS=30
```

## OTP settings

### `OTP_EXPIRY_MINUTES`

```bash
OTP_EXPIRY_MINUTES=5
```

## WebAuthn / passkeys

These must match the public auth host users visit.

```bash
WEBAUTHN_RP_ID="auth.example.com"
WEBAUTHN_RP_NAME="Gatekeeper"
WEBAUTHN_ORIGIN="https://auth.example.com"
```

## OAuth providers

### Google

```bash
GOOGLE_CLIENT_ID="..."
GOOGLE_CLIENT_SECRET="..."
```

### GitHub

```bash
GITHUB_CLIENT_ID="..."
GITHUB_CLIENT_SECRET="..."
```

If both values for a provider are present, that provider is enabled on the sign-in page.

## Server settings

```bash
SERVER_HOST="0.0.0.0"
SERVER_PORT=8000
SERVER_RELOAD=false
```

In production, run without reload and usually behind nginx.

## Recommended production notes

- Use a dedicated auth hostname such as `auth.example.com`.
- Set `COOKIE_DOMAIN=.example.com` if apps live on sibling subdomains.
- Configure nginx to send `X-Robots-Tag: noindex, nofollow, noarchive` on the auth host and protected internal apps.
- Rebuild the frontend when deploying so `robots.txt` and current static assets are published.

## Full variable list

| Variable | Default |
|---|---|
| `APP_NAME` | `Gatekeeper` |
| `APP_URL` | `http://localhost:8000` |
| `FRONTEND_URL` | `http://localhost:4321` |
| `SECRET_KEY` | required |
| `DATABASE_URL` | `sqlite+aiosqlite:///./gatekeeper.db` |
| `EMAIL_PROVIDER` | `ses` |
| `EMAIL_FROM_NAME` | `Gatekeeper` |
| `AWS_ACCESS_KEY_ID` | empty |
| `AWS_SECRET_ACCESS_KEY` | empty |
| `AWS_REGION` | `us-east-1` |
| `SES_FROM_EMAIL` | empty |
| `SMTP_HOST` | empty |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | empty |
| `SMTP_PASSWORD` | empty |
| `SMTP_FROM_EMAIL` | empty |
| `ACCEPTED_DOMAINS` | empty |
| `OTP_EXPIRY_MINUTES` | `5` |
| `SESSION_EXPIRY_DAYS` | `30` |
| `COOKIE_DOMAIN` | unset |
| `DEFAULT_APP_ACCESS` | `allow` |
| `WEBAUTHN_RP_ID` | `localhost` |
| `WEBAUTHN_RP_NAME` | `Gatekeeper` |
| `WEBAUTHN_ORIGIN` | `http://localhost:4321` |
| `GOOGLE_CLIENT_ID` | empty |
| `GOOGLE_CLIENT_SECRET` | empty |
| `GITHUB_CLIENT_ID` | empty |
| `GITHUB_CLIENT_SECRET` | empty |
| `SERVER_HOST` | `0.0.0.0` |
| `SERVER_PORT` | `8000` |
| `SERVER_RELOAD` | `true` |
