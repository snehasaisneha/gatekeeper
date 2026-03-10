# Audit logs

Gatekeeper records authentication, admin, and security events in `audit_logs`.

## Why this matters

The audit trail is not only for successful sign-ins. It is also part of the abuse-review path for:

- pending approval attempts
- failed sign-in attempts
- banned IP blocks
- email and IP bans created during rejection or manual review

## Common event families

### Auth events

- `auth.signin.otp_sent`
- `auth.signin.otp_success`
- `auth.signin.google`
- `auth.signin.github`
- `auth.signin.passkey`
- `auth.signin.failed`
- `auth.identity.pending_approval`
- `auth.signout`

### Admin events

- `admin.user.created`
- `admin.user.approved`
- `admin.user.rejected`
- `admin.user.updated`
- `admin.user.deleted`
- `admin.app.created`
- `admin.app.updated`
- `admin.app.deleted`
- `admin.access.granted`
- `admin.access.revoked`
- `admin.domain.added`
- `admin.domain.removed`

### Security events

- `security.blocked.banned_ip`
- `security.email.banned.rejected`
- `security.ip.banned.cross`
- manual ban/unban events from the security admin endpoints

## Stored fields

Audit records include:

- timestamp
- actor id/email
- event type
- target type/id when relevant
- source IP
- user agent
- event details payload

For sign-in events, Gatekeeper also records lightweight device parsing in the event details when a user agent is available.

## How to view logs

### Admin UI

Use the admin dashboard for recent activity and security review.

### API

The admin API exposes audit log listing and filtering. Interactive docs are available at:

- `/api/v1`
- `/api/v1/openapi.json`

Example:

```bash
curl -H "Cookie: session=..." \
  "https://auth.example.com/api/v1/admin/audit-logs?page=1&page_size=50"
```

## How to use the logs operationally

- Review `auth.identity.pending_approval` events to see who is proving identity but waiting for access.
- Review `auth.signin.failed` events for typo-heavy, bot-heavy, or suppressed-email patterns.
- When rejecting spam users, confirm that the associated email and IP bans were created.
- Use source IP data to distinguish one noisy bot from a shared internal NAT address.

## Retention

Gatekeeper does not currently implement built-in retention policies. If you need one, apply it at the database/ops layer.

Example SQLite cleanup:

```sql
DELETE FROM audit_logs
WHERE timestamp < datetime('now', '-180 days');
```

Apply retention cautiously if you rely on old abuse patterns during investigations.
