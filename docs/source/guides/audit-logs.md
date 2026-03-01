# Audit Logs

Gatekeeper maintains a comprehensive audit log of authentication and administrative events for security and compliance purposes.

## What's logged

### Authentication events

| Event | Description |
|-------|-------------|
| `auth.signin.otp_sent` | OTP code requested |
| `auth.signin.otp_success` | OTP verification successful |
| `auth.signin.otp_failed` | OTP verification failed |
| `auth.signin.google` | Google SSO sign-in successful |
| `auth.signin.github` | GitHub SSO sign-in successful |
| `auth.signin.passkey` | Passkey sign-in successful |
| `auth.signin.failed` | Any sign-in method failed |
| `auth.signout` | User signed out |

### Admin events

| Event | Description |
|-------|-------------|
| `admin.user.created` | Admin created a user |
| `admin.user.approved` | Admin approved a pending user |
| `admin.user.rejected` | Admin rejected a user |
| `admin.user.deleted` | Admin deleted a user |
| `admin.user.updated` | Admin modified user settings |
| `admin.app.created` | App registered |
| `admin.app.updated` | App settings changed |
| `admin.app.deleted` | App removed |
| `admin.access.granted` | User granted app access |
| `admin.access.revoked` | User access revoked |
| `admin.domain.added` | Approved domain added |
| `admin.domain.removed` | Approved domain removed |

## Log structure

Each audit log entry contains:

```json
{
  "id": "uuid",
  "timestamp": "2024-01-15T10:30:00Z",
  "actor_id": "user-uuid",
  "actor_email": "user@example.com",
  "event_type": "auth.signin.google",
  "target_type": "user",
  "target_id": "target-uuid",
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "details": {
    "method": "google",
    "device": {
      "browser": "Chrome",
      "os": "macOS",
      "type": "desktop"
    }
  }
}
```

## Querying logs

### API

Admins can query logs via the API:

```bash
# List recent logs
curl -X GET "https://auth.example.com/api/v1/admin/audit-logs" \
  -H "Cookie: session=..."

# Filter by event type
curl -X GET "https://auth.example.com/api/v1/admin/audit-logs?event_type=auth.signin" \
  -H "Cookie: session=..."

# Filter by user
curl -X GET "https://auth.example.com/api/v1/admin/audit-logs?actor_email=user@example.com" \
  -H "Cookie: session=..."

# Filter by time range
curl -X GET "https://auth.example.com/api/v1/admin/audit-logs?since=2024-01-01T00:00:00Z&until=2024-01-31T23:59:59Z" \
  -H "Cookie: session=..."
```

### Query parameters

| Parameter | Description |
|-----------|-------------|
| `page` | Page number (default: 1) |
| `page_size` | Items per page (default: 50, max: 100) |
| `event_type` | Filter by event type prefix (e.g., `auth.signin`) |
| `actor_email` | Filter by actor email |
| `target_type` | Filter by target type (`user`, `app`, `domain`) |
| `since` | Events after this timestamp (ISO 8601) |
| `until` | Events before this timestamp (ISO 8601) |

## Data retention

Audit logs are stored in the database indefinitely by default. For compliance or storage reasons, you may want to implement a retention policy.

To manually clean old logs:

```sql
-- Delete logs older than 1 year
DELETE FROM audit_logs WHERE timestamp < datetime('now', '-1 year');
```

## Security considerations

- Audit logs are append-only — events cannot be modified or deleted through the API
- Only super admins can view audit logs
- Actor information is denormalized (email stored directly) so logs remain meaningful even if users are deleted
- IP addresses are captured respecting `X-Forwarded-For` headers (set by reverse proxies)
