"""Operational CLI commands."""

from typing import Annotated

import typer
from sqlalchemy import delete, func, select, text

from gatekeeper.cli._helpers import console, err_console, run_async
from gatekeeper.config import get_settings
from gatekeeper.database import async_session_maker
from gatekeeper.models.session import Session
from gatekeeper.models.user import User

app = typer.Typer(no_args_is_help=True, help="Operational commands.")

settings = get_settings()


@app.command("test-email")
@run_async
async def test_email(
    to: Annotated[str, typer.Option("--to", help="Recipient email address")],
):
    """Send a test email to verify email configuration."""
    async with async_session_maker() as db:
        try:
            from gatekeeper.services.email import EmailService

            email_service = EmailService(db=db)

            # Use a simple test method
            sent = await email_service._send_email(
                to=to,
                subject=f"[{settings.app_name}] Test Email",
                body_text=(
                    "This is a test email from Gatekeeper.\n\n"
                    "If you're reading this, your email configuration is working correctly."
                ),
                body_html=(
                    "<p>This is a test email from Gatekeeper.</p>"
                    "<p>If you're reading this, your email configuration is working correctly.</p>"
                ),
            )

            if sent:
                console.print(
                    f"[green]\u2713[/green] Test email sent to {to} via {settings.email_provider}"
                )
            else:
                err_console.print("[red]\u2717[/red] Failed to send test email")
                raise typer.Exit(code=1)
        except Exception as e:
            err_console.print(f"[red]✗[/red] Failed to send email: {e}")
            raise typer.Exit(code=1) from None


@app.command()
@run_async
async def healthcheck():
    """Check that the deployment is correctly configured."""
    all_ok = True

    # Database
    try:
        async with async_session_maker() as db:
            # Check connection
            result = await db.execute(text("SELECT 1"))
            result.scalar()

            # Count migrations
            migration_count = 0
            try:
                result = await db.execute(text("SELECT COUNT(*) FROM _migrations"))
                migration_count = result.scalar() or 0
            except Exception:
                pass  # Table might not exist

            db_type = "SQLite" if "sqlite" in settings.database_url else "PostgreSQL"
            console.print(
                f"Database:     [green]✓[/green] connected "
                f"({db_type}, {migration_count} migrations applied)"
            )
    except Exception as e:
        console.print(f"Database:     [red]\u2717[/red] {e}")
        all_ok = False

    # Admin user
    try:
        async with async_session_maker() as db:
            stmt = select(func.count(User.id)).where(User.is_admin == True)  # noqa: E712
            result = await db.execute(stmt)
            admin_count = result.scalar() or 0

            if admin_count > 0:
                console.print(f"Admin user:   [green]\u2713[/green] {admin_count} admin(s) found")
            else:
                console.print("Admin user:   [red]\u2717[/red] no admin users found")
                all_ok = False
    except Exception:
        pass

    # Email config
    if settings.email_provider:
        provider = settings.email_provider.upper()
        from_addr = settings.email_from_address
        console.print(f"Email:        [green]✓[/green] {provider} configured (from: {from_addr})")
    else:
        console.print("Email:        [red]\u2717[/red] email provider not configured")
        all_ok = False

    # WebAuthn
    if settings.webauthn_rp_id and settings.webauthn_origin:
        rp_id = settings.webauthn_rp_id
        origin = settings.webauthn_origin
        console.print(f"WebAuthn:     [green]✓[/green] RP ID: {rp_id}, Origin: {origin}")
    else:
        console.print("WebAuthn:     [yellow]\u26a0[/yellow] not configured (passkeys disabled)")

    # User stats
    try:
        async with async_session_maker() as db:
            stmt = select(User)
            result = await db.execute(stmt)
            users = result.scalars().all()

            by_status: dict[str, int] = {}
            for u in users:
                by_status[u.status.value] = by_status.get(u.status.value, 0) + 1
            summary = ", ".join(f"{v} {k}" for k, v in by_status.items())
            console.print(f"Users:        {len(users)} total ({summary})")
    except Exception:
        pass

    if not all_ok:
        raise typer.Exit(code=1)


@app.command("reset-sessions")
@run_async
async def reset_sessions(
    email: Annotated[
        str | None,
        typer.Option("--email", "-e", help="Reset sessions for a specific user"),
    ] = None,
):
    """Clear active sessions. All sessions if no email specified."""
    if not email:
        confirm = typer.confirm(
            "Clear ALL active sessions? Every user will need to re-authenticate."
        )
        if not confirm:
            console.print("Aborted.")
            raise typer.Exit()

    async with async_session_maker() as db:
        if email:
            email = email.lower().strip()

            # Find user
            user_stmt = select(User).where(User.email == email)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()

            if not user:
                err_console.print(f"[red]Error:[/red] User {email} not found.")
                raise typer.Exit(code=1)

            # Count and delete sessions
            count_stmt = select(func.count(Session.id)).where(Session.user_id == user.id)
            count_result = await db.execute(count_stmt)
            count = count_result.scalar() or 0

            delete_stmt = delete(Session).where(Session.user_id == user.id)
            await db.execute(delete_stmt)
            await db.commit()

            console.print(f"[green]\u2713[/green] Cleared {count} session(s) for {email}.")
        else:
            # Count and delete all sessions
            count_stmt = select(func.count(Session.id))
            count_result = await db.execute(count_stmt)
            count = count_result.scalar() or 0

            delete_stmt = delete(Session)
            await db.execute(delete_stmt)
            await db.commit()

            console.print(f"[green]\u2713[/green] Cleared {count} session(s).")


@app.command("serve")
def serve():
    """Start the Gatekeeper API server."""
    import uvicorn

    uvicorn.run(
        "gatekeeper.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.server_reload,
    )
