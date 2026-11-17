"""Read-only API connectivity checks for configured Debrid providers.

A successful list_torrents() call confirms that the provider API accepted the
configured credentials and returned a valid response. It does not establish
subscription validity, remaining traffic, or expiry dates.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HealthResult:
    provider: str
    status: str
    detail: str
    checked_at: str = ""


async def check_provider(provider: Any, timeout: float = 15.0) -> HealthResult:
    """Perform a read-only API request; never create, change, or delete account data."""
    try:
        torrents = await asyncio.wait_for(provider.list_torrents(), timeout=timeout)
        count = len(torrents) if isinstance(torrents, (list, tuple)) else 0
        return HealthResult(provider.slug, "ok", f"API responded; torrents={count}")
    except asyncio.TimeoutError:
        return HealthResult(provider.slug, "timeout", f"API request exceeded {timeout:g}s")
    except Exception as exc:
        # Do not persist exception messages: provider responses can contain private data.
        return HealthResult(provider.slug, "error", type(exc).__name__)


async def check_providers(providers: dict[str, Any], timeout: float = 15.0) -> list[HealthResult]:
    results = []
    for provider in providers.values():
        results.append(await check_provider(provider, timeout=timeout))
    return results
