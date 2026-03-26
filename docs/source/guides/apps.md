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

## Gatekeeper app admin roles

Gatekeeper app administration is separate from the runtime `X-Auth-Role` header, but it can now be derived from it.

Each app has an `admin_roles` setting. If a user is granted one of those roles for that app, Gatekeeper treats them as an app admin for that app only. That gives them access to the scoped app-management surface in Gatekeeper, including grants, settings, scoped API keys, and app audit visibility.

Example:

- app roles: `viewer,editor,owner`
- app admin roles: `owner`

In that setup:

- `viewer` and `editor` users can use the app normally
- `owner` users also become Gatekeeper app admins for that app

Gatekeeper still forwards the assigned role to the app in `X-Auth-Role`. Your app decides what that role means at runtime.

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
    proxy_set_header Host auth.example.com;
    proxy_set_header Cookie $http_cookie;
}
```

The `Host` header on the auth subrequest must be the Gatekeeper auth host, not the protected app host. That keeps the subrequest aligned with the auth layer and avoids cross-host validation bugs.

### What the admin wizard generates

When you create an app from the admin UI, the wizard generates a protected-app nginx block that:

- proxies `/_gk/validate` to your Gatekeeper auth URL
- sets `Host` to the Gatekeeper auth hostname
- forwards `X-GK-App` with the app slug you registered
- captures Gatekeeper response headers and forwards them to your upstream app
- redirects `401` users to Gatekeeper signin
- redirects `403` users to the Gatekeeper access-request page
- routes `/logout` and `/signout` back through the auth host so users land on a clean signin flow

### App-side authorization headers

Gatekeeper authentication happens at nginx. Your app should trust the headers coming from that nginx tier, not from the public internet directly.

Typical forwarding block:

```nginx
location / {
    auth_request /_gk/validate;
    auth_request_set $auth_user $upstream_http_x_auth_user;
    auth_request_set $auth_role $upstream_http_x_auth_role;
    auth_request_set $auth_name $upstream_http_x_auth_name;

    proxy_pass http://127.0.0.1:3000;
    proxy_set_header Host $host;
    proxy_set_header X-Auth-User $auth_user;
    proxy_set_header X-Auth-Role $auth_role;
    proxy_set_header X-Auth-Name $auth_name;
}
```

The important headers are:

- `X-Auth-User`: the authenticated email identity
- `X-Auth-Role`: the Gatekeeper app role if one was granted
- `X-Auth-Name`: the user display name when available

### How your app should use those headers

Treat `X-Auth-User` as the primary identity key. Most apps should map that header to their local session/user model on each request.

Treat `X-Auth-Role` as an authorization hint coming from Gatekeeper. Gatekeeper does not enforce role semantics inside your app. You define what `viewer`, `editor`, `admin`, or any custom role means once the request reaches your application.

Recommended pattern:

- reject or redirect if `X-Auth-User` is missing
- look up the user by `X-Auth-User`
- map `X-Auth-Role` to your internal permissions
- default safely if the role header is empty

If you need app-local super-admin behavior, use a Gatekeeper app role like `admin` or `owner` and map that role in your own authorization layer.

For internal apps on public hostnames, add:

```nginx
add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
```

If you also control the app HTML, add:

```html
<meta name="robots" content="noindex, nofollow, noarchive">
```

This is especially relevant for engineering docs, dashboards, notebooks, and internal admin tools.
