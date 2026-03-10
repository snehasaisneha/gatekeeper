# CLI reference

Gatekeeper ships a Typer CLI exposed as `gk`.

Run help at any level with:

```bash
uv run gk --help
uv run gk users --help
uv run gk apps --help
uv run gk domains --help
uv run gk ops --help
```

## Users

```bash
uv run gk users add --email EMAIL [--admin] [--seeded] [--name NAME]
uv run gk users list [--status all|pending|approved|rejected] [--admins-only] [--csv]
uv run gk users approve --email EMAIL
uv run gk users approve --all-pending
uv run gk users reject --email EMAIL
uv run gk users update --email EMAIL [--name NAME] [--admin | --no-admin]
uv run gk users remove --email EMAIL [--force]
```

## Apps

```bash
uv run gk apps add --slug SLUG --name NAME
uv run gk apps list
uv run gk apps show --slug SLUG
uv run gk apps grant --slug SLUG --email EMAIL [--role ROLE]
uv run gk apps grant --slug SLUG --all-approved [--role ROLE]
uv run gk apps revoke --slug SLUG --email EMAIL
uv run gk apps remove --slug SLUG [--force]
```

## Domains

```bash
uv run gk domains list
uv run gk domains add --domain example.com
uv run gk domains remove --domain example.com [--force]
```

## Operations

```bash
uv run gk ops serve [--host HOST] [--port PORT] [--reload | --no-reload] [--workers N]
uv run gk ops healthcheck
uv run gk ops reset-sessions [--email EMAIL]
uv run gk ops test-email --to EMAIL
```

## Migrations

Project-level shortcuts from `pyproject.toml`:

```bash
uv run all-migrations
uv run migrations --name 011_add_security_tables
```

## Notes

- `gk users add` creates a pending user unless you pass `--seeded`.
- `gk apps grant --all-approved` is useful when you want a broadly available internal app.
- `gk ops serve --workers N` disables reload mode when `N > 1`.
- Use `uv run all-migrations` rather than calling the migration module directly.
