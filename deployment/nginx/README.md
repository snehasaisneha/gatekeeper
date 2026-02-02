# Nginx Configuration

## Architecture

```
                         Internet
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    ROUTING SERVER                            │
│                    (public IP)                               │
│                                                              │
│  routing-gatekeeper.conf      routing-protected-app.conf    │
│  auth.example.com             docs.example.com              │
│         │                            │                       │
│         │ proxy                      │ auth_request + proxy  │
└─────────┼────────────────────────────┼───────────────────────┘
          │                            │
          ▼                            ▼
┌──────────────────┐         ┌──────────────────┐
│ GATEKEEPER SERVER│         │    APP SERVER    │
│ (10.0.0.10)      │         │   (10.0.0.20)    │
│                  │         │                  │
│ gatekeeper-      │◄────────│                  │
│ server.conf      │ validate│ app-server.conf  │
│ :8000            │         │ :3000            │
└──────────────────┘         └──────────────────┘
```

## Files

| File | Runs On | Purpose |
|------|---------|---------|
| `gatekeeper-server.conf` | Gatekeeper server | Serves frontend + proxies API |
| `app-server.conf` | App server | Serves your app (template) |
| `routing-gatekeeper.conf` | Routing server | Proxies to Gatekeeper (NO auth) |
| `routing-protected-app.conf` | Routing server | Auth + proxy to app (template) |

## Setup

### 1. Gatekeeper Server (10.0.0.10)

```bash
# Copy config
sudo cp gatekeeper-server.conf /etc/nginx/sites-available/gatekeeper
sudo nano /etc/nginx/sites-available/gatekeeper
# Edit: frontend_root, uvicorn port

# Enable
sudo ln -s /etc/nginx/sites-available/gatekeeper /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 2. App Server (10.0.0.20)

```bash
# Copy template
sudo cp app-server.conf /etc/nginx/sites-available/myapp
sudo nano /etc/nginx/sites-available/myapp
# Edit: listen port, backend/root

# Enable
sudo ln -s /etc/nginx/sites-available/myapp /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 3. Routing Server

```bash
# Gatekeeper routing
sudo cp routing-gatekeeper.conf /etc/nginx/sites-available/auth.example.com
sudo nano /etc/nginx/sites-available/auth.example.com
# Edit: server_name, gatekeeper server IP:port

# Protected app routing
sudo cp routing-protected-app.conf /etc/nginx/sites-available/docs.example.com
sudo nano /etc/nginx/sites-available/docs.example.com
# Edit: server_name, app_slug, server IPs, gatekeeper_url

# Enable
sudo ln -s /etc/nginx/sites-available/auth.example.com /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/docs.example.com /etc/nginx/sites-enabled/

# Test (must pass before certbot)
sudo nginx -t && sudo systemctl reload nginx

# SSL (after nginx -t passes)
sudo certbot --nginx -d auth.example.com -d docs.example.com
```

### 4. Register App in Gatekeeper

```bash
uv run gk apps add --slug docs --name "Documentation"
uv run gk apps grant --slug docs --email user@example.com
```

## Auth Flow

1. User visits `http://docs.example.com/page`
2. Routing server: `auth_request` → `http://10.0.0.10:8000/api/v1/auth/validate`
3. Gatekeeper checks session:
   - **401** → redirect to `http://auth.example.com/signin?redirect=...`
   - **403** → redirect to `http://auth.example.com/request-access?app=docs`
   - **200** → proxy to `http://10.0.0.20:3000` with `X-Auth-User` header

## Cookie Domain

For SSO across subdomains, set in Gatekeeper's `.env`:

```
COOKIE_DOMAIN=.example.com
```
