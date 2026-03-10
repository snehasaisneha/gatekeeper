# Deployment

This guide covers deploying Gatekeeper to a production server.

## Architecture

A typical Gatekeeper deployment looks like this:

```
Internet
    ↓
┌─────────────────────────────────────────┐
│  nginx (routing server)                 │
│  - Routes to Gatekeeper on auth.*       │
│  - Routes to apps on *.example.com      │
│  - Uses auth_request for protection     │
└─────────────────────────────────────────┘
    ↓                    ↓
┌──────────────┐   ┌──────────────┐
│  Gatekeeper  │   │  Your Apps   │
│  (port 8001) │   │  (various)   │
└──────────────┘   └──────────────┘
```

Gatekeeper runs as a systemd service. nginx handles SSL termination and routing.

## Server setup

### 1. Install dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install nginx python3.12 python3.12-venv

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and install

```bash
cd /opt
sudo git clone https://github.com/snehasaisneha/gatekeeper
cd gatekeeper
sudo uv sync
```

### 3. Configure

Create the environment file:

```bash
sudo cp .env.example /opt/gatekeeper/.env
sudo nano /opt/gatekeeper/.env
```

Set production values:

```bash
SECRET_KEY=<generate with: openssl rand -hex 32>
DATABASE_URL=sqlite+aiosqlite:////opt/gatekeeper/gatekeeper.db
APP_URL=https://auth.example.com
FRONTEND_URL=https://auth.example.com
COOKIE_DOMAIN=.example.com
PUBLIC_API_DOCS=false
TRUSTED_PROXY_IPS=127.0.0.1,10.0.0.0/8
EMAIL_PROVIDER=ses
# ... other settings
```

`TRUSTED_PROXY_IPS` must include only the nginx or routing tiers that are allowed to set `X-Forwarded-For` / `X-Real-IP`. Do not put broad public ranges there.

### 4. Initialize database

```bash
cd /opt/gatekeeper
sudo uv run all-migrations
sudo uv run gk users add --email admin@example.com --admin --seeded
```

### 5. Build frontend

```bash
cd /opt/gatekeeper/frontend
sudo npm install
sudo npm run build
```

## Systemd service

Create `/etc/systemd/system/gatekeeper.service`:

```ini
[Unit]
Description=Gatekeeper Auth Service
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/gatekeeper
Environment="PATH=/opt/gatekeeper/.venv/bin:/usr/local/bin:/usr/bin"
ExecStart=/opt/gatekeeper/.venv/bin/gk ops serve --host 127.0.0.1 --port 8001 --no-reload --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

:::{tip}
Adjust `--workers` based on your server's CPU cores. A good starting point is 2-4 workers per CPU core.

You can also set server options via environment variables instead of CLI flags:

```ini
Environment="SERVER_HOST=127.0.0.1"
Environment="SERVER_PORT=8001"
Environment="SERVER_RELOAD=false"
```
:::

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable gatekeeper
sudo systemctl start gatekeeper
```

Check status:

```bash
sudo systemctl status gatekeeper
sudo journalctl -u gatekeeper -f
```

## nginx configuration

### Gatekeeper server

Create `/etc/nginx/sites-available/gatekeeper`:

```nginx
server {
    listen 80;
    server_name auth.example.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name auth.example.com;

    # SSL (add your certificates)
    ssl_certificate /etc/letsencrypt/live/auth.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/auth.example.com/privkey.pem;
    add_header X-Robots-Tag "noindex, nofollow, noarchive" always;

    # Frontend static files
    location / {
        root /opt/gatekeeper/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Protected app

Create a config for each protected app:

```nginx
# Internal auth check
location = /_gatekeeper/validate {
    internal;
    proxy_pass http://127.0.0.1:8001/api/v1/auth/validate;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    proxy_set_header X-Original-URI $request_uri;
    proxy_set_header X-GK-App "myapp";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Cookie $http_cookie;
}

server {
    listen 443 ssl http2;
    server_name myapp.example.com;
    add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
    add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0" always;
    add_header Pragma "no-cache" always;
    add_header Expires "0" always;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    location / {
        auth_request /_gatekeeper/validate;
        error_page 401 = @signin;
        error_page 403 = @denied;

        auth_request_set $auth_user $upstream_http_x_auth_user;
        proxy_set_header X-Auth-User $auth_user;

        proxy_pass http://127.0.0.1:3000;
    }

    location @signin {
        return 302 https://auth.example.com/signin?redirect=$scheme://$host$request_uri;
    }

    location @denied {
        return 302 https://auth.example.com/request-access?app=myapp;
    }

    location = /logout {
        return 302 https://auth.example.com/signout?redirect=https://auth.example.com/signin?redirect=https://$host/;
    }

    location = /signout {
        return 302 https://auth.example.com/signout?redirect=https://auth.example.com/signin?redirect=https://$host/;
    }
}
```

For internal apps, leave that `X-Robots-Tag` header on the protected app domain too. If you control the app HTML, add:

```html
<meta name="robots" content="noindex, nofollow, noarchive">
```

For static docs and other cached internal apps, keep the `Cache-Control: no-store` headers on the
protected app nginx block. That avoids stale pages appearing to remain logged in after signout.

Enable and reload:

```bash
sudo ln -s /etc/nginx/sites-available/gatekeeper /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## SSL certificates

Use Let's Encrypt for free certificates:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d auth.example.com
sudo certbot --nginx -d myapp.example.com
```

Certbot automatically renews certificates.

## Existing deployments

If your auth domain is already live, make sure the `auth.example.com` nginx `server` block sends:

```nginx
add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
```

Then redeploy the frontend so `/robots.txt` is published, reload nginx, and verify:

```bash
curl -I https://auth.example.com
curl https://auth.example.com/robots.txt
```

The response should include `X-Robots-Tag: noindex, nofollow, noarchive`, and `robots.txt` should disallow all crawlers.

## Health checks

Test that everything is working:

```bash
# Check service
sudo systemctl status gatekeeper

# Check API
curl -s http://127.0.0.1:8001/api/v1/health

# Check from outside
curl -s https://auth.example.com/api/v1/health
```

## Updating

To update Gatekeeper:

```bash
cd /opt/gatekeeper
sudo git pull
sudo uv sync
sudo uv run all-migrations
cd frontend && sudo npm install && sudo npm run build
sudo systemctl restart gatekeeper
```

## Backups

For SQLite, back up the database file:

```bash
cp /opt/gatekeeper/gatekeeper.db /backup/gatekeeper-$(date +%Y%m%d).db
```

For PostgreSQL, use `pg_dump`:

```bash
pg_dump gatekeeper > /backup/gatekeeper-$(date +%Y%m%d).sql
```
