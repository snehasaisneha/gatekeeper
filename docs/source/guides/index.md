# Guides

These guides cover the operational parts of running Gatekeeper.

## Identity and access

- [Managing users](users.md): approvals, rejection, internal vs external users, and session handling
- [Managing apps](apps.md): app registration, grants, roles, and nginx integration
- [Google SSO](google-sso.md): provider setup and redirect details
- [GitHub SSO](github-sso.md): provider setup and verified-email behavior

## Operations

- [Deployment](deployment.md): production topology, nginx, systemd, and noindex guidance
- [Rollout checklist](rollouts.md): step-by-step production rollout and verification sequence
- [Email setup](email.md): SMTP and SES configuration
- [Audit logs](audit-logs.md): auth/admin/security event visibility

```{toctree}
:hidden:

users
apps
google-sso
github-sso
email
deployment
rollouts
audit-logs
```
