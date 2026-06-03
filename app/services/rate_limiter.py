# NOTE: This rate limiter resets on server restart. Acceptable for MVP single-instance deployment.
import time

_requests: dict[str, list[float]] = {}


def check_rate_limit(
    user_id: str,
    max_requests: int = 20,
    window_seconds: int = 3600,
) -> tuple[bool, int]:
    """
    Returns (allowed, retry_after_seconds).
    allowed=True means the request is permitted and has been recorded.
    allowed=False means the user is rate-limited; retry_after is seconds until the window resets.
    """
    now = time.time()
    timestamps = _requests.get(user_id, [])

    # Prune timestamps outside the window
    timestamps = [t for t in timestamps if now - t < window_seconds]

    if len(timestamps) < max_requests:
        timestamps.append(now)
        _requests[user_id] = timestamps
        return (True, 0)

    # Rate limited — compute how long until the oldest timestamp falls out of the window
    oldest = timestamps[0]
    retry_after = int(window_seconds - (now - oldest))
    _requests[user_id] = timestamps
    return (False, max(retry_after, 1))
