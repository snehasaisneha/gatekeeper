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
│  auth.example.com             app.example.com               │
│         │                            │                       │
│         │ proxy                      │ auth_request + proxy  │
└─────────┼────────────────────────────┼───────────────────────┘
          │                            │
          ▼                            ▼
┌──────────────────┐         ┌──────────────────┐
│ GATEKEEPER SERVER│         │    APP SERVER    │
│ (private IP)     │         │   (private IP)   │
│                  │         │                  │
│ nginx:8000       │◄────────│                  │
│ uvicorn:8001     │ validate│ app:8000         │
└──────────────────┘         └──────────────────┘
```

## Files

| File | Runs On | Purpose |
|------|---------|---------|
| `gatekeeper-server.conf` | Gatekeeper server | Serves frontend (nginx) + proxies API to uvicorn |
| `app-server.conf` | App server | Optional - only if app needs nginx in front |
| `routing-gatekeeper.conf` | Routing server | Proxies to Gatekeeper (NO auth - must be public) |
| `routing-protected-app.conf` | Routing server | Auth validation + proxy to app (copy per app) |

## Setup

### 1. Gatekeeper Server

```bash
# Create config (edit the path to frontend/dist)
sudo nano /etc/nginx/sites-available/gatekeeper

# Paste contents of gatekeeper-server.conf, then:
sudo ln -s /etc/nginx/sites-available/gatekeeper /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # remove default site
sudo nginx -t && sudo systemctl reload nginx
```

**Important:** The config includes `absolute_redirect off` and `port_in_redirect off` to prevent nginx from leaking the internal port (8000) in redirects.
It should also send `X-Robots-Tag: noindex, nofollow, noarchive` on the auth host so search engines do not index your login domain.
Gatekeeper should trust forwarded client IP headers only from this nginx tier. Set `TRUSTED_PROXY_IPS` in `.env` to the exact nginx/routing server IPs or CIDRs.

### 2. Routing Server - Gatekeeper Route

```bash
sudo nano /etc/nginx/sites-available/auth.example.com
# Paste contents of routing-gatekeeper.conf
# Edit: server_name, proxy_pass IP

sudo ln -s /etc/nginx/sites-available/auth.example.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d auth.example.com
```

The auth route template includes:

```nginx
add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
```

It should also overwrite the forwarding headers explicitly:

```nginx
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

### 3. Routing Server - Protected App Route

For each protected app:

```bash
sudo nano /etc/nginx/sites-available/app.example.com
# Paste contents of routing-protected-app.conf
# Edit these 5 values:
#   - server_name (your app domain)
#   - proxy_pass in /_gk/validate (Gatekeeper IP:8000)
#   - X-GK-App header (app slug)
#   - proxy_pass in location / (App server IP:port)
#   - URLs in @login and @denied (Gatekeeper public URL + app slug)

sudo ln -s /etc/nginx/sites-available/app.example.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d app.example.com
```

For internal apps, the protected-app template also includes:

```nginx
add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0" always;
```

If you control the app HTML too, add a page-level robots meta tag as defense in depth:

```html
<meta name="robots" content="noindex, nofollow, noarchive">
```

The protected-app template also routes `/logout` and `/signout` back through Gatekeeper signin
after clearing the session. That gives cached static apps a clean post-logout landing state.

### 4. Register App in Gatekeeper

Via CLI:
```bash
uv run gk apps add --slug myapp --name "My App"
uv run gk apps grant --slug myapp --email user@example.com
```

Or via admin UI at `https://auth.example.com/admin`

## Auth Flow

1. User visits `https://app.example.com/page`
2. Routing nginx: `auth_request` → Gatekeeper `/api/v1/auth/validate`
3. Gatekeeper checks session cookie:
   - **401** (not logged in) → redirect to `/signin?redirect=...`
   - **403** (no app access) → redirect to `/request-access?app=...`
   - **200** (authorized) → proxy to app with `X-Auth-User` header

## Troubleshooting

### 502 Bad Gateway
- App server not reachable from routing server
- Check: Is the app running? `curl http://<app-ip>:<port>/` from routing server
- Check: Is the app binding to `0.0.0.0`? Use `ss -tlnp | grep <port>` - should show `0.0.0.0`, not `127.0.0.1`

### Redirect shows wrong port (e.g., :8000)
- Missing `absolute_redirect off;` and `port_in_redirect off;` in gatekeeper-server.conf
- Or browser cached old 301 redirect - test in incognito

### After login, doesn't redirect back to app
- Check that `@login` location uses `?redirect=$scheme://$host$request_uri`
- Rebuild frontend if this was recently fixed

### Logout looks stale until the next click or reload
- Keep the protected app `Cache-Control: no-store` headers
- Route `/logout` and `/signout` through `https://auth.example.com/signin?...` after signout
- For static sites, use a normal browser navigation for logout rather than a background fetch

## Cookie Domain

For SSO across subdomains (`auth.example.com`, `app.example.com`), set in Gatekeeper `.env`:

```
COOKIE_DOMAIN=.example.com
```

## Existing Deployments

If your auth domain is already live, add this to the `server` block for `auth.example.com` and reload nginx:

```nginx
add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
```

Then verify:

```bash
curl -I https://auth.example.com
curl https://auth.example.com/robots.txt
```

The response headers should include `X-Robots-Tag: noindex, nofollow, noarchive`, and `robots.txt` should disallow all crawlers.

## API-Only Apps

Works for browser-based API calls. The flow:
1. JS frontend calls `https://api.example.com/endpoint`
2. Returns 401 → browser follows redirect to login
3. User logs in → cookie set on `.example.com`
4. JS retries API call → cookie sent → authorized

**Won't work** for server-to-server or CLI calls (no browser to handle redirects).
