"""User management CLI commands."""

import contextlib
from enum import Enum
from typing import Annotated

import typer
from rich.table import Table
from sqlalchemy import select

from gatekeeper.cli._helpers import console, err_console, run_async
from gatekeeper.database import async_session_maker
from gatekeeper.models.user import User, UserStatus
from gatekeeper.services.email import EmailService

app = typer.Typer(no_args_is_help=True, help="User management commands.")


class StatusFilter(str, Enum):
    all = "all"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


@app.command()
@run_async
async def add(
    email: Annotated[str, typer.Option("--email", "-e", help="User email address")],
    admin: Annotated[bool, typer.Option("--admin", "-a", help="Grant admin privileges")] = False,
    seeded: Annotated[
        bool, typer.Option("--seeded", "-s", help="Auto-approve, skip invitation email")
    ] = False,
    name: Annotated[str | None, typer.Option("--name", "-n", help="User display name")] = None,
):
    """Add a user to Gatekeeper."""
    email = email.lower().strip()

    async with async_session_maker() as db:
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            err_console.print(
                f"[red]Error:[/red] User {email} already exists (status: {existing.status.value})"
            )
            raise typer.Exit(code=1)

        user = User(
            email=email,
            name=name,
            is_admin=admin,
            is_seeded=seeded,
            status=UserStatus.APPROVED if seeded else UserStatus.PENDING,
        )
        db.add(user)
        await db.commit()

        if not seeded:
            try:
                email_service = EmailService(db=db)
                await email_service.send_invitation(email, "CLI")
                console.print(
                    f"[green]\u2713[/green] Created user {email} (pending). Invitation email sent."
                )
            except Exception as e:
                console.print(
                    f"[yellow]⚠[/yellow] Created user {email} (pending). Failed to send email: {e}"
                )
        else:
            role = " [bold]Admin.[/bold]" if admin else ""
            console.print(f"[green]\u2713[/green] Created user {email} (approved, seeded).{role}")


@app.command("list")
@run_async
async def list_users(
    status: Annotated[
        StatusFilter, typer.Option("--status", help="Filter by status")
    ] = StatusFilter.all,
    admins_only: Annotated[bool, typer.Option("--admins-only", help="Show only admins")] = False,
    csv: Annotated[bool, typer.Option("--csv", help="Output as CSV for export")] = False,
):
    """List all users in the system."""
    async with async_session_maker() as db:
        stmt = select(User).order_by(User.created_at.desc())

        if status != StatusFilter.all:
            stmt = stmt.where(User.status == UserStatus(status.value))

        if admins_only:
            stmt = stmt.where(User.is_admin == True)  # noqa: E712

        result = await db.execute(stmt)
        users = result.scalars().all()

        if csv:
            console.print("email,name,status,admin,created")
            for u in users:
                name = u.name or ""
                admin = "yes" if u.is_admin else "no"
                created = f"{u.created_at:%Y-%m-%d}"
                console.print(f"{u.email},{name},{u.status.value},{admin},{created}")
            return

        table = Table(title="Users")
        table.add_column("Email", style="cyan")
        table.add_column("Name")
        table.add_column("Status")
        table.add_column("Admin")
        table.add_column("Created")

        for u in users:
            status_style = {
                "approved": "green",
                "pending": "yellow",
                "rejected": "red",
            }.get(u.status.value, "")
            table.add_row(
                u.email,
                u.name or "-",
                f"[{status_style}]{u.status.value}[/{status_style}]",
                "yes" if u.is_admin else "no",
                f"{u.created_at:%Y-%m-%d}",
            )
        console.print(table)

        # Summary
        by_status: dict[str, int] = {}
        for u in users:
            by_status[u.status.value] = by_status.get(u.status.value, 0) + 1
        summary = ", ".join(f"{v} {k}" for k, v in by_status.items())
        console.print(f"\n{len(users)} users ({summary})")


