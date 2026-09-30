from dataclasses import dataclass

from bus_booking_ai_agent.config.upstash_redis import redis 


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    current_count: int
    limit: int
    retry_after_seconds: int


def check_rate_limit(
    user_id: str,
    action: str,
    limit: int,
    window_seconds: int = 60,
) -> RateLimitResult:
    key = f"rate_limit:{action}:{user_id}"

    current_count = redis.incr(key)

    if current_count == 1:
        redis.expire(key, window_seconds)

    allowed = current_count <= limit

    retry_after = redis.ttl(key)

    if retry_after < 0:
        retry_after = window_seconds

    return RateLimitResult(
        allowed=allowed,
        current_count=current_count,
        limit=limit,
        retry_after_seconds=retry_after,
    )