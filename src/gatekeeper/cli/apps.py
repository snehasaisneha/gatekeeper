"""App management CLI commands."""

import re
import uuid
from typing import Annotated

import typer
from rich.table import Table
from sqlalchemy import select

from gatekeeper.cli._helpers import console, err_console, run_async
from gatekeeper.database import async_session_maker
from gatekeeper.models.app import App, UserAppAccess
from gatekeeper.models.user import User

app = typer.Typer(no_args_is_help=True, help="App management commands.")


@app.command()
@run_async
async def add(
    slug: Annotated[str, typer.Option("--slug", "-s", help="URL-safe app identifier")],
    name: Annotated[str, typer.Option("--name", "-n", help="Display name for the app")],
):
    """Register a new app."""
    slug = slug.lower().strip()

    if not re.match(r"^[a-z0-9-]+$", slug):
        err_console.print(f"[red]Error:[/red] Invalid slug format: {slug}")
        err_console.print("Slug must contain only lowercase letters, numbers, and hyphens")
        raise typer.Exit(code=1)

    async with async_session_maker() as db:
        stmt = select(App).where(App.slug == slug)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            err_console.print(f"[red]Error:[/red] App with slug '{slug}' already exists")
            raise typer.Exit(code=1)

        new_app = App(id=uuid.uuid4(), slug=slug, name=name)
        db.add(new_app)
        await db.commit()
        console.print(f"[green]\u2713[/green] Created app: {slug} ({name})")


@app.command("list")
@run_async
async def list_apps():
    """List all registered apps."""
    async with async_session_maker() as db:
        stmt = select(App).order_by(App.created_at.desc())
        result = await db.execute(stmt)
        apps = result.scalars().all()

        if not apps:
            console.print("No apps registered.")
            return

        table = Table(title="Apps")
        table.add_column("Slug", style="cyan")
        table.add_column("Name")
        table.add_column("Users")
        table.add_column("Created")

        for a in apps:
            # Count users with access
            count_stmt = select(UserAppAccess).where(UserAppAccess.app_id == a.id)
            count_result = await db.execute(count_stmt)
            user_count = len(count_result.scalars().all())

            table.add_row(
                a.slug,
                a.name,
                str(user_count),
                f"{a.created_at:%Y-%m-%d}",
            )

        console.print(table)
        console.print(f"\nTotal: {len(apps)} app(s)")


@app.command()
@run_async
async def show(
    slug: Annotated[str, typer.Option("--slug", "-s", help="App slug to show")],
):
    """Show app details and users with access."""
    slug = slug.lower().strip()

    async with async_session_maker() as db:
        stmt = select(App).where(App.slug == slug)
        result = await db.execute(stmt)
        app_obj = result.scalar_one_or_none()

        if not app_obj:
            err_console.print(f"[red]Error:[/red] App '{slug}' not found")
            raise typer.Exit(code=1)

        console.print(f"\n[bold]{app_obj.name}[/bold] ({app_obj.slug})")
        console.print(f"Created: {app_obj.created_at:%Y-%m-%d %H:%M}")
        console.print()

        # Get users with access
        access_stmt = (
            select(UserAppAccess, User)
            .join(User, UserAppAccess.user_id == User.id)
            .where(UserAppAccess.app_id == app_obj.id)
            .order_by(UserAppAccess.granted_at.desc())
        )
        access_result = await db.execute(access_stmt)
        access_rows = access_result.all()

        if not access_rows:
            console.print("No users have access to this app.")
            return

        table = Table(title="Users with Access")
        table.add_column("Email", style="cyan")
        table.add_column("Name")
        table.add_column("Role")
        table.add_column("Granted")
        table.add_column("Granted By")

        for access, user in access_rows:
            table.add_row(
                user.email,
                user.name or "-",
                access.role or "-",
                f"{access.granted_at:%Y-%m-%d}",
                access.granted_by or "-",
            )

        console.print(table)
        console.print(f"\n{len(access_rows)} user(s) with access")


