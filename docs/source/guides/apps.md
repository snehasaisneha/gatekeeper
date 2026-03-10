# Managing apps

An app in Gatekeeper is a protected service identified by a slug.

Examples:

- `docs`
- `grafana`
- `jupyter`
- `admin-panel`

The slug is what nginx sends in `X-GK-App` during the auth subrequest.

## Registering apps

```bash
uv run gk apps add --slug docs --name "Engineering Docs"
uv run gk apps add --slug grafana --name "Grafana"
```

The slug must contain only lowercase letters, numbers, and hyphens.

## Listing and inspecting apps

```bash
uv run gk apps list
uv run gk apps show --slug docs
```

## Granting access

Explicit grants matter most for external users and for any deployment using strict app registration.

```bash
uv run gk apps grant --slug docs --email contractor@example.net
uv run gk apps grant --slug docs --email alice@example.com --role editor
uv run gk apps grant --slug wiki --all-approved
```

## Revoking access

```bash
uv run gk apps revoke --slug docs --email contractor@example.net
```

## Removing apps

```bash
uv run gk apps remove --slug old-dashboard --force
```

## Internal vs external access

Gatekeeper distinguishes between:

- internal users: email domain is in `ACCEPTED_DOMAINS`
- external users: everyone else

Registered app behavior:

- internal users are broadly allowed
- external users need explicit grants
- admins bypass normal app restrictions

Unregistered app behavior is controlled by `DEFAULT_APP_ACCESS`:

- `allow`: signed-in users can pass validation for unregistered apps
- `deny`: unregistered apps return `403`

If you want tight control, set `DEFAULT_APP_ACCESS=deny` and register every protected app.

## Roles

Roles are optional string hints attached to an app grant.

```bash
uv run gk apps grant --slug docs --email alice@example.com --role editor
```

Gatekeeper does not enforce role semantics. It forwards the role to your app in the auth response headers if your nginx config exposes it:

```nginx
auth_request_set $auth_role $upstream_http_x_auth_role;
proxy_set_header X-Auth-Role $auth_role;
```

Common patterns:

- `viewer`, `editor`, `admin`
- `read`, `write`
- `member`, `owner`

## nginx integration

Typical protected-app snippet:

```nginx
location = /_gk/validate {
    internal;
    proxy_pass https://auth.example.com/api/v1/auth/validate;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    proxy_set_header X-Original-URI $request_uri;
    proxy_set_header X-GK-App docs;
    proxy_set_header Cookie $http_cookie;
}
```

For internal apps on public hostnames, add:

```nginx
add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
```

If you also control the app HTML, add:

```html
<meta name="robots" content="noindex, nofollow, noarchive">
```

This is especially relevant for engineering docs, dashboards, notebooks, and internal admin tools.
