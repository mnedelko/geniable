"""Input validators for CLI commands."""

import re
from typing import Optional
from pathlib import Path


def validate_url(url: str) -> bool:
    """Validate a URL format.

    Args:
        url: URL string to validate

    Returns:
        True if valid
    """
    pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return bool(pattern.match(url))


def validate_email(email: str) -> bool:
    """Validate an email format.

    Args:
        email: Email string to validate

    Returns:
        True if valid
    """
    pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    return bool(pattern.match(email))


def validate_api_key(key: str, prefix: Optional[str] = None) -> bool:
    """Validate an API key format.

    Args:
        key: API key to validate
        prefix: Expected prefix (e.g., 'ls_' for LangSmith)

    Returns:
        True if valid
    """
    if not key or len(key) < 10:
        return False

    if prefix and not key.startswith(prefix):
        return False

    return True


def validate_project_key(key: str) -> bool:
    """Validate a Jira project key format.

    Args:
        key: Project key to validate

    Returns:
        True if valid
    """
    pattern = re.compile(r'^[A-Z][A-Z0-9_]{1,9}$')
    return bool(pattern.match(key.upper()))


def validate_path(path: str, must_exist: bool = False) -> bool:
    """Validate a file path.

    Args:
        path: Path string to validate
        must_exist: Whether the path must exist

    Returns:
        True if valid
    """
    try:
        p = Path(path)
        if must_exist:
            return p.exists()
        return True
    except Exception:
        return False
