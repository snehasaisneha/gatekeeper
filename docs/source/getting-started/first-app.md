# Protecting your first app

This guide shows you how to protect an internal service with Gatekeeper using nginx.

## How it works

Nginx uses the `auth_request` directive to check authentication before serving requests. For each request:

1. Nginx sends a subrequest to Gatekeeper's `/api/v1/auth/validate` endpoint
2. Gatekeeper checks the session cookie
3. If valid, Gatekeeper returns `200 OK` and nginx serves the request
4. If invalid, Gatekeeper returns `401` and nginx redirects to the sign-in page

## Prerequisites

- Gatekeeper running and accessible
- nginx installed on your server
- An internal app you want to protect

## Step 1: Register the app

First, register your app with Gatekeeper:

```bash
uv run gk apps add --slug myapp --name "My Internal App"
```

The slug is a URL-safe identifier used in access control.

## Step 2: Grant yourself access

Grant your admin user access to the app:

```bash
uv run gk apps grant --slug myapp --email you@example.com
```

## Step 3: Configure nginx

Add this configuration to nginx. Replace the placeholders with your actual values.

```nginx
# Gatekeeper auth endpoint (internal only)
location = /_gatekeeper/validate {
    internal;
    proxy_pass http://localhost:8000/api/v1/auth/validate;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    proxy_set_header X-Original-URI $request_uri;
    proxy_set_header X-GK-App "myapp";  # Your app slug
    proxy_set_header Host $host;
    proxy_set_header Cookie $http_cookie;
}

# Your protected app
server {
    listen 443 ssl;
    server_name myapp.example.com;
    add_header X-Robots-Tag "noindex, nofollow, noarchive" always;

    # SSL configuration...

    location / {
        auth_request /_gatekeeper/validate;

        # On 401, redirect to sign-in
        error_page 401 = @signin;

        # On 403, show access denied
        error_page 403 = @denied;

        # Pass the authenticated user to your app
        auth_request_set $auth_user $upstream_http_x_auth_user;
        proxy_set_header X-Auth-User $auth_user;

        # Proxy to your app
        proxy_pass http://localhost:3000;
    }

    location @signin {
        return 302 https://auth.example.com/signin?redirect=$scheme://$host$request_uri;
    }

    location @denied {
        return 302 https://auth.example.com/request-access?app=myapp;
    }
}
```

For internal apps, keep that `X-Robots-Tag` header on the app domain too. If you also control the app HTML, add:

```html
<meta name="robots" content="noindex, nofollow, noarchive">
```

## Step 4: Reload nginx

Test and reload the configuration:

```bash
nginx -t
sudo systemctl reload nginx
```

## Step 5: Test it

1. Open your app URL in a browser (e.g., `https://myapp.example.com`)
2. You should be redirected to the Gatekeeper sign-in page
3. Sign in with your email
4. After signing in, you're redirected back to your app
5. If the user is signed in but lacks access, nginx can send them to a request-access or support flow

## Using the authenticated user

Gatekeeper passes the user's email in the `X-Auth-User` header. Your app can read this to know who's making the request.

Example in Python/Flask:

```python
from flask import request

@app.route("/")
def index():
    user_email = request.headers.get("X-Auth-User")
    return f"Hello, {user_email}!"
```

## Troubleshooting

### Getting 401 even when signed in

- Check that the `Cookie` header is being passed to Gatekeeper
- Verify `COOKIE_DOMAIN` matches your app's domain
- Check browser dev tools for the session cookie

### Getting 403 Forbidden

- Verify the user has access to the app: `gk apps show --slug myapp`
- Grant access if missing: `gk apps grant --slug myapp --email user@example.com`

### Redirect loop

- Make sure the sign-in page itself isn't protected by `auth_request`
- Gatekeeper's own endpoints should not require authentication

## Next steps

- [Managing apps](../guides/apps.md) — Add more apps and manage access
- [Managing users](../guides/users.md) — Add users and handle approvals
