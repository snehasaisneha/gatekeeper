# Gatekeeper

Gatekeeper is a self-hosted authentication gateway for internal apps. It gives you one auth domain, one session, and one admin surface for sign-in, approvals, app access, and audit/security review.

## What Gatekeeper does

- Puts a dedicated auth service in front of internal apps using nginx `auth_request`
- Supports email OTP, passkeys, Google SSO, and GitHub SSO
- Auto-approves users from trusted domains and sends everyone else into pending approval
- Lets admins manage users, apps, domains, bans, branding, and audit logs from one place
- Keeps your auth data on your infrastructure

## Typical flow

1. A user visits `https://docs.example.com`.
2. nginx makes a subrequest to Gatekeeper at `/api/v1/auth/validate`.
3. If the user is not signed in, nginx redirects them to `https://auth.example.com/signin`.
4. The user proves identity with OTP, passkey, Google, or GitHub.
5. If their account is approved, Gatekeeper sets a session cookie and redirects them back.
6. If their account is pending, Gatekeeper records the attempt and waits for admin approval.

## Operational model

Gatekeeper works best when:

- `auth.example.com` is your dedicated auth host
- internal apps live on sibling subdomains such as `docs.example.com` or `grafana.example.com`
- `COOKIE_DOMAIN=.example.com` is set for cross-subdomain SSO
- auth and internal app domains send `X-Robots-Tag: noindex, nofollow, noarchive`
- production deploys use `PUBLIC_API_DOCS=false` and a tight `TRUSTED_PROXY_IPS` list

## Start here

::::{grid} 1 2 2 2
:gutter: 3

:::{grid-item-card} Getting Started
:link: getting-started/index
:link-type: doc

Install Gatekeeper, configure email and domains, create your first admin, and protect your first app.
:::

:::{grid-item-card} Guides
:link: guides/index
:link-type: doc

Operational guides for users, apps, deployment, audit logs, and SSO providers.
:::

:::{grid-item-card} Reference
:link: reference/index
:link-type: doc

Current CLI, API, and environment reference for the running product.
:::

::::

```{toctree}
:hidden:
:maxdepth: 2

getting-started/index
guides/index
reference/index
```
