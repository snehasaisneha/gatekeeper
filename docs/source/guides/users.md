# Managing users

Gatekeeper has three user states:

- `pending`: identity was established, but an admin has not approved access yet
- `approved`: the user can sign in and access apps they are entitled to
- `rejected`: the user is denied and cannot sign in

## How users enter the system

Gatekeeper does not rely on a separate long-lived registration flow. Users typically enter through the normal sign-in flow:

1. the user visits `/signin`
2. they authenticate with OTP, passkey, Google, or GitHub
3. Gatekeeper either:
   - auto-approves them if their email domain is trusted
   - moves them into `pending`
   - blocks them if they were already rejected/banned

## Internal vs external users

Users from `ACCEPTED_DOMAINS` are treated as internal.

Internal users:

- are auto-approved on first successful identity proof
- generally do not need per-app grants for normal internal app access

External users:

- enter `pending` unless an admin created or approved them
- need explicit app access for registered apps

## Creating users manually

### CLI

```bash
uv run gk users add --email alice@example.com
uv run gk users add --email admin@example.com --admin
uv run gk users add --email founder@example.com --admin --seeded
```

Notes:

- plain `add` creates a pending user and attempts to send an invitation
- `--seeded` creates an already-approved user
- `--admin` grants admin privileges

### Admin UI

Admins can also create, approve, reject, and update users from `/admin`.

## Listing and filtering users

```bash
uv run gk users list
uv run gk users list --status pending
uv run gk users list --status approved
uv run gk users list --status rejected
uv run gk users list --admins-only
```

## Approving users

```bash
uv run gk users approve --email alice@example.com
uv run gk users approve --all-pending
```

Approving a user moves them to `approved` and allows future sign-in to create a session.

## Rejecting users

```bash
uv run gk users reject --email spammer@example.com
```

From the admin API/UI, rejecting a pending user is also part of the security flow:

- the email is banned
- Gatekeeper attempts to find and ban the associated source IP
- the action is recorded in audit/security logs

This is most useful for spam sign-ups and disposable identities.

## Security flow for bad sign-in attempts

Gatekeeper records security-relevant sign-in attempts before approval too:

- users who prove identity but land in `pending approval`
- users whose OTP delivery fails
- users who fail sign-in checks
- rejected or banned users attempting to sign in again

That data is intended to feed the security dashboard and ban decisions, not just the happy path.

## Updating users

```bash
uv run gk users update --email alice@example.com --name "Alice Smith"
uv run gk users update --email alice@example.com --admin
uv run gk users update --email alice@example.com --no-admin
```

Admins can also update notification preferences from the UI/API.

## Removing users

```bash
uv run gk users remove --email alice@example.com --force
```

Removing a user deletes the account and associated auth data such as sessions and passkeys.

## Resetting sessions

```bash
uv run gk ops reset-sessions --email alice@example.com
uv run gk ops reset-sessions
```

Use this if:

- a device is lost
- a session cookie may have leaked
- you changed access policy and want fresh login enforcement

## Operational recommendations

- Keep `ACCEPTED_DOMAINS` small and explicit.
- Review pending users from unknown domains promptly.
- Treat rejection as a security action, not just a workflow step.
- For internal-only deployments, add `noindex` headers on auth and app domains so user names and app names do not appear in search results.
