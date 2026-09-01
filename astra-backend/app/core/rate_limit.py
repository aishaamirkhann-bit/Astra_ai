import asyncio
from collections import defaultdict, deque
from time import monotonic

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def reset_rate_limit_state() -> None:
    """Clear in-process buckets (primarily for isolated tests)."""
    _RATE_LIMIT_BUCKETS.clear()


class SensitiveEndpointRateLimitMiddleware(BaseHTTPMiddleware):
    """Small-process limiter; Redis provides shared enforcement in production."""

    def __init__(self, app):
        super().__init__(app)
        self._requests = _RATE_LIMIT_BUCKETS
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next):
        limit = self._limit_for(request.url.path)
        if request.method == "POST" and limit:
            # Uvicorn resolves trusted proxy headers into request.client; never
            # trust a directly supplied X-Forwarded-For value here.
            client = request.client.host if request.client else "unknown"
            key = f"{client}:{request.url.path}"
            now = monotonic()
            async with self._lock:
                bucket = self._requests[key]
                while bucket and bucket[0] <= now - settings.RATE_LIMIT_WINDOW_SECONDS:
                    bucket.popleft()
                if len(bucket) >= limit:
                    retry_after = max(1, int(settings.RATE_LIMIT_WINDOW_SECONDS - (now - bucket[0])))
                    return JSONResponse(status_code=429, content={"detail": "Too many authorization attempts"}, headers={"Retry-After": str(retry_after)})
                bucket.append(now)
        return await call_next(request)

    @staticmethod
    def _limit_for(path: str) -> int:
        if path.endswith("/wallet/authorize-consent"):
            return settings.CONSENT_RATE_LIMIT
        if path.endswith(("/auth/verify-otp", "/auth/resend-otp", "/auth/login", "/auth/forgot-password", "/auth/reset-password")):
            return settings.OTP_RATE_LIMIT
        return 0
