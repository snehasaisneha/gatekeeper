import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from gatekeeper.api.v1.router import router as v1_router
from gatekeeper.config import get_settings
from gatekeeper.database import async_session_maker, init_db
from gatekeeper.rate_limit import limiter
from gatekeeper.services.security import SecurityService, get_client_ip

STATIC_DIR = Path(__file__).parent / "static"

settings = get_settings()


class BanCheckMiddleware(BaseHTTPMiddleware):
    """Middleware to check if the client IP is banned."""

    async def dispatch(self, request: Request, call_next):
        if (
            request.url.path in {"/health", "/favicon.ico"}
            or request.url.path.startswith("/static")
        ):
            return await call_next(request)

        client_ip = get_client_ip(request)
        if not client_ip:
            return await call_next(request)

        # Check if IP is banned
        try:
            async with async_session_maker() as db:
                security_service = SecurityService(db)
                if await security_service.is_ip_banned(client_ip):
                    # Log the blocked request
                    from gatekeeper.models.audit import AuditLog

                    audit = AuditLog(
                        event_type="security.blocked.banned_ip",
                        ip_address=client_ip,
                        details=json.dumps({"path": request.url.path}),
                    )
                    db.add(audit)
                    await db.commit()

                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Access denied"},
                    )
        except Exception:
            # If ban check fails (e.g., table doesn't exist), allow the request
            # This ensures the app doesn't break if security tables aren't migrated
            pass

        return await call_next(request)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Static authentication service for engineering documentation",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ban checking middleware (must be after CORS)
app.add_middleware(BanCheckMiddleware)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(v1_router, prefix="/api/v1")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def root_redirect(_request: Request) -> RedirectResponse:
    return RedirectResponse(url="/api/v1" if settings.public_api_docs else "/health")


@app.get("/api/v1", include_in_schema=False)
@limiter.limit("30/minute")
async def swagger_ui(request: Request):  # noqa: ARG001
    if not settings.public_api_docs:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return get_swagger_ui_html(
        openapi_url="/api/v1/openapi.json",
        title=f"{settings.app_name} API",
        swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    )


@app.get("/api/v1/openapi.json", include_in_schema=False)
@limiter.limit("20/minute")
async def openapi_schema(request: Request):  # noqa: ARG001
    if not settings.public_api_docs:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return JSONResponse(app.openapi())


@app.get("/favicon.ico", include_in_schema=False)
@limiter.exempt
async def favicon(_request: Request) -> RedirectResponse:
    return RedirectResponse(url="/static/favicon.svg")


@app.get("/health", tags=["Health"])
@limiter.exempt
async def health_check(_request: Request) -> dict[str, str]:
    return {"status": "healthy"}
