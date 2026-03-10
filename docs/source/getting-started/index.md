# Getting Started

This guide is the shortest path to a working Gatekeeper deployment.

## Before you start

You need:

- Python 3.12+
- `uv`
- nginx for production use
- an email provider for OTP delivery
- a public auth hostname such as `auth.example.com`

For local development, you can run Gatekeeper directly without nginx and use a test SMTP setup.

## 1. Install the project

```bash
git clone https://github.com/snehasaisneha/gatekeeper
cd gatekeeper
uv sync
npm -C frontend install
```

## 2. Create your config

```bash
cp .env.example .env
```

Set at least:

```bash
SECRET_KEY="$(openssl rand -hex 32)"
APP_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:8000"
DATABASE_URL="sqlite+aiosqlite:///./data/gatekeeper.db"
EMAIL_PROVIDER="smtp"
SMTP_HOST="smtp.example.com"
SMTP_PORT=587
SMTP_USER="smtp-user"
SMTP_PASSWORD="smtp-password"
SMTP_FROM_EMAIL="auth@example.com"
WEBAUTHN_RP_ID="localhost"
WEBAUTHN_ORIGIN="http://localhost:8000"
```

If you want users from company domains to be auto-approved, also set:

```bash
ACCEPTED_DOMAINS="example.com,subsidiary.example"
```

## 3. Initialize the database

```bash
mkdir -p data
uv run all-migrations
```

## 4. Create the first admin

```bash
uv run gk users add --email you@example.com --admin --seeded
```

`--seeded` creates an already-approved user so you can sign in immediately.

## 5. Build and run Gatekeeper

```bash
npm -C frontend run build
uv run gk ops serve --host 127.0.0.1 --port 8000
```

Open `http://localhost:8000/signin`.

## 6. Sign in and open the admin UI

1. Enter your email at `/signin`.
2. Complete OTP or use another configured method.
3. Open `/admin`.

From there you can:

- review pending users
- add approved domains
- register apps
- inspect bans and security events
- adjust branding

## 7. Put nginx in front of your apps

For production, Gatekeeper expects nginx to protect internal apps via `auth_request`.

Read these next:

- [Configuration](configuration.md)
- [Protecting your first app](first-app.md)
- [Deployment](../guides/deployment.md)

```{toctree}
:hidden:

configuration
first-app
```
