from slowapi import Limiter
from starlette.requests import Request

from gatekeeper.services.security import get_client_ip as get_request_client_ip


def get_client_ip(request: Request) -> str:
    """Get the client IP used for rate limiting."""
    return get_request_client_ip(request) or "unknown"


limiter = Limiter(
    key_func=get_client_ip,
    default_limits=["120/minute", "1000/hour"],
)
