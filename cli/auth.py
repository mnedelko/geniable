"""Cognito authentication module for CLI.

Handles:
- SRP-based authentication with AWS Cognito
- Token storage in system keyring
- Token refresh logic
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Service name for keyring storage
KEYRING_SERVICE = "geniable"


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    pass


class PasswordChangeRequired(Exception):
    """Raised when user must change their temporary password."""

    def __init__(self, session: str, user_id: str, message: str = "Password change required"):
        self.session = session
        self.user_id = user_id
        super().__init__(message)


@dataclass
class AuthTokens:
    """Container for Cognito tokens."""

    access_token: str
    id_token: str
    refresh_token: str
    expires_at: Optional[datetime]  # Datetime in UTC
    user_id: str
    email: str

    def is_expired(self) -> bool:
        """Check if access token is expired (with 5-minute buffer)."""
        if not self.expires_at:
            return True
        buffer_seconds = 300  # 5 minutes
        now = datetime.now(timezone.utc)
        expires = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
        return now > expires - timedelta(seconds=buffer_seconds)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "access_token": self.access_token,
            "id_token": self.id_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.timestamp() if self.expires_at else None,
            "user_id": self.user_id,
            "email": self.email,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuthTokens":
        """Create from dictionary."""
        expires_at = data.get("expires_at")
        if expires_at:
            expires_at = datetime.fromtimestamp(expires_at, tz=timezone.utc)
        return cls(
            access_token=data["access_token"],
            id_token=data["id_token"],
            refresh_token=data["refresh_token"],
            expires_at=expires_at,
            user_id=data["user_id"],
            email=data["email"],
        )


class TokenStorage:
    """Secure token storage using system keyring or encrypted file fallback."""

    def __init__(self, use_keyring: bool = True, config_dir: Optional[str] = None):
        """Initialize token storage.

        Args:
            use_keyring: Try to use system keyring (macOS Keychain, etc.)
            config_dir: Directory for fallback file storage
        """
        self.use_keyring = use_keyring
        self.config_dir = config_dir or os.path.expanduser("~/.geniable")
        self._keyring = None

        if use_keyring:
            try:
                import keyring
                self._keyring = keyring
            except ImportError:
                logger.debug("keyring not available, using file storage")
                self.use_keyring = False

    def _get_token_file(self) -> str:
        """Get path to token file."""
        os.makedirs(self.config_dir, exist_ok=True)
        return os.path.join(self.config_dir, "tokens.json")

    def store_tokens(self, tokens: AuthTokens) -> None:
        """Store tokens securely.

        Args:
            tokens: AuthTokens to store
        """
        data = json.dumps(tokens.to_dict())

        if self._keyring:
            try:
                self._keyring.set_password(KEYRING_SERVICE, "tokens", data)
                logger.debug("Tokens stored in keyring")
                return
            except Exception as e:
                logger.warning(f"Keyring storage failed: {e}, using file fallback")

        # File fallback (less secure but functional)
        token_file = self._get_token_file()
        with open(token_file, "w") as f:
            f.write(data)
        os.chmod(token_file, 0o600)  # User read/write only
        logger.debug("Tokens stored in file")

    def get_tokens(self) -> Optional[AuthTokens]:
        """Retrieve stored tokens.

        Returns:
            AuthTokens or None if not found
        """
        data = None

        if self._keyring:
            try:
                data = self._keyring.get_password(KEYRING_SERVICE, "tokens")
                if data:
                    logger.debug("Tokens retrieved from keyring")
            except Exception as e:
                logger.warning(f"Keyring retrieval failed: {e}")

        if not data:
            # Try file fallback
            token_file = self._get_token_file()
            if os.path.exists(token_file):
                with open(token_file, "r") as f:
                    data = f.read()
                logger.debug("Tokens retrieved from file")

        if not data:
            return None

        try:
            return AuthTokens.from_dict(json.loads(data))
        except Exception as e:
            logger.error(f"Failed to parse stored tokens: {e}")
            return None

    def clear_tokens(self) -> None:
        """Clear stored tokens."""
        if self._keyring:
            try:
                self._keyring.delete_password(KEYRING_SERVICE, "tokens")
                logger.debug("Tokens cleared from keyring")
            except Exception:
                pass

        # Also clear file if exists
        token_file = self._get_token_file()
        if os.path.exists(token_file):
            os.remove(token_file)
            logger.debug("Tokens cleared from file")


class CognitoAuthClient:
    """Cognito authentication client with SRP support."""

    def __init__(
        self,
        user_pool_id: str,
        client_id: str,
        region: str = "ap-southeast-2",
        use_keyring: bool = True,
    ):
        """Initialize Cognito client.

        Args:
            user_pool_id: Cognito User Pool ID
            client_id: Cognito App Client ID
            region: AWS region
            use_keyring: Use system keyring for token storage
        """
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.region = region
        self._client = None
        self._token_storage = TokenStorage(use_keyring=use_keyring)

        # SRP constants
        self._N_HEX = (
            "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
            "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
            "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
            "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
            "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
            "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
            "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
            "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
            "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
            "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
            "15728E5A8AAAC42DAD33170D04507A33A85521ABDF1CBA64"
            "ECFB850458DBEF0A8AEA71575D060C7DB3970F85A6E1E4C7"
            "ABF5AE8CDB0933D71E8C94E04A25619DCEE3D2261AD2EE6B"
            "F12FFA06D98A0864D87602733EC86A64521F2B18177B200C"
            "BBE117577A615D6C770988C0BAD946E208E24FA074E5AB31"
            "43DB5BFCE0FD108E4B82D120A93AD2CAFFFFFFFFFFFFFFFF"
        )
        self._g_hex = "2"
        self._info_bits = bytearray("Caldera Derived Key", "utf-8")

    @property
    def client(self):
        """Lazy-load Cognito client."""
        if self._client is None:
            import boto3
            self._client = boto3.client(
                "cognito-idp",
                region_name=self.region,
            )
        return self._client

    def login(self, username: str, password: str) -> AuthTokens:
        """Authenticate user with SRP.

        Args:
            username: User's email/username
            password: User's password

        Returns:
            AuthTokens on success

        Raises:
            AuthenticationError on authentication failure
        """
        try:
            # Generate SRP values
            small_a, large_a = self._generate_random_key_pair()

            # Initiate auth
            auth_params = {
                "USERNAME": username,
                "SRP_A": self._long_to_hex(large_a),
            }

            response = self.client.initiate_auth(
                AuthFlow="USER_SRP_AUTH",
                ClientId=self.client_id,
                AuthParameters=auth_params,
            )

            challenge_name = response.get("ChallengeName")

            if challenge_name != "PASSWORD_VERIFIER":
                raise AuthenticationError(f"Unexpected challenge: {challenge_name}")

            # Process challenge
            challenge = response["ChallengeParameters"]
            user_id = challenge["USER_ID_FOR_SRP"]
            salt = challenge["SALT"]
            srp_b = challenge["SRP_B"]
            secret_block = challenge["SECRET_BLOCK"]

            # Compute response
            timestamp = datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S %Z %Y")
            claim = self._compute_claim(
                small_a=small_a,
                large_a=large_a,
                username=user_id,
                password=password,
                salt=salt,
                srp_b=srp_b,
                secret_block=secret_block,
                timestamp=timestamp,
            )

            # Respond to challenge
            challenge_response = {
                "USERNAME": user_id,
                "PASSWORD_CLAIM_SECRET_BLOCK": secret_block,
                "PASSWORD_CLAIM_SIGNATURE": claim,
                "TIMESTAMP": timestamp,
            }

            auth_result = self.client.respond_to_auth_challenge(
                ClientId=self.client_id,
                ChallengeName="PASSWORD_VERIFIER",
                ChallengeResponses=challenge_response,
            )

            # Check if password change is required (comes AFTER SRP verification)
            if auth_result.get("ChallengeName") == "NEW_PASSWORD_REQUIRED":
                raise PasswordChangeRequired(
                    session=auth_result["Session"],
                    user_id=auth_result["ChallengeParameters"].get("USER_ID_FOR_SRP", username),
                    message="Password change required for new account.",
                )

            if "AuthenticationResult" not in auth_result:
                raise AuthenticationError("Authentication failed")

            result = auth_result["AuthenticationResult"]

            # Parse tokens with datetime expiry
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=result["ExpiresIn"])
            tokens = AuthTokens(
                access_token=result["AccessToken"],
                id_token=result["IdToken"],
                refresh_token=result["RefreshToken"],
                expires_at=expires_at,
                user_id=self._extract_user_id(result["IdToken"]),
                email=username,
            )

            # Store tokens
            self._token_storage.store_tokens(tokens)

            return tokens

        except self.client.exceptions.NotAuthorizedException as e:
            raise AuthenticationError("Invalid username or password") from e
        except self.client.exceptions.UserNotFoundException as e:
            raise AuthenticationError("User not found") from e
        except self.client.exceptions.UserNotConfirmedException as e:
            raise AuthenticationError("User account not confirmed") from e
        except (AuthenticationError, PasswordChangeRequired):
            raise
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise AuthenticationError(f"Authentication failed: {e}") from e

    def complete_password_change(
        self, session: str, user_id: str, new_password: str, email: str
    ) -> AuthTokens:
        """Complete the password change challenge.

        Args:
            session: Session from the NEW_PASSWORD_REQUIRED challenge
            user_id: User ID from the challenge
            new_password: New password to set
            email: User's email address

        Returns:
            AuthTokens on success

        Raises:
            AuthenticationError on failure
        """
        try:
            response = self.client.respond_to_auth_challenge(
                ClientId=self.client_id,
                ChallengeName="NEW_PASSWORD_REQUIRED",
                Session=session,
                ChallengeResponses={
                    "USERNAME": user_id,
                    "NEW_PASSWORD": new_password,
                },
            )

            if "AuthenticationResult" not in response:
                raise AuthenticationError("Password change failed")

            result = response["AuthenticationResult"]

            # Parse tokens with datetime expiry
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=result["ExpiresIn"])
            tokens = AuthTokens(
                access_token=result["AccessToken"],
                id_token=result["IdToken"],
                refresh_token=result["RefreshToken"],
                expires_at=expires_at,
                user_id=self._extract_user_id(result["IdToken"]),
                email=email,
            )

            # Store tokens
            self._token_storage.store_tokens(tokens)

            return tokens

        except self.client.exceptions.InvalidPasswordException as e:
            raise AuthenticationError(
                "Invalid password. Password must be at least 12 characters "
                "and include uppercase, lowercase, and numbers."
            ) from e
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Password change error: {e}")
            raise AuthenticationError(f"Password change failed: {e}") from e

    def refresh(self, refresh_token: str) -> AuthTokens:
        """Refresh access tokens.

        Args:
            refresh_token: Refresh token

        Returns:
            New AuthTokens

        Raises:
            AuthenticationError on refresh failure
        """
        try:
            response = self.client.initiate_auth(
                AuthFlow="REFRESH_TOKEN_AUTH",
                ClientId=self.client_id,
                AuthParameters={
                    "REFRESH_TOKEN": refresh_token,
                },
            )

            if "AuthenticationResult" not in response:
                raise AuthenticationError("Token refresh failed")

            result = response["AuthenticationResult"]

            # Get stored tokens for user info
            stored = self._token_storage.get_tokens()
            user_id = stored.user_id if stored else ""
            email = stored.email if stored else ""

            # Parse tokens with datetime expiry
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=result["ExpiresIn"])
            tokens = AuthTokens(
                access_token=result["AccessToken"],
                id_token=result["IdToken"],
                refresh_token=refresh_token,  # Refresh token doesn't change
                expires_at=expires_at,
                user_id=user_id or self._extract_user_id(result["IdToken"]),
                email=email,
            )

            # Store refreshed tokens
            self._token_storage.store_tokens(tokens)

            return tokens

        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            raise AuthenticationError(f"Token refresh failed: {e}") from e

    def logout(self) -> None:
        """Clear stored tokens (local logout)."""
        self._token_storage.clear_tokens()

    def get_current_tokens(self) -> Optional[AuthTokens]:
        """Get current tokens, refreshing if necessary.

        Returns:
            Valid AuthTokens or None if not logged in
        """
        tokens = self._token_storage.get_tokens()
        if not tokens:
            return None

        if tokens.is_expired():
            try:
                tokens = self.refresh(tokens.refresh_token)
            except Exception as e:
                logger.warning(f"Token refresh failed: {e}")
                return None

        return tokens

    def is_authenticated(self) -> bool:
        """Check if user is authenticated.

        Returns:
            True if valid tokens exist
        """
        tokens = self.get_current_tokens()
        return tokens is not None

    # =========================================================================
    # SRP Helper Methods
    # =========================================================================

    def _generate_random_key_pair(self) -> Tuple[int, int]:
        """Generate SRP random key pair."""
        n = int(self._N_HEX, 16)
        g = int(self._g_hex, 16)

        # Generate random small_a
        small_a = int.from_bytes(secrets.token_bytes(128), "big") % n

        # Compute large_a = g^small_a mod n
        large_a = pow(g, small_a, n)

        return small_a, large_a

    def _compute_claim(
        self,
        small_a: int,
        large_a: int,
        username: str,
        password: str,
        salt: str,
        srp_b: str,
        secret_block: str,
        timestamp: str,
    ) -> str:
        """Compute SRP password claim."""
        n = int(self._N_HEX, 16)
        g = int(self._g_hex, 16)
        large_b = int(srp_b, 16)

        # Compute u = H(A | B)
        u = self._compute_u(large_a, large_b)
        if u == 0:
            raise Exception("Invalid SRP u value")

        # Compute x = H(salt | H(pool_id | username | ":" | password))
        pool_name = self.user_pool_id.split("_")[1]
        user_pass_hash = self._hash_sha256(f"{pool_name}{username}:{password}")
        x_hash = self._hash_sha256(bytes.fromhex(self._pad_hex(salt)) + user_pass_hash)
        x = int(x_hash.hex(), 16)

        # Compute k
        k = int(self._hash_sha256(
            bytes.fromhex(self._pad_hex(self._N_HEX)) +
            bytes.fromhex(self._pad_hex(self._g_hex))
        ).hex(), 16)

        # Compute S = (B - k * g^x) ^ (a + u * x) mod N
        g_mod = pow(g, x, n)
        int_val = (large_b - k * g_mod) % n
        s = pow(int_val, small_a + u * x, n)

        # Derive key
        hkdf_key = self._compute_hkdf(
            s_bytes=bytes.fromhex(self._pad_hex(self._long_to_hex(s))),
            u_bytes=bytes.fromhex(self._pad_hex(self._long_to_hex(u))),
        )

        # Compute signature
        # Pool name and username should be UTF-8 bytes, not hex
        pool_name = self.user_pool_id.split("_")[1]
        msg = (
            pool_name.encode("utf-8")
            + username.encode("utf-8")
            + base64.standard_b64decode(secret_block)
            + timestamp.encode("utf-8")
        )

        signature = hmac.new(hkdf_key, msg, hashlib.sha256).digest()
        return base64.standard_b64encode(signature).decode()

    def _compute_u(self, large_a: int, large_b: int) -> int:
        """Compute SRP u value."""
        u_hex = self._hash_sha256(
            bytes.fromhex(self._pad_hex(self._long_to_hex(large_a))) +
            bytes.fromhex(self._pad_hex(self._long_to_hex(large_b)))
        ).hex()
        return int(u_hex, 16)

    def _compute_hkdf(self, s_bytes: bytes, u_bytes: bytes) -> bytes:
        """Compute HKDF key."""
        prk = hmac.new(u_bytes, s_bytes, hashlib.sha256).digest()

        info_bits_update = self._info_bits + bytearray(chr(1), "utf-8")
        return hmac.new(prk, info_bits_update, hashlib.sha256).digest()[:16]

    def _hash_sha256(self, data) -> bytes:
        """Compute SHA256 hash."""
        if isinstance(data, str):
            data = data.encode()
        return hashlib.sha256(data).digest()

    def _pad_hex(self, hex_string: str) -> str:
        """Pad hex string to even length."""
        if len(hex_string) % 2 == 1:
            hex_string = "0" + hex_string
        elif int(hex_string[0:2], 16) >= 128:
            hex_string = "00" + hex_string
        return hex_string

    def _long_to_hex(self, n: int) -> str:
        """Convert long to hex string."""
        return format(n, "x")

    def _extract_user_id(self, id_token: str) -> str:
        """Extract user ID (sub) from ID token."""
        try:
            # JWT is base64url encoded, split by dots
            payload = id_token.split(".")[1]
            # Add padding if needed
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding
            decoded = base64.urlsafe_b64decode(payload)
            claims = json.loads(decoded)
            return claims.get("sub", "")
        except Exception:
            return ""


# Hardcoded Cognito configuration - all users connect to the same Geniable cloud service
DEFAULT_COGNITO_USER_POOL_ID = "ap-southeast-2_5OWr5yHu8"
DEFAULT_COGNITO_CLIENT_ID = "3936nngb9i12t5ei6rjn9fblgc"
DEFAULT_COGNITO_REGION = "ap-southeast-2"


def get_auth_client(
    user_pool_id: Optional[str] = None,
    client_id: Optional[str] = None,
    region: Optional[str] = None,
    use_keyring: bool = True,
) -> CognitoAuthClient:
    """Get configured auth client.

    Args:
        user_pool_id: Cognito User Pool ID (or from env/config/hardcoded default)
        client_id: Cognito App Client ID (or from env/config/hardcoded default)
        region: AWS region (or from env/config/hardcoded default)
        use_keyring: Use system keyring for token storage

    Returns:
        Configured CognitoAuthClient
    """
    # Try to get from environment, fallback to hardcoded defaults
    pool_id = user_pool_id or os.environ.get("GENI_USER_POOL_ID") or DEFAULT_COGNITO_USER_POOL_ID
    cli_id = client_id or os.environ.get("GENI_CLIENT_ID") or DEFAULT_COGNITO_CLIENT_ID
    aws_region = region or os.environ.get("GENI_REGION") or DEFAULT_COGNITO_REGION

    return CognitoAuthClient(
        user_pool_id=pool_id,
        client_id=cli_id,
        region=aws_region,
        use_keyring=use_keyring,
    )
