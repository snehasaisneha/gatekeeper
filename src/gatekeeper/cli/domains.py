"""Domain management CLI commands."""

import uuid
from typing import Annotated

import typer
from rich.table import Table
from sqlalchemy import select

from gatekeeper.cli._helpers import console, err_console, run_async
from gatekeeper.database import async_session_maker
from gatekeeper.models.domain import ApprovedDomain

app = typer.Typer(no_args_is_help=True, help="Approved domain management commands.")


@app.command("list")
@run_async
async def list_domains():
    """List all approved domains."""
    async with async_session_maker() as db:
        stmt = select(ApprovedDomain).order_by(ApprovedDomain.created_at.desc())
        result = await db.execute(stmt)
        domains = result.scalars().all()

        if not domains:
            console.print("No approved domains.")
            return

        table = Table(title="Approved Domains")
        table.add_column("Domain", style="cyan")
        table.add_column("Created")
        table.add_column("Created By")

        for d in domains:
            table.add_row(
                d.domain,
                f"{d.created_at:%Y-%m-%d}",
                d.created_by or "-",
            )

        console.print(table)
        console.print(f"\nTotal: {len(domains)} domain(s)")


@app.command()
@run_async
async def add(
    domain: Annotated[str, typer.Option("--domain", "-d", help="Domain to approve")],
):
    """Add a domain to the approved list.

    Users with emails from approved domains are considered internal
    and automatically have access to all apps.
    """
    domain = domain.lower().strip()

    # Basic domain validation
    if not domain or "." not in domain or domain.startswith(".") or domain.endswith("."):
        err_console.print(f"[red]Error:[/red] Invalid domain format: {domain}")
        raise typer.Exit(code=1)

    async with async_session_maker() as db:
        stmt = select(ApprovedDomain).where(ApprovedDomain.domain == domain)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            err_console.print(f"[red]Error:[/red] Domain '{domain}' is already approved")
            raise typer.Exit(code=1)

        new_domain = ApprovedDomain(
            id=uuid.uuid4(),
            domain=domain,
            created_by="CLI",
        )
        db.add(new_domain)
        await db.commit()
        console.print(f"[green]\u2713[/green] Added approved domain: {domain}")


@app.command()
@run_async
async def remove(
    domain: Annotated[str, typer.Option("--domain", "-d", help="Domain to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation prompt")] = False,
):
    """Remove a domain from the approved list.

    Users from this domain will become external users
    and will need explicit app access grants.
    """
    domain = domain.lower().strip()

    if not force:
        confirm = typer.confirm(
            f"Remove domain '{domain}'? Users from this domain will become external users."
        )
        if not confirm:
            console.print("Aborted.")
            raise typer.Exit()

    async with async_session_maker() as db:
        stmt = select(ApprovedDomain).where(ApprovedDomain.domain == domain)
        result = await db.execute(stmt)
        domain_obj = result.scalar_one_or_none()

        if not domain_obj:
            err_console.print(f"[red]Error:[/red] Domain '{domain}' not found in approved list")
            raise typer.Exit(code=1)

        await db.delete(domain_obj)
        await db.commit()
        console.print(f"[green]\u2713[/green] Removed approved domain: {domain}")
