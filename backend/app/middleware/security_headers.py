"""Security response headers, environment-sensitive (keeps Vite dev server usable)."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import settings

_AUTH_PATH_PREFIXES = ("/api/auth", "/api/admin")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        is_production = settings.environment.lower() == "production"
        if is_production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
            # Vite dev server needs 'unsafe-inline'/'unsafe-eval' and websocket connect-src; only
            # apply a strict CSP in production so local development is not broken.
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )

        if request.url.path.startswith(_AUTH_PATH_PREFIXES):
            response.headers["Cache-Control"] = "no-store"

        return response
