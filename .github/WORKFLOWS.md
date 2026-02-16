# GitHub Actions CI

This directory contains the CI/CD workflows for Gatekeeper.

## Workflows

| Workflow | Triggers | Purpose |
|----------|----------|---------|
| **Smoke Test** | All PRs, push to main | Comprehensive build verification for backend and frontend |
| **Lint** | Changes to `**.py`, `pyproject.toml` | Ruff linter and formatter checks |
| **Test** | Changes to `src/**`, `tests/**`, `pyproject.toml`, `uv.lock` | Pytest suite |
| **Docs** | Changes to `docs/**`, `pyproject.toml`, `uv.lock`, `.readthedocs.yaml` | Sphinx documentation build |
| **Deps Check** | Changes to `pyproject.toml`, `uv.lock` | Verify lockfile is in sync |

## Smoke Test

The smoke test is the primary gatekeeper (pun intended) for all PRs. It runs on every pull request regardless of which files changed, ensuring both backend and frontend always build correctly.

**Backend checks:**
- CLI loads (`gk --help`)
- All subcommands available (`gk users`, `gk apps`, `gk ops`)
- Server starts and responds to health checks

**Frontend checks:**
- Dependencies install cleanly
- Production build succeeds

## Path-Based Filtering

Specialized workflows (Lint, Test, Docs, Deps Check) use path-based filtering to avoid unnecessary runs:

- **Lint** only runs when Python files change
- **Test** only runs when source or test files change
- **Docs** only runs when documentation files change
- **Deps Check** only runs when dependency files change

The **Smoke Test** always runs on PRs to catch integration issues regardless of which component changed.

## Local Verification

Before pushing, run the local CI check script which mirrors all CI checks:

```bash
./scripts/ci-check.sh
```

This runs: lint, tests, CLI smoke tests, frontend build, and docs build.

## Python Version Management

All Python workflows use [astral-sh/setup-uv](https://github.com/astral-sh/setup-uv) to install uv. When `uv sync` or `uv run` executes, uv automatically reads `.python-version` and installs the correct Python version if needed. This eliminates the need for both `actions/setup-python` and explicit version configuration in the workflow.

## Concurrency

All workflows use concurrency groups to cancel in-progress runs when new commits are pushed to the same branch:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```
