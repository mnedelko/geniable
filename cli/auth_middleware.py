"""Authentication middleware for CLI commands.

Provides decorators and utilities for requiring authentication
in CLI commands.
"""

import functools
import logging
from typing import Callable, Optional, TypeVar

import typer

from cli.output_formatter import print_error, print_info, print_warning

logger = logging.getLogger(__name__)

# Type variable for decorated functions
F = TypeVar("F", bound=Callable)


def require_auth(func: F) -> F:
    """Decorator to require authentication for a command.

    If user is not authenticated, displays an error message and exits.
    If authenticated, the command runs normally.

    Usage:
        @app.command()
        @require_auth
        def my_command():
            # This code only runs if authenticated
            pass
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            from cli.auth import get_auth_client
        except ImportError as e:
            print_error(f"Authentication module not available: {e}")
            raise typer.Exit(1)

        try:
            auth_client = get_auth_client()

            if not auth_client.is_authenticated():
                print_error("Authentication required")
                print_info("Run 'geni login' to authenticate")
                raise typer.Exit(1)

            # Inject auth context into kwargs if the function accepts it
            return func(*args, **kwargs)

        except ValueError as e:
            # Cognito not configured
            print_warning("Authentication not configured")
            print_info(str(e))
            raise typer.Exit(1)
        except typer.Exit:
            raise
        except Exception as e:
            print_error(f"Authentication check failed: {e}")
            raise typer.Exit(1)

    return wrapper  # type: ignore


def get_access_token() -> Optional[str]:
    """Get the current user's access token.

    Returns:
        Access token string or None if not authenticated
    """
    try:
        from cli.auth import get_auth_client

        auth_client = get_auth_client()
        tokens = auth_client.get_current_tokens()

        if tokens:
            return tokens.access_token
        return None

    except Exception as e:
        logger.debug(f"Failed to get access token: {e}")
        return None


def get_id_token() -> Optional[str]:
    """Get the current user's ID token (for API Gateway authorization).

    Returns:
        ID token string or None if not authenticated
    """
    try:
        from cli.auth import get_auth_client

        auth_client = get_auth_client()
        tokens = auth_client.get_current_tokens()

        if tokens:
            return tokens.id_token
        return None

    except Exception as e:
        logger.debug(f"Failed to get ID token: {e}")
        return None


def get_user_id() -> Optional[str]:
    """Get the current user's ID (Cognito sub claim).

    Returns:
        User ID string or None if not authenticated
    """
    try:
        from cli.auth import get_auth_client

        auth_client = get_auth_client()
        tokens = auth_client.get_current_tokens()

        if tokens:
            return tokens.user_id
        return None

    except Exception as e:
        logger.debug(f"Failed to get user ID: {e}")
        return None


def get_auth_headers() -> dict:
    """Get authorization headers for API requests.

    Returns:
        Dictionary with Authorization header or empty dict if not authenticated
    """
    token = get_id_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


class AuthenticatedCommand:
    """Context manager for commands that require authentication.

    Usage:
        with AuthenticatedCommand() as auth:
            # auth.access_token - current access token
            # auth.id_token - current ID token
            # auth.user_id - current user ID
            # auth.headers - authorization headers dict
            pass
    """

    def __init__(self, require_login: bool = True):
        """Initialize authenticated command context.

        Args:
            require_login: If True, raises Exit if not authenticated
        """
        self.require_login = require_login
        self.access_token: Optional[str] = None
        self.id_token: Optional[str] = None
        self.user_id: Optional[str] = None
        self._tokens = None

    def __enter__(self):
        try:
            from cli.auth import get_auth_client

            auth_client = get_auth_client()
            self._tokens = auth_client.get_current_tokens()

            if self._tokens:
                self.access_token = self._tokens.access_token
                self.id_token = self._tokens.id_token
                self.user_id = self._tokens.user_id
            elif self.require_login:
                print_error("Authentication required")
                print_info("Run 'geni login' to authenticate")
                raise typer.Exit(1)

        except ValueError as e:
            if self.require_login:
                print_warning("Authentication not configured")
                print_info(str(e))
                raise typer.Exit(1)
        except typer.Exit:
            raise
        except Exception as e:
            if self.require_login:
                print_error(f"Authentication check failed: {e}")
                raise typer.Exit(1)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    @property
    def headers(self) -> dict:
        """Get authorization headers for API requests."""
        if self.id_token:
            return {"Authorization": f"Bearer {self.id_token}"}
        return {}

    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self._tokens is not None
