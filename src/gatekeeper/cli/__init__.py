"""Gatekeeper CLI - manage users, apps, and operations."""

import typer

from gatekeeper.cli.apps import app as apps_app
from gatekeeper.cli.ops import app as ops_app
from gatekeeper.cli.users import app as users_app

app = typer.Typer(
    name="gk",
    help="Gatekeeper CLI - manage users, apps, and operations.",
    no_args_is_help=True,
)

app.add_typer(users_app, name="users", help="User management commands.")
app.add_typer(apps_app, name="apps", help="App management commands.")
app.add_typer(ops_app, name="ops", help="Operational commands.")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
