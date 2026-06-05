# NOTE: This rate limiter resets on server restart. Acceptable for MVP single-instance deployment.
import time

_requests: dict[str, list[float]] = {}
_MAX_ENTRIES = 10_000
_PRUNING_FRACTION = 0.20


def _prune_if_needed() -> None:
    """If the dict exceeds _MAX_ENTRIES, remove the oldest 20% of keys."""
    if len(_requests) <= _MAX_ENTRIES:
        return

    # Sort keys by their most recent timestamp (oldest last)
    sorted_keys = sorted(
        _requests.keys(),
        key=lambda k: _requests[k][-1] if _requests[k] else 0.0,
        reverse=True,
    )
    retain_count = int(len(sorted_keys) * (1 - _PRUNING_FRACTION))
    for key in sorted_keys[retain_count:]:
        del _requests[key]


def check_rate_limit(
    key: str,
    max_requests: int = 20,
    window_seconds: int = 3600,
) -> tuple[bool, int]:
    """
    Returns (allowed, retry_after_seconds).
    allowed=True means the request is permitted and has been recorded.
    allowed=False means the caller is rate-limited; retry_after is seconds until the window resets.
    """
    _prune_if_needed()

    now = time.time()
    timestamps = _requests.get(key, [])

    # Prune timestamps outside the window
    timestamps = [t for t in timestamps if now - t < window_seconds]

    if len(timestamps) < max_requests:
        timestamps.append(now)
        _requests[key] = timestamps
        return (True, 0)

    # Rate limited — compute how long until the oldest timestamp falls out of the window
    oldest = timestamps[0]
    retry_after = int(window_seconds - (now - oldest))
    _requests[key] = timestamps
    return (False, max(retry_after, 1))


def check_auth_rate_limit(ip: str, endpoint: str) -> tuple[bool, int]:
    """
    Rate-limit authentication endpoints by IP.
      - login:    5 requests per 900 seconds (15 min)
      - register: 3 requests per 900 seconds (15 min)
    Returns (allowed, retry_after_seconds).
    """
    limits = {
        "login": (5, 900),
        "register": (3, 900),
    }
    max_req, window = limits.get(endpoint, (5, 900))
    key = f"auth:{endpoint}:{ip}"
    return check_rate_limit(key=key, max_requests=max_req, window_seconds=window)
