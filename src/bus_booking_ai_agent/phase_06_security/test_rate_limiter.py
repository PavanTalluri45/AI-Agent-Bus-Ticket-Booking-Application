from uuid import uuid4

from bus_booking_ai_agent.config.upstash_redis import redis
from bus_booking_ai_agent.phase_06_security.rate_limiter import (
    check_rate_limit,
)


def main() -> None:
    test_user_id = str(uuid4())

    action = f"test:{test_user_id}"

    redis.delete(
        f"rate_limit:{action}:{test_user_id}"
    )

    limit = 3

    print("Testing rate limiter...")
    print()

    for request_number in range(1, 5):
        result = check_rate_limit(
            user_id=test_user_id,
            action=action,
            limit=limit,
            window_seconds=60,
        )

        print(
            f"Request {request_number}: "
            f"count={result.current_count}, "
            f"allowed={result.allowed}, "
            f"limit={result.limit}, "
            f"retry_after={result.retry_after_seconds}s"
        )

    key = f"rate_limit:{action}:{test_user_id}"
    redis.delete(key)

    print()
    print("Rate limiter test completed.")


if __name__ == "__main__":
    main()