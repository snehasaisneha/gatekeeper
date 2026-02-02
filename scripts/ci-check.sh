#!/usr/bin/env bash
# Run all CI checks locally before pushing
set -e

echo "=== Lint ==="
uv run ruff check .
uv run ruff format --check .

echo "=== Tests ==="
uv run pytest --tb=short -q

echo "=== CLI Smoke Test ==="
uv run gk --help > /dev/null
uv run gk users --help > /dev/null
uv run gk apps --help > /dev/null
uv run gk ops --help > /dev/null

echo "=== Frontend Build ==="
npm -C frontend install --silent
npm -C frontend run build

echo "=== Docs Build ==="
uv sync --group docs --quiet
uv run sphinx-build -b html -c docs docs/source docs/_build/html -W --keep-going -q

echo "=== All checks passed ==="
