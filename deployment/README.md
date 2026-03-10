# Deployment

## Architecture

```
                    Internet
                        │
                        ▼
              ┌─────────────────┐
              │ ROUTING SERVER  │  routing-gatekeeper.conf
              │ (public IP)     │  routing-protected-app.conf
              └────────┬────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
┌─────────────────┐        ┌─────────────────┐
│ GATEKEEPER      │        │ APP SERVER      │
│ (private IP)    │        │ (private IP)    │
│                 │        │                 │
│ nginx:8000      │        │ your-app:8000   │
│ uvicorn:8001    │        │                 │
└─────────────────┘        └─────────────────┘
```

## Files

```
deployment/
├── nginx/
│   ├── gatekeeper-server.conf      # Gatekeeper: nginx + frontend
│   ├── app-server.conf             # App server (optional template)
│   ├── routing-gatekeeper.conf     # Routing → Gatekeeper (public)
│   ├── routing-protected-app.conf  # Routing → App with auth (public)
│   └── README.md
├── systemd/
│   └── gatekeeper.service
└── README.md
```

## Quick Deploy

### 1. Gatekeeper Server

```bash
# Clone and install
sudo mkdir -p /deploy && sudo chown $USER:$USER /deploy
git clone <your-repo> /deploy/gatekeeper
cd /deploy/gatekeeper

# Install nginx and certbot if needed
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx

# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Install dependencies and build frontend
uv sync
npm -C frontend install && npm -C frontend run build

# Configure
cp .env.example .env
nano .env  # Set SECRET_KEY, DATABASE_URL, COOKIE_DOMAIN, email config, etc.

# Initialize database
mkdir -p data
uv run all-migrations

# Create admin user
uv run gk users add --email admin@example.com --admin --seeded

# Nginx (edit path in config first)
sudo nano /etc/nginx/sites-available/gatekeeper
# Paste deployment/nginx/gatekeeper-server.conf contents
sudo ln -s /etc/nginx/sites-available/gatekeeper /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# Systemd (edit paths in config first)
sudo nano /etc/systemd/system/gatekeeper.service
# Paste deployment/systemd/gatekeeper.service contents
sudo systemctl daemon-reload && sudo systemctl enable --now gatekeeper

# Verify
sudo systemctl status gatekeeper
curl http://localhost:8000/health
```

### 2. Routing Server

```bash
# Gatekeeper route (public, no auth)
sudo nano /etc/nginx/sites-available/auth.example.com
# Paste routing-gatekeeper.conf, edit server_name and proxy_pass IP
sudo ln -s /etc/nginx/sites-available/auth.example.com /etc/nginx/sites-enabled/

# Protected app route (copy for each app)
sudo nano /etc/nginx/sites-available/app.example.com
# Paste routing-protected-app.conf, edit the 5 marked values
sudo ln -s /etc/nginx/sites-available/app.example.com /etc/nginx/sites-enabled/

# Test and enable SSL
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d auth.example.com -d app.example.com
```

The auth route template now includes:

```nginx
add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
```

This should stay on your public auth host so search engines do not index your login pages.
The protected-app template now includes the same header for internal app domains, plus
`Cache-Control: no-store` so cached static apps do not appear to stay logged in after signout.

### 3. Register Apps

Via CLI:
```bash
cd /deploy/gatekeeper
uv run gk apps add --slug myapp --name "My App"
uv run gk apps grant --slug myapp --email admin@example.com
```

Or via admin UI at `https://auth.example.com/admin`

### 4. App Server

Your app just needs to:
1. Run on a port accessible from the routing server
2. Bind to `0.0.0.0` (not `127.0.0.1`)
3. Optionally read `X-Auth-User` header for user info

No nginx needed on app server unless you want to serve static files.

## Environment Variables

Key `.env` settings:

```bash
# Required
SECRET_KEY="<generate with: openssl rand -hex 32>"
DATABASE_URL="sqlite+aiosqlite:///./data/gatekeeper.db"

# URLs (update after SSL setup)
APP_URL="https://auth.example.com"
FRONTEND_URL="https://auth.example.com"

# Cookie (for SSO across subdomains)
COOKIE_DOMAIN=".example.com"

# Server
SERVER_PORT=8001
SERVER_RELOAD=false

# WebAuthn
WEBAUTHN_RP_ID="auth.example.com"
WEBAUTHN_ORIGIN="https://auth.example.com"

# Email - SMTP (Gmail example)
EMAIL_PROVIDER="smtp"
SMTP_HOST="smtp.gmail.com"
SMTP_PORT=587
SMTP_USER="you@gmail.com"
SMTP_PASSWORD="<app-password>"
SMTP_FROM_EMAIL="you@gmail.com"
```

## Troubleshooting

### Service won't start
```bash
sudo journalctl -u gatekeeper -f --no-pager -n 50
```

### 502 Bad Gateway on protected app
- App not running or not binding to `0.0.0.0`
- Test from routing server: `curl http://<app-private-ip>:<port>/`

### Redirect shows :8000 port
- Add `absolute_redirect off;` and `port_in_redirect off;` to gatekeeper nginx config
- Test in incognito (browser caches 301 redirects)

### Login doesn't redirect back to app
- Ensure frontend was rebuilt after redirect fix
- Check `@login` location has `?redirect=$scheme://$host$request_uri`

### Keep auth.example.com out of search
- Ensure the auth nginx `server` block sends `X-Robots-Tag: noindex, nofollow, noarchive`
- Rebuild and redeploy the frontend so `/robots.txt` is served with `Disallow: /`
- Verify with `curl -I https://auth.example.com` and `curl https://auth.example.com/robots.txt`

### Keep internal apps out of search
- Leave `X-Robots-Tag: noindex, nofollow, noarchive` on protected app nginx server blocks too
- If you control the app HTML, add `<meta name="robots" content="noindex, nofollow, noarchive">`
- Verify with `curl -I https://app.example.com`

### Logout looks stale on static docs or other cached apps
- Keep the protected app `Cache-Control: no-store` headers in nginx
- Route `/logout` and `/signout` through the Gatekeeper signin page after signout
- Use a normal browser navigation for logout, not a background fetch
