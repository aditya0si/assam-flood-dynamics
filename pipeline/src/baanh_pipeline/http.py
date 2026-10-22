"""HTTP fetching with an on-disk cache and bounded retries."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from .config import Config
from .util import atomic_write_bytes


class FetchError(RuntimeError):
    pass


@dataclass
class FetchResult:
    payload: bytes
    url: str
    attempts: int
    from_cache: bool
    status_code: int | None
    fetched_at: str
    error: str | None = None


def url_cache_name(url: str, suffix: str = "") -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    return f"{digest}{suffix}"


def fetch_bytes(
    cfg: Config,
    url: str,
    cache_path: Path,
    *,
    refresh: bool = False,
    method: str = "GET",
    data: dict[str, Any] | None = None,
    timeout_s: float | None = None,
    retries: int | None = None,
    accept: str | None = None,
    abort_on_rate_limit: bool = False,
) -> FetchResult:
    http = cfg.sources["http"]
    timeout = float(timeout_s if timeout_s is not None else http["timeout_s"])
    attempts_allowed = int(retries if retries is not None else http["retries"])
    backoff = [float(v) for v in http["backoff_s"]]
    if cache_path.exists() and cache_path.stat().st_size > 0 and not refresh:
        return FetchResult(
            payload=cache_path.read_bytes(),
            url=url,
            attempts=0,
            from_cache=True,
            status_code=None,
            fetched_at="cache",
        )

    headers = {"User-Agent": str(http["user_agent"])}
    if accept:
        headers["Accept"] = accept
    session = requests.Session()
    last_error = ""
    attempts = 0
    for index in range(max(1, attempts_allowed)):
        attempts = index + 1
        try:
            started = time.time()
            response = session.request(
                method,
                url,
                data=data,
                headers=headers,
                timeout=timeout,
            )
            elapsed = time.time() - started
            if response.status_code in (200, 201):
                atomic_write_bytes(cache_path, response.content)
                return FetchResult(
                    payload=response.content,
                    url=url,
                    attempts=attempts,
                    from_cache=False,
                    status_code=response.status_code,
                    fetched_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                )
            if response.status_code in (429, 500, 502, 503, 504):
                last_error = f"HTTP {response.status_code} after {elapsed:.1f}s: {response.text[:180]!r}"
                if response.status_code == 429:
                    # A caller that can resume from a per-chunk cache should stop
                    # immediately rather than burn the rest of the retry budget on
                    # a quota that will not recover within the backoff window.
                    if abort_on_rate_limit:
                        raise FetchError(
                            f"fetch failed for {url} after {attempts} attempt(s): {last_error}"
                        )
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = float(retry_after) if retry_after is not None else 60.0
                    except ValueError:
                        delay = 60.0
                    time.sleep(max(5.0, min(delay, 120.0)))
            else:
                last_error = f"HTTP {response.status_code} after {elapsed:.1f}s: {response.text[:180]!r}"
                break
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if index + 1 < max(1, attempts_allowed):
            delay = backoff[min(index, len(backoff) - 1)]
            time.sleep(delay)
    raise FetchError(f"fetch failed for {url} after {attempts} attempt(s): {last_error}")
