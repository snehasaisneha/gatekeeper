# Gatekeeper

Self-hosted auth gateway for internal tools. Email OTP, passkeys, Google, GitHub, multi-app SSO, and an admin/security surface for approvals, app access, bans, and audit review.

© 2025 Sai Sneha · [AGPL-3.0-or-later](LICENSE)

Gatekeeper is free to use, modify, and self-host, in perpetuity. Source sharing is only required if you offer a modified version of Gatekeeper as a public service.

## Why Gatekeeper?

You have internal tools — docs, dashboards, Jupyter notebooks, admin panels. You need auth, but:

- **Auth0/Okta** = $23+/user/month, your data on their servers
- **Keycloak** = 512MB+ RAM, days of setup, enterprise complexity
- **Cloudflare Access** = traffic through their network, vendor lock-in
- **Basic auth** = unhashed passwords, no audit trail, security theater

Gatekeeper sits behind an auth hostname such as `auth.example.com` and protects sibling subdomains through nginx `auth_request`.

## Features

- **Google SSO + GitHub SSO + Email OTP + Passkeys** — Multiple auth methods, no passwords
- **Zero-friction onboarding** — Users from approved domains sign in directly, no registration
- **Multi-app SSO** — One login for all your internal tools (`*.company.com`)
- **Role-based access** — Control who accesses what, with optional role hints
- **Admin panel** — Approve users, manage domains and apps
- **Security controls** — IP and email bans, audit logs, rate limits, public-docs disablement
- **CLI tools** — `gk users`, `gk apps`, `gk domains`, `gk ops` for headless management
- **SQLite or PostgreSQL** — Zero-config default, scales when needed
- **SES or SMTP** — Bring your own email provider

## Quick Start

```bash
# Clone and configure
git clone <repo> && cd gatekeeper
uv sync
cp .env.example .env

# Initialize
uv run all-migrations
uv run gk users add --email admin@example.com --admin --seeded

# Run locally
npm -C frontend run build
uv run gk ops serve --host 127.0.0.1 --port 8000
```

Frontend dev mode: `cd frontend && npm install && npm run dev`

In production, keep `PUBLIC_API_DOCS=false`, set `TRUSTED_PROXY_IPS` to only your proxy tiers, and put `X-Robots-Tag: noindex, nofollow, noarchive` on the public auth and internal app hostnames.

## Protecting Apps

1. Register an app in Gatekeeper:

   ```bash
   uv run gk apps add --slug docs --name "Documentation"
   uv run gk apps grant --slug docs --email user@example.com
   ```

2. Configure nginx to validate requests:
   ```nginx
   location / {
       auth_request /_gatekeeper/validate;
       proxy_set_header X-Auth-User $auth_user;
       proxy_pass http://your-app:3000;
   }
   ```

See [`deployment/`](deployment/), [`deployment/README.md`](deployment/README.md), and the Sphinx guides under [`docs/source/guides`](docs/source/guides) for the current nginx and rollout flow.

## CLI

```bash
# User management
uv run gk users add --email user@example.com
uv run gk users list
uv run gk users approve --email user@example.com

# Domain management (auto-approve users from these domains)
uv run gk domains add --domain company.com
uv run gk domains list

# App management
uv run gk apps add --slug grafana --name "Grafana"
uv run gk apps grant --slug grafana --email user@example.com --role admin
uv run gk apps list

# Operations
uv run gk ops test-email --to you@example.com
uv run gk ops healthcheck
```

## Configuration

Key environment variables (see `.env.example` for all):

| Variable              | Description                                         |
| --------------------- | --------------------------------------------------- |
| `SECRET_KEY`          | Signing key (min 32 chars)                          |
| `DATABASE_URL`        | `sqlite+aiosqlite:///./gatekeeper.db` or PostgreSQL |
| `ACCEPTED_DOMAINS`    | Seed approved internal domains on startup           |
| `EMAIL_PROVIDER`      | `ses` or `smtp`                                     |
| `COOKIE_DOMAIN`       | `.example.com` for multi-app SSO                    |
| `PUBLIC_API_DOCS`     | Leave `false` in production                         |
| `TRUSTED_PROXY_IPS`   | Proxy IPs/CIDRs allowed to set forwarded IP headers |
| `GOOGLE_CLIENT_ID`    | Google OAuth client ID (optional)                   |
| `GOOGLE_CLIENT_SECRET`| Google OAuth client secret (optional)               |
| `GITHUB_CLIENT_ID`    | GitHub OAuth client ID (optional)                   |
| `GITHUB_CLIENT_SECRET`| GitHub OAuth client secret (optional)               |
| `WEBAUTHN_RP_ID`      | Domain for passkey registration                     |

## Production Deployment

```bash
# On your server
uv run all-migrations
uv run gk users add --email admin@example.com --admin --seeded

# Systemd
sudo cp deployment/systemd/gatekeeper.service /etc/systemd/system/
sudo systemctl enable --now gatekeeper

# Nginx
sudo cp deployment/nginx/gatekeeper-server.conf /etc/nginx/sites-available/gatekeeper
sudo certbot --nginx -d auth.example.com
```

See [`deployment/README.md`](deployment/README.md) for the full deployment guide and [`docs/source/guides/rollouts.md`](docs/source/guides/rollouts.md) for the rollout checklist.

## Who This Is For

**Good fit:**

- Small to medium teams (5–100 users)
- 3–10 internal tools needing protection
- Self-hosted requirement (data residency, compliance)
- Teams using Google Workspace or GitHub (one-click SSO)

**Not a fit:**

- Enterprise scale (1000+ users, complex RBAC hierarchies)
- Multi-tenant SaaS (customer-facing auth)
- Need for SAML/OIDC provider integration beyond Google/GitHub
