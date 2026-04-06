import asyncio
import time
import os
import json
import threading

_LOCK_FILE     = "/tmp/_ratelimit.lock"
_STATE_FILE    = "/tmp/_ratelimit.json"
_BUCKETS_FILE  = "/tmp/_buckets.json"
_THROTTLE_FILE = "/tmp/_throttle"

_global_reset_at: float = 0.0

_windows_lock = threading.Lock()

def _windows_lock_file():
    _windows_lock.acquire()

def _windows_unlock_file():
    _windows_lock.release()

def _read_global_reset():
    try:
        with open(_STATE_FILE) as f:
            return float(json.load(f).get("reset_at", 0))
    except Exception:
        return 0.0


def _write_global_reset(ts: float):
    try:
        with open(_STATE_FILE, "w") as f:
            json.dump({"reset_at": ts}, f)
    except Exception:
        pass


def _update_bucket(headers):
    """Parse x-ratelimit-* headers and upsert into shared buckets file."""
    bucket = headers.get("x-ratelimit-bucket")
    if not bucket:
        return
    try:
        remaining = int(headers.get("x-ratelimit-remaining", -1))
        limit     = int(headers.get("x-ratelimit-limit", -1))
        reset     = float(headers.get("x-ratelimit-reset", 0))
        now       = time.monotonic()

        try:
            with open(_BUCKETS_FILE) as f:
                data = json.load(f)
        except Exception:
            data = {}

        data[bucket] = {
            "remaining": remaining,
            "limit":     limit,
            "reset":     reset,
            "updated":   now,
        }

        with open(_BUCKETS_FILE, "w") as f:
            json.dump(data, f)

        print(
            f"[RL:TRACK] bucket={bucket} "
            f"remaining={remaining} limit={limit} reset={reset:.3f}",
            flush=True,
        )
    except Exception:
        pass


def _check_throttle() -> float:
    """Return seconds to sleep if alert.py has set a throttle, else 0."""
    try:
        with open(_THROTTLE_FILE) as f:
            d = json.load(f)
        until = float(d.get("until", 0))
        now   = time.monotonic()
        if until > now:
            return until - now
    except Exception:
        pass
    return 0.0


async def request(http, method: str, url: str, **kwargs):
    for attempt in range(5):

        throttle = _check_throttle()
        if throttle > 0:
            print(f"[RATELIMIT] throttle signal {throttle:.2f}s (alert.py)", flush=True)
            await asyncio.sleep(throttle)

        reset_at = _read_global_reset()
        now = time.monotonic()
        if reset_at > now:
            wait = reset_at - now
            print(f"[RATELIMIT] global cooldown {wait:.1f}s", flush=True)
            await asyncio.sleep(wait)

        resp = await getattr(http, method)(url, **kwargs)

        _update_bucket(resp.headers)

        if resp.status_code == 429:
            try:
                data = resp.json()
            except Exception:
                data = {}
            retry_after = float(
                resp.headers.get("retry-after") or data.get("retry_after") or 5
            )
            is_global = (
                data.get("global", False)
                or resp.headers.get("x-ratelimit-global") == "true"
            )
            print(
                f"[RATELIMIT] 429 {'global' if is_global else 'local'} "
                f"retry_after={retry_after:.1f}s attempt={attempt+1}",
                flush=True,
            )
            if is_global:
                _write_global_reset(time.monotonic() + retry_after + 1.0)
            if retry_after > 120:
                print(f"[RATELIMIT] retry_after too long ({retry_after}s), wrote global reset, dropping", flush=True)
                return resp
            await asyncio.sleep(retry_after + 0.5)
            continue

        return resp

    return resp