# Configuration

Gatekeeper is configured entirely through environment variables. Create a `.env` file in the project root, or set them in your shell or deployment environment.

## Required settings

These must be set for Gatekeeper to run:

### SECRET_KEY

A random string used to sign session tokens. Must be at least 32 characters.

```bash
SECRET_KEY=your-random-secret-key-here-make-it-long
```

Generate one with:

```bash
openssl rand -hex 32
```

:::{warning}
Keep this secret. If it leaks, attackers can forge session tokens.
:::

### APP_URL

The public URL where Gatekeeper is hosted.

```bash
APP_URL=https://auth.example.com
```

### FRONTEND_URL

The URL where the frontend is served. Usually the same as `APP_URL`.

```bash
FRONTEND_URL=https://auth.example.com
```

## Email settings

Gatekeeper sends login codes by email. Configure one of these providers:

### AWS SES

```bash
EMAIL_PROVIDER=ses
SES_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
EMAIL_FROM=noreply@yourdomain.com
```

### SMTP

```bash
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=user
SMTP_PASSWORD=password
EMAIL_FROM=noreply@yourdomain.com
```

For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password.

## Database settings

### DATABASE_URL

Connection string for the database. Defaults to SQLite.

```bash
# SQLite (default)
DATABASE_URL=sqlite+aiosqlite:///./gatekeeper.db

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/gatekeeper
```

SQLite works well for small deployments. Use PostgreSQL for high availability or if you need multiple Gatekeeper instances.

## Cookie and SSO settings

### COOKIE_DOMAIN

The domain for session cookies. Set this to enable SSO across subdomains.

```bash
# SSO across all *.example.com subdomains
COOKIE_DOMAIN=.example.com

# Single domain only (default)
COOKIE_DOMAIN=auth.example.com
```

The leading dot (`.example.com`) allows the cookie to be shared across subdomains.

### SESSION_EXPIRY_DAYS

How long sessions last before users need to sign in again.

```bash
SESSION_EXPIRY_DAYS=30  # default
```

## Passkey settings

For passwordless sign-in with passkeys (WebAuthn):

### WEBAUTHN_RP_ID

The domain for passkey registration. Must match where users access Gatekeeper.

```bash
WEBAUTHN_RP_ID=auth.example.com
```

### WEBAUTHN_RP_NAME

Display name shown in passkey prompts.

```bash
WEBAUTHN_RP_NAME=My Company Auth
```

### WEBAUTHN_ORIGIN

The full origin URL for passkey verification.

```bash
WEBAUTHN_ORIGIN=https://auth.example.com
```

## User registration settings

### ACCEPTED_DOMAINS

Email domains that are automatically approved when users sign in. Comma-separated.

```bash
ACCEPTED_DOMAINS=example.com,company.org
```

Users with emails from other domains go into a pending state and need admin approval.

:::{note}
These domains are seeded into the database on startup. You can also manage domains via the admin UI or CLI (`gk domains add`).
:::

## Google SSO settings (optional)

Enable "Sign in with Google" as an authentication option.

### GOOGLE_CLIENT_ID

OAuth 2.0 Client ID from Google Cloud Console.

```bash
GOOGLE_CLIENT_ID=123456789-abcdef.apps.googleusercontent.com
```

### GOOGLE_CLIENT_SECRET

OAuth 2.0 Client Secret from Google Cloud Console.

```bash
GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret
```

Both settings must be provided for Google SSO to be enabled. See the [Google SSO guide](../guides/google-sso.md) for setup instructions.

## GitHub SSO settings (optional)

Enable "Sign in with GitHub" as an authentication option. GitHub SSO checks all verified emails linked to the user's GitHub account.

### GITHUB_CLIENT_ID

OAuth Client ID from GitHub Developer Settings.

```bash
GITHUB_CLIENT_ID=your-github-client-id
```

### GITHUB_CLIENT_SECRET

OAuth Client Secret from GitHub Developer Settings.

```bash
GITHUB_CLIENT_SECRET=your-github-client-secret
```

Both settings must be provided for GitHub SSO to be enabled. See the [GitHub SSO guide](../guides/github-sso.md) for setup instructions.

## Server settings

These settings configure the Gatekeeper API server. They can be set via environment variables or overridden with CLI arguments when running `gk ops serve`.

### SERVER_HOST

The address the server binds to.

```bash
SERVER_HOST=0.0.0.0  # default - listen on all interfaces
```

Use `127.0.0.1` to only accept local connections (recommended when behind a reverse proxy).

### SERVER_PORT

The port the server listens on.

```bash
SERVER_PORT=8000  # default
```

### SERVER_RELOAD

Enable auto-reload on file changes. Useful for development, should be disabled in production.

```bash
SERVER_RELOAD=true   # default - enabled for development
SERVER_RELOAD=false  # recommended for production
```

### CLI overrides

All server settings can be overridden via CLI arguments:

```bash
# Override host and port
gk ops serve --host 127.0.0.1 --port 9000

# Production mode with multiple workers
gk ops serve --no-reload --workers 4
```

See [CLI Reference](../reference/cli.md) for all available options.

### OTP_EXPIRY_MINUTES

How long login codes remain valid.

```bash
OTP_EXPIRY_MINUTES=10  # default
```

## All settings reference

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (required) | Token signing key, 32+ chars |
| `DATABASE_URL` | `sqlite:///gatekeeper.db` | Database connection string |
| `APP_URL` | `http://localhost:8000` | Public Gatekeeper URL |
| `FRONTEND_URL` | `http://localhost:4321` | Frontend URL |
| `COOKIE_DOMAIN` | `.localhost` | Cookie domain for SSO |
| `SESSION_EXPIRY_DAYS` | `30` | Session lifetime |
| `EMAIL_PROVIDER` | `ses` | `ses` or `smtp` |
| `EMAIL_FROM` | (required) | Sender email address |
| `ACCEPTED_DOMAINS` | (empty) | Auto-approve email domains |
| `GOOGLE_CLIENT_ID` | (empty) | Google OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | (empty) | Google OAuth Client Secret |
| `GITHUB_CLIENT_ID` | (empty) | GitHub OAuth Client ID |
| `GITHUB_CLIENT_SECRET` | (empty) | GitHub OAuth Client Secret |
| `WEBAUTHN_RP_ID` | `localhost` | Passkey domain |
| `WEBAUTHN_RP_NAME` | `Gatekeeper` | Passkey display name |
| `WEBAUTHN_ORIGIN` | `http://localhost:8000` | Passkey origin |
| `SERVER_HOST` | `0.0.0.0` | Server bind address |
| `SERVER_PORT` | `8000` | Server port |
| `SERVER_RELOAD` | `true` | Auto-reload on file changes |
| `OTP_EXPIRY_MINUTES` | `10` | Login code validity |
