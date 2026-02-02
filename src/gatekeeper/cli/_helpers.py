"""Shared helpers for CLI commands."""

import asyncio
from collections.abc import Callable
from functools import wraps

from rich.console import Console

console = Console()
err_console = Console(stderr=True)


def run_async[T](func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to run async functions from Typer commands."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper
