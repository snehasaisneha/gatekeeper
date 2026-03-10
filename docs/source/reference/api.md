# API reference

Gatekeeper exposes a FastAPI API under `/api/v1`.

## Live docs

- Swagger UI: `/api/v1`
- OpenAPI JSON: `/api/v1/openapi.json`

## Main route groups

## Authentication

Common routes:

- `GET /api/v1/auth/validate`: nginx `auth_request` validation endpoint
- `POST /api/v1/auth/signin`: start OTP sign-in / create a pending-or-approved user if needed
- `POST /api/v1/auth/signin/verify`: complete OTP sign-in or enter pending approval
- `POST /api/v1/auth/signout`: clear the active session
- `GET /api/v1/auth/me`: current approved user
- `PATCH /api/v1/auth/me`: profile and notification preferences
- `GET /api/v1/auth/me/apps`: list the current user's app access
- passkey routes under `/api/v1/auth/passkey/...`
- Google OAuth routes under `/api/v1/auth/google/...`
- GitHub OAuth routes under `/api/v1/auth/github/...`
- branding/provider status routes under `/api/v1/auth/...`

## Admin

Common routes:

- domain management under `/api/v1/admin/domains`
- user listing/detail/update under `/api/v1/admin/users`
- pending approval list under `/api/v1/admin/users/pending`
- explicit approve/reject actions under `/api/v1/admin/users/{user_id}/approve` and `/reject`
- app management under `/api/v1/admin/apps`
- access grant/revoke routes under `/api/v1/admin/apps/...`
- audit log listing under `/api/v1/admin/audit-logs`
- deployment config and branding routes under `/api/v1/admin/...`

## Security admin

Security routes live under `/api/v1/admin/security`.

These include:

- dashboard stats
- banned IP listing / creation / unban
- banned email listing / creation / unban
- security event listing

## Response and access model

- most auth routes are public or session-based
- admin routes require an approved admin user
- auth cookies are HTTP-only session cookies
- nginx is expected to forward `Cookie`, `Host`, `X-Forwarded-For`, and app context headers as appropriate

## Important operational notes

- The interactive docs are at `/api/v1`, not `/docs`.
- The root `/` redirects to the API docs endpoint.
- Security-relevant pre-approval activity now appears in audit/security flows, not just successful login flows.

For exact request and response schemas, use the live OpenAPI docs from the running deployment.
