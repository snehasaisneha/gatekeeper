# Gatekeeper

Lightweight, self-hosted auth gateway for internal tools. Email OTP + Passkeys. Multi-app SSO. Protect any app behind nginx. No vendor lock-in, no per-user pricing, full data control.

## Why Gatekeeper?

You have internal tools — docs, dashboards, Jupyter notebooks, admin panels. You need auth, but:

- **Auth0/Okta** = $23+/user/month, your data on their servers
- **Keycloak** = 512MB+ RAM, days of setup, enterprise complexity
- **Cloudflare Access** = traffic through their network, vendor lock-in
- **Basic auth** = unhashed passwords, no audit trail, security theater

Gatekeeper: single SQLite file, ~50MB RAM, deploys in 15 minutes. Sits in front of nginx, protects anything behind it.

## Features

- **Email OTP + Passkeys** — No passwords to manage or leak
- **Multi-app SSO** — One login for all your internal tools (`*.company.com`)
- **Role-based access** — Control who accesses what, with optional role hints
- **Admin panel** — Approve registrations, manage users and apps
- **CLI tools** — `gk users`, `gk apps`, `gk ops` for headless management
- **SQLite or PostgreSQL** — Zero-config default, scales when needed
- **SES or SMTP** — Bring your own email provider

## Quick Start

```bash
# Clone and configure
git clone <repo> && cd gatekeeper
cp .env.example .env  # Edit with your settings

# Install and run
uv sync
uv run all-migrations
uv run gk users add --email admin@example.com --admin --seeded
uv run gatekeeper
```

Frontend: `cd frontend && npm install && npm run dev`

**That's it.** API at `:8000`, frontend at `:4321`.

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

See [`deployment/`](deployment/) for complete nginx configs.

## CLI

```bash
# User management
uv run gk users add --email user@example.com
uv run gk users list
uv run gk users approve --email user@example.com

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

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Signing key (min 32 chars) |
| `DATABASE_URL` | `sqlite+aiosqlite:///./gatekeeper.db` or PostgreSQL |
| `ACCEPTED_DOMAINS` | Auto-approve emails from these domains |
| `EMAIL_PROVIDER` | `ses` or `smtp` |
| `COOKIE_DOMAIN` | `.example.com` for multi-app SSO |
| `WEBAUTHN_RP_ID` | Domain for passkey registration |

## Production Deployment

```bash
# On your server
uv run all-migrations
uv run gk users add --email admin@example.com --admin --seeded

# Systemd
sudo cp deployment/systemd/gatekeeper.service /etc/systemd/system/
sudo systemctl enable --now gatekeeper

# Nginx
sudo cp deployment/nginx/gatekeeper.conf /etc/nginx/sites-available/
sudo certbot --nginx -d auth.example.com
```

See [`deployment/README.md`](deployment/README.md) for full guide.

## Who This Is For

**Good fit:**
- Small to medium teams (5–100 users)
- 3–10 internal tools needing protection
- Self-hosted requirement (data residency, compliance)
- No existing IdP, or want independence from it

**Not a fit:**
- Enterprise scale (1000+ users, complex RBAC hierarchies)
- Multi-tenant SaaS (customer-facing auth)
- Existing Google Workspace/Okta SSO you want to use

## License

AGPL-3.0-or-later

Use, modify, and deploy internally with no obligations. Source-sharing only required if you offer a modified version as a public service.
