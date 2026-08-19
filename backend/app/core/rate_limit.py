"""Rate limiting abstraction.

`RateLimiter` defines the interface; `InMemoryRateLimiter` is a single-process, development-grade
sliding-window implementation good enough for one uvicorn worker. For a multi-worker or
multi-instance production deployment, replace it with a Redis-backed implementation (e.g. using
`redis.asyncio` + a Lua script or `INCR`+`EXPIRE`) behind the same interface — no call sites need
to change.
"""
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque


class RateLimiter(ABC):
    @abstractmethod
    async def check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        raise NotImplementedError


class InMemoryRateLimiter(RateLimiter):
    """Sliding-window counter kept in process memory.

    NOTE: this state is per-process. In a multi-worker (gunicorn) or multi-instance deployment,
    limits are enforced independently per worker/instance. Replace with a Redis-backed
    implementation for accurate distributed rate limiting in production.
    """

    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)

    async def check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.monotonic()
        bucket = self._hits[key]
        cutoff = now - window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            retry_after = int(window_seconds - (now - bucket[0])) + 1
            return False, max(retry_after, 1)

        bucket.append(now)
        return True, 0


# Process-wide singleton. Swap for a Redis-backed instance in production by changing this line.
rate_limiter: RateLimiter = InMemoryRateLimiter()


async def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    from app.core.exceptions import rate_limited

    allowed, retry_after = await rate_limiter.check(key, limit, window_seconds)
    if not allowed:
        raise rate_limited(retry_after)
