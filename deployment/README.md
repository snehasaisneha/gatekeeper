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
│ (10.0.0.10)     │        │ (10.0.0.20)     │
│                 │        │                 │
│ gatekeeper-     │        │ app-server.conf │
│ server.conf     │        │                 │
└─────────────────┘        └─────────────────┘
```

## Files

```
deployment/
├── nginx/
│   ├── gatekeeper-server.conf      # Gatekeeper server (internal)
│   ├── app-server.conf             # App server template (internal)
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
cd /opt/gatekeeper
cp .env.example .env && nano .env
uv sync
npm -C frontend install && npm -C frontend run build
uv run gk ops migrate
uv run gk users add --email admin@example.com --admin --seeded

# Nginx
sudo cp deployment/nginx/gatekeeper-server.conf /etc/nginx/sites-available/gatekeeper
sudo ln -s /etc/nginx/sites-available/gatekeeper /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Systemd
sudo cp deployment/systemd/gatekeeper.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now gatekeeper
```

### 2. Routing Server

```bash
# Gatekeeper route
sudo cp deployment/nginx/routing-gatekeeper.conf /etc/nginx/sites-available/auth.example.com
sudo nano /etc/nginx/sites-available/auth.example.com  # Edit IPs
sudo ln -s /etc/nginx/sites-available/auth.example.com /etc/nginx/sites-enabled/

# Protected app route
sudo cp deployment/nginx/routing-protected-app.conf /etc/nginx/sites-available/docs.example.com
sudo nano /etc/nginx/sites-available/docs.example.com  # Edit IPs, slug
sudo ln -s /etc/nginx/sites-available/docs.example.com /etc/nginx/sites-enabled/

# Test then SSL
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d auth.example.com -d docs.example.com
```

### 3. Register App

```bash
uv run gk apps add --slug docs --name "Documentation"
uv run gk apps grant --slug docs --email admin@example.com
```

## Cookie Domain

```
COOKIE_DOMAIN=.example.com
```
