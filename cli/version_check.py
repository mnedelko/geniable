"""Version check utility for geniable CLI."""

from __future__ import annotations

import contextlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

_CACHE_FILE = Path.home() / ".geniable_version_cache"
_CACHE_TTL = 3600  # 1 hour
_PYPI_TIMEOUT = 2  # seconds

# Commands that should NOT trigger the version check
_SKIP_COMMANDS: set[tuple[str, ...]] = {
    ("analyze", "specific"),
    ("analyze-specific",),
    ("ticket", "create"),
    ("issues", "list"),
    ("issues-list",),
    ("login",),
    ("reset-password",),
}

# Match only stable release versions (digits and dots)
_STABLE_VERSION = re.compile(r"^\d+(\.\d+)+$")


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse a stable version string like '2.18.3' into a comparable tuple."""
    return tuple(int(x) for x in v.split("."))


def _is_stable(v: str) -> bool:
    """Return True if version string is a stable release (no pre-release suffix)."""
    return bool(_STABLE_VERSION.match(v))


def should_skip() -> bool:
    """Return True if the current command is in the skip list."""
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        return True
    return any(tuple(args[: len(p)]) == p for p in _SKIP_COMMANDS)


def check_for_updates() -> None:
    """Check PyPI for a newer version and warn if outdated.

    Non-blocking: silently returns on any error. Caches results for 1 hour.
    """
    with contextlib.suppress(Exception):
        _do_check()


def _do_check() -> None:
    from importlib.metadata import version as get_version

    current = get_version("geniable")
    if not _is_stable(current):
        return

    # Check cache first
    if _CACHE_FILE.exists():
        cache = json.loads(_CACHE_FILE.read_text())
        if time.time() - cache.get("timestamp", 0) < _CACHE_TTL:
            latest = cache.get("latest", "")
            if latest and _parse_version(latest) > _parse_version(current):
                _show_notice(current, latest)
            return

    # Fetch from PyPI using stdlib (no requests dependency for startup path)
    req = urllib.request.Request(
        "https://pypi.org/pypi/geniable/json",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=_PYPI_TIMEOUT) as resp:
        data = json.loads(resp.read().decode())
    latest = data["info"]["version"]

    # Skip pre-release versions from PyPI
    if not _is_stable(latest):
        return

    # Write cache
    with contextlib.suppress(Exception):
        _CACHE_FILE.write_text(
            json.dumps({"timestamp": time.time(), "latest": latest})
        )

    if _parse_version(latest) > _parse_version(current):
        _show_notice(current, latest)


def _show_notice(current: str, latest: str) -> None:
    from cli.output_formatter import print_info, print_warning

    print_warning(f"Update available: v{current} → v{latest}")
    print_info("Upgrade: pip install --upgrade geniable")
