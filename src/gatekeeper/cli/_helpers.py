"""Shared helpers for CLI commands."""

import asyncio
from functools import wraps
from typing import Callable, TypeVar

from rich.console import Console

console = Console()
err_console = Console(stderr=True)

T = TypeVar("T")


def run_async(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to run async functions from Typer commands."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper
