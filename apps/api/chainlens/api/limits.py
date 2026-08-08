"""Phase 7 hardening: rate limiting and per-document access scoping.

Both are deliberately small and in-process. A token bucket in a dict is the wrong answer
for more than one replica, and that limitation is stated here rather than discovered in
production: with several API processes the effective limit is the configured limit times
the replica count. The interface is the part worth getting right now, because moving the
bucket to Redis is a change of one class.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

from fastapi import HTTPException, Request


@dataclass
class TokenBucket:
    """Sliding-window counter. Exact rather than approximate, at the cost of memory."""

    limit: int
    window_seconds: float
    hits: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def check(self, key: str, now: float | None = None) -> tuple[bool, int, float]:
        moment = now if now is not None else time.monotonic()
        bucket = self.hits[key]
        cutoff = moment - self.window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self.limit:
            retry_after = max(0.0, bucket[0] + self.window_seconds - moment)
            return False, 0, retry_after
        bucket.append(moment)
        return True, self.limit - len(bucket), 0.0


class RateLimiter:
    """Per-client limits, with a stricter bucket for the expensive endpoints.

    Retrieval costs an embedding and two index scans; listing documents costs a query.
    Charging them the same is how a limit ends up either useless or hostile, so the
    expensive paths get their own smaller bucket.
    """

    #: Endpoints whose cost justifies the stricter bucket.
    EXPENSIVE_PREFIXES = ("/query", "/analyse", "/compare", "/documents")

    def __init__(
        self,
        default_per_minute: int = 120,
        expensive_per_minute: int = 20,
        window_seconds: float = 60.0,
    ) -> None:
        self.default = TokenBucket(default_per_minute, window_seconds)
        self.expensive = TokenBucket(expensive_per_minute, window_seconds)

    @staticmethod
    def client_key(request: Request) -> str:
        # An explicit key beats an IP address behind a proxy, and an IP address beats
        # nothing. Never fall back to a single global bucket: that turns a rate limit into
        # a denial of service that one client can inflict on everyone.
        api_key = request.headers.get("x-api-key")
        if api_key:
            return f"key:{api_key[:32]}"
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        return f"ip:{request.client.host if request.client else 'unknown'}"

    def enforce(self, request: Request) -> tuple[str, int]:
        key = self.client_key(request)
        path = request.url.path
        expensive = request.method != "GET" or any(
            path.startswith(prefix) for prefix in self.EXPENSIVE_PREFIXES
        )
        bucket = self.expensive if expensive else self.default
        allowed, remaining, retry_after = bucket.check(key)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"rate limit of {bucket.limit} requests per "
                    f"{int(bucket.window_seconds)}s exceeded for this client"
                ),
                headers={"retry-after": str(max(1, int(retry_after) + 1))},
            )
        return key, remaining


class DocumentScope:
    """Per-document access scoping.

    The deployment this was written for has no user model, so scoping is expressed as a
    mapping from an API key to the documents it may read, loaded from configuration. With
    no mapping configured every key sees everything, which is the current behaviour and is
    reported by `/readyz` rather than being a silent default.
    """

    def __init__(self, scopes: dict[str, set[str]] | None = None) -> None:
        self.scopes = scopes or {}

    @property
    def enforcing(self) -> bool:
        return bool(self.scopes)

    def allows(self, request: Request, document_id: str) -> bool:
        if not self.enforcing:
            return True
        api_key = request.headers.get("x-api-key")
        if not api_key:
            return False
        allowed = self.scopes.get(api_key)
        return bool(allowed and (document_id in allowed or "*" in allowed))

    def require(self, request: Request, document_id: str) -> None:
        if not self.allows(request, document_id):
            # 404 rather than 403: telling an unauthorised caller that a document exists is
            # itself a disclosure.
            raise HTTPException(status_code=404, detail="document not found")