@app.command()
@run_async
async def grant(
    slug: Annotated[str, typer.Option("--slug", "-s", help="App slug")],
    email: Annotated[
        str | None, typer.Option("--email", "-e", help="User email to grant access")
    ] = None,
    role: Annotated[
        str | None, typer.Option("--role", "-r", help="Role to assign (optional)")
    ] = None,
    all_approved: Annotated[
        bool, typer.Option("--all-approved", help="Grant access to all approved users")
    ] = False,
):
    """Grant a user access to an app."""
    if not email and not all_approved:
        err_console.print("[red]Error:[/red] Provide --email or --all-approved")
        raise typer.Exit(code=1)

    slug = slug.lower().strip()

    async with async_session_maker() as db:
        # Find app
        app_stmt = select(App).where(App.slug == slug)
        app_result = await db.execute(app_stmt)
        app_obj = app_result.scalar_one_or_none()

        if not app_obj:
            err_console.print(f"[red]Error:[/red] App '{slug}' not found")
            raise typer.Exit(code=1)

        if all_approved:
            from gatekeeper.models.user import UserStatus

            # Get all approved users
            users_stmt = select(User).where(User.status == UserStatus.APPROVED)
            users_result = await db.execute(users_stmt)
            users = users_result.scalars().all()

            granted = 0
            for user in users:
                # Check if already has access
                existing_stmt = select(UserAppAccess).where(
                    UserAppAccess.user_id == user.id,
                    UserAppAccess.app_id == app_obj.id,
                )
                existing_result = await db.execute(existing_stmt)
                if existing_result.scalar_one_or_none():
                    continue

                access = UserAppAccess(
                    user_id=user.id,
                    app_id=app_obj.id,
                    role=role,
                    granted_by="CLI",
                )
                db.add(access)
                granted += 1

            await db.commit()
            role_msg = f" with role '{role}'" if role else ""
            console.print(
                f"[green]\u2713[/green] Granted access to '{slug}' for {granted} user(s){role_msg}"
            )
        else:
            email = email.lower().strip()

            # Find user
            user_stmt = select(User).where(User.email == email)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()

            if not user:
                err_console.print(f"[red]Error:[/red] User '{email}' not found")
                raise typer.Exit(code=1)

            # Check existing access
            existing_stmt = select(UserAppAccess).where(
                UserAppAccess.user_id == user.id,
                UserAppAccess.app_id == app_obj.id,
            )
            existing_result = await db.execute(existing_stmt)
            existing = existing_result.scalar_one_or_none()

            if existing:
                if existing.role != role:
                    existing.role = role
                    existing.granted_by = "CLI"
                    await db.commit()
                    role_msg = f" with role '{role}'" if role else " (no role)"
                    console.print(
                        f"[green]\u2713[/green] Updated access for '{email}' on '{slug}'{role_msg}"
                    )
                else:
                    console.print(f"User '{email}' already has access to '{slug}'")
                return

            access = UserAppAccess(
                user_id=user.id,
                app_id=app_obj.id,
                role=role,
                granted_by="CLI",
            )
            db.add(access)
            await db.commit()
            role_msg = f" with role '{role}'" if role else ""
            console.print(
                f"[green]\u2713[/green] Granted access to '{slug}' for '{email}'{role_msg}"
            )


@app.command()
@run_async
async def revoke(
    slug: Annotated[str, typer.Option("--slug", "-s", help="App slug")],
    email: Annotated[str, typer.Option("--email", "-e", help="User email to revoke access")],
):
    """Revoke a user's access to an app."""
    slug = slug.lower().strip()
    email = email.lower().strip()

    async with async_session_maker() as db:
        # Find app
        app_stmt = select(App).where(App.slug == slug)
        app_result = await db.execute(app_stmt)
        app_obj = app_result.scalar_one_or_none()

        if not app_obj:
            err_console.print(f"[red]Error:[/red] App '{slug}' not found")
            raise typer.Exit(code=1)

        # Find user
        user_stmt = select(User).where(User.email == email)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if not user:
            err_console.print(f"[red]Error:[/red] User '{email}' not found")
            raise typer.Exit(code=1)

        # Find and delete access
        access_stmt = select(UserAppAccess).where(
            UserAppAccess.user_id == user.id,
            UserAppAccess.app_id == app_obj.id,
        )
        access_result = await db.execute(access_stmt)
        access = access_result.scalar_one_or_none()

        if not access:
            err_console.print(f"[red]Error:[/red] User '{email}' does not have access to '{slug}'")
            raise typer.Exit(code=1)

        await db.delete(access)
        await db.commit()
        console.print(f"[green]\u2713[/green] Revoked access to '{slug}' for '{email}'")


@app.command()
@run_async
async def remove(
    slug: Annotated[str, typer.Option("--slug", "-s", help="App slug to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation prompt")] = False,
):
    """Remove an app and all associated access grants."""
    slug = slug.lower().strip()

    if not force:
        confirm = typer.confirm(f"Remove app '{slug}'? This revokes all user access grants.")
        if not confirm:
            console.print("Aborted.")
            raise typer.Exit()

    async with async_session_maker() as db:
        stmt = select(App).where(App.slug == slug)
        result = await db.execute(stmt)
        app_obj = result.scalar_one_or_none()

        if not app_obj:
            err_console.print(f"[red]Error:[/red] App '{slug}' not found")
            raise typer.Exit(code=1)

        await db.delete(app_obj)
        await db.commit()
        console.print(f"[green]\u2713[/green] Removed app: {slug}")
