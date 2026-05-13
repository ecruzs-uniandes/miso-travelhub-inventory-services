"""In-memory token bucket per (user_id, route). For multi-instance use Redis.

The current PF1 gap (rate limiting distribuido) is documented; for PF2 MVP this
in-memory implementation is acceptable since Cloud Armor enforces a global limit
at the edge. This is a defense-in-depth layer.
"""
import time
from collections import defaultdict
from typing import Any

from fastapi import HTTPException, Request, status

from app.config import settings
from app.middleware.filters.base import AuthFilter


class RateLimitFilter(AuthFilter):
    def __init__(self) -> None:
        super().__init__()
        # key -> [count, window_start_epoch_seconds]
        self._buckets: dict[str, list[float]] = defaultdict(lambda: [0.0, time.time()])
        self._window_seconds = 60.0
        self._limit = settings.rate_limit_rpm

    async def handle(self, request: Request, payload: dict[str, Any]) -> None:
        key = f"{payload.get('sub')}:{request.url.path}"
        bucket = self._buckets[key]
        now = time.time()
        if now - bucket[1] >= self._window_seconds:
            bucket[0] = 0.0
            bucket[1] = now
        bucket[0] += 1
        if bucket[0] > self._limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {self._limit} req/min",
            )
        await self._pass_to_next(request, payload)