@app.command()
@run_async
async def approve(
    email: Annotated[
        str | None, typer.Option("--email", "-e", help="User email to approve")
    ] = None,
    all_pending: Annotated[
        bool, typer.Option("--all-pending", help="Approve all pending users")
    ] = False,
):
    """Approve a pending user registration."""
    if not email and not all_pending:
        err_console.print("[red]Error:[/red] Provide --email or --all-pending")
        raise typer.Exit(code=1)

    async with async_session_maker() as db:
        if all_pending:
            stmt = select(User).where(User.status == UserStatus.PENDING)
            result = await db.execute(stmt)
            users = result.scalars().all()

            for u in users:
                u.status = UserStatus.APPROVED

            await db.commit()

            # Send emails
            email_service = EmailService(db=db)
            for u in users:
                with contextlib.suppress(Exception):
                    await email_service.send_registration_approved(u.email)

            console.print(f"[green]\u2713[/green] Approved {len(users)} user(s).")
        else:
            email = email.lower().strip()
            stmt = select(User).where(User.email == email)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                err_console.print(f"[red]Error:[/red] User {email} not found.")
                raise typer.Exit(code=1)

            if user.status != UserStatus.PENDING:
                err_console.print(f"[red]Error:[/red] User is already {user.status.value}.")
                raise typer.Exit(code=1)

            user.status = UserStatus.APPROVED
            await db.commit()

            try:
                email_service = EmailService(db=db)
                await email_service.send_registration_approved(email)
            except Exception:
                pass  # Best effort

            console.print(f"[green]\u2713[/green] Approved {email}.")


@app.command()
@run_async
async def reject(
    email: Annotated[str, typer.Option("--email", "-e", help="User email to reject")],
):
    """Reject a pending user registration."""
    email = email.lower().strip()

    async with async_session_maker() as db:
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            err_console.print(f"[red]Error:[/red] User {email} not found.")
            raise typer.Exit(code=1)

        if user.status != UserStatus.PENDING:
            err_console.print(f"[red]Error:[/red] User is already {user.status.value}.")
            raise typer.Exit(code=1)

        user.status = UserStatus.REJECTED
        await db.commit()
        console.print(f"[green]\u2713[/green] Rejected {email}.")


@app.command()
@run_async
async def remove(
    email: Annotated[str, typer.Option("--email", "-e", help="User email to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation prompt")] = False,
):
    """Remove a user and all their data (sessions, passkeys, OTPs)."""
    email = email.lower().strip()

    if not force:
        confirm = typer.confirm(
            f"Remove user {email}? This deletes their account, sessions, and passkeys."
        )
        if not confirm:
            console.print("Aborted.")
            raise typer.Exit()

    async with async_session_maker() as db:
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            err_console.print(f"[red]Error:[/red] User {email} not found.")
            raise typer.Exit(code=1)

        if user.is_seeded:
            err_console.print(
                "[red]Error:[/red] Cannot remove seeded admin. Use --force with caution."
            )
            if not force:
                raise typer.Exit(code=1)

        await db.delete(user)
        await db.commit()
        console.print(f"[green]\u2713[/green] Removed {email} and all associated data.")


@app.command()
@run_async
async def update(
    email: Annotated[str, typer.Option("--email", "-e", help="User email to update")],
    admin: Annotated[
        bool | None, typer.Option("--admin/--no-admin", help="Set admin status")
    ] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Set display name")] = None,
):
    """Update a user's profile or admin status."""
    email = email.lower().strip()

    if admin is None and name is None:
        err_console.print("[red]Error:[/red] Provide at least one field to update.")
        raise typer.Exit(code=1)

    async with async_session_maker() as db:
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            err_console.print(f"[red]Error:[/red] User {email} not found.")
            raise typer.Exit(code=1)

        if admin is not None:
            user.is_admin = admin

        if name is not None:
            user.name = name

        await db.commit()
        console.print(f"[green]\u2713[/green] Updated {email}.")
