"""AWS Secrets Manager integration for secure credential storage.

Syncs local configuration credentials to AWS Secrets Manager for use by
cloud services (Integration Service, Evaluation Service).
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SecretSyncResult:
    """Result of a secret sync operation."""

    secret_name: str
    success: bool
    message: str
    version_id: Optional[str] = None


class SecretsManagerClient:
    """Client for syncing credentials to AWS Secrets Manager.

    Stores credentials in Secrets Manager so they can be accessed by
    cloud services without storing sensitive data in config files.
    """

    # Default secret names - can be overridden via config
    DEFAULT_SECRET_PREFIX = "geniable"

    SECRET_MAPPINGS = {
        "langsmith": {
            "secret_suffix": "langsmith",
            "fields": ["api_key"],
        },
        "jira": {
            "secret_suffix": "jira",
            "fields": ["api_token", "email", "base_url", "project_key"],
        },
        "notion": {
            "secret_suffix": "notion",
            "fields": ["api_key", "database_id"],
        },
        "aws": {
            "secret_suffix": "aws-gateway",
            "fields": ["api_key"],
        },
    }

    def __init__(
        self,
        region: str = "us-east-1",
        secret_prefix: Optional[str] = None,
        kms_key_id: Optional[str] = None,
    ):
        """Initialize the Secrets Manager client.

        Args:
            region: AWS region for Secrets Manager
            secret_prefix: Prefix for secret names (default: geniable)
            kms_key_id: Optional KMS key ID for encryption (uses AWS managed key if not specified)
        """
        self.region = region
        self.secret_prefix = secret_prefix or self.DEFAULT_SECRET_PREFIX
        self.kms_key_id = kms_key_id
        self._client = None

    def _get_client(self):
        """Get or create boto3 Secrets Manager client."""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client("secretsmanager", region_name=self.region)
            except ImportError:
                raise ImportError(
                    "boto3 is required for AWS Secrets Manager integration. "
                    "Install with: pip install boto3"
                )
        return self._client

    def _get_secret_name(self, category: str) -> str:
        """Get the full secret name for a category.

        Args:
            category: Secret category (langsmith, jira, notion, aws)

        Returns:
            Full secret name (e.g., geniable/langsmith)
        """
        mapping = self.SECRET_MAPPINGS.get(category, {})
        suffix = mapping.get("secret_suffix", category)
        return f"{self.secret_prefix}/{suffix}"

    def sync_secret(
        self,
        category: str,
        credentials: Dict[str, Any],
        description: Optional[str] = None,
    ) -> SecretSyncResult:
        """Sync a single secret category to Secrets Manager.

        Args:
            category: Secret category (langsmith, jira, notion, aws)
            credentials: Dictionary of credentials to store
            description: Optional description for the secret

        Returns:
            SecretSyncResult with success status
        """
        secret_name = self._get_secret_name(category)
        mapping = self.SECRET_MAPPINGS.get(category, {})
        fields = mapping.get("fields", list(credentials.keys()))

        # Filter to only specified fields
        secret_value = {k: v for k, v in credentials.items() if k in fields and v}

        if not secret_value:
            return SecretSyncResult(
                secret_name=secret_name,
                success=True,
                message="No credentials to sync",
            )

        try:
            client = self._get_client()
            secret_string = json.dumps(secret_value)

            # Try to update existing secret first
            try:
                response = client.put_secret_value(
                    SecretId=secret_name,
                    SecretString=secret_string,
                )
                return SecretSyncResult(
                    secret_name=secret_name,
                    success=True,
                    message="Secret updated",
                    version_id=response.get("VersionId"),
                )

            except client.exceptions.ResourceNotFoundException:
                # Secret doesn't exist, create it
                create_kwargs = {
                    "Name": secret_name,
                    "SecretString": secret_string,
                    "Description": description or f"LangSmith Analyzer {category} credentials",
                }

                if self.kms_key_id:
                    create_kwargs["KmsKeyId"] = self.kms_key_id

                response = client.create_secret(**create_kwargs)
                return SecretSyncResult(
                    secret_name=secret_name,
                    success=True,
                    message="Secret created",
                    version_id=response.get("VersionId"),
                )

        except Exception as e:
            logger.error(f"Failed to sync {category} credentials: {e}")
            return SecretSyncResult(
                secret_name=secret_name,
                success=False,
                message=str(e),
            )

    def sync_all(self, config: Dict[str, Any]) -> List[SecretSyncResult]:
        """Sync all credentials from config to Secrets Manager.

        Args:
            config: Configuration dictionary (from wizard or loaded config)

        Returns:
            List of SecretSyncResult for each category
        """
        results = []

        # Sync LangSmith credentials
        if "langsmith" in config:
            results.append(
                self.sync_secret("langsmith", config["langsmith"])
            )

        # Sync AWS Gateway API key (if set)
        if "aws" in config and config["aws"].get("api_key"):
            results.append(
                self.sync_secret("aws", {"api_key": config["aws"]["api_key"]})
            )

        # Sync provider credentials
        provider = config.get("provider", "none")

        if provider == "jira" and "jira" in config:
            results.append(
                self.sync_secret("jira", config["jira"])
            )

        if provider == "notion" and "notion" in config:
            results.append(
                self.sync_secret("notion", config["notion"])
            )

        return results

    def get_secret(self, category: str) -> Optional[Dict[str, Any]]:
        """Retrieve a secret from Secrets Manager.

        Args:
            category: Secret category (langsmith, jira, notion, aws)

        Returns:
            Dictionary of credentials or None if not found
        """
        secret_name = self._get_secret_name(category)

        try:
            client = self._get_client()
            response = client.get_secret_value(SecretId=secret_name)
            return json.loads(response["SecretString"])

        except client.exceptions.ResourceNotFoundException:
            logger.debug(f"Secret {secret_name} not found")
            return None

        except Exception as e:
            logger.error(f"Failed to get secret {secret_name}: {e}")
            return None

    def delete_secret(
        self,
        category: str,
        force: bool = False,
    ) -> SecretSyncResult:
        """Delete a secret from Secrets Manager.

        Args:
            category: Secret category to delete
            force: If True, delete immediately without recovery window

        Returns:
            SecretSyncResult with success status
        """
        secret_name = self._get_secret_name(category)

        try:
            client = self._get_client()

            delete_kwargs = {"SecretId": secret_name}
            if force:
                delete_kwargs["ForceDeleteWithoutRecovery"] = True
            else:
                delete_kwargs["RecoveryWindowInDays"] = 7

            client.delete_secret(**delete_kwargs)

            return SecretSyncResult(
                secret_name=secret_name,
                success=True,
                message="Secret scheduled for deletion" if not force else "Secret deleted",
            )

        except client.exceptions.ResourceNotFoundException:
            return SecretSyncResult(
                secret_name=secret_name,
                success=True,
                message="Secret not found (already deleted)",
            )

        except Exception as e:
            logger.error(f"Failed to delete secret {secret_name}: {e}")
            return SecretSyncResult(
                secret_name=secret_name,
                success=False,
                message=str(e),
            )

    def list_secrets(self) -> List[Dict[str, Any]]:
        """List all secrets with the configured prefix.

        Returns:
            List of secret metadata dicts
        """
        try:
            client = self._get_client()
            secrets = []

            paginator = client.get_paginator("list_secrets")
            for page in paginator.paginate(
                Filters=[{"Key": "name", "Values": [f"{self.secret_prefix}/"]}]
            ):
                for secret in page.get("SecretList", []):
                    secrets.append({
                        "name": secret["Name"],
                        "description": secret.get("Description", ""),
                        "last_changed": secret.get("LastChangedDate"),
                        "created": secret.get("CreatedDate"),
                    })

            return secrets

        except Exception as e:
            logger.error(f"Failed to list secrets: {e}")
            return []

    def validate_connection(self) -> bool:
        """Validate connection to AWS Secrets Manager.

        Returns:
            True if connection is valid
        """
        try:
            client = self._get_client()
            # Try to list secrets with our prefix (even if none exist)
            client.list_secrets(
                MaxResults=1,
                Filters=[{"Key": "name", "Values": [f"{self.secret_prefix}/"]}]
            )
            return True

        except Exception as e:
            logger.debug(f"Secrets Manager connection failed: {e}")
            return False


def format_sync_results(results: List[SecretSyncResult]) -> str:
    """Format sync results for display.

    Args:
        results: List of SecretSyncResult

    Returns:
        Formatted string for console output
    """
    lines = []
    for result in results:
        status = "[green]✓[/green]" if result.success else "[red]✗[/red]"
        lines.append(f"  {status} {result.secret_name}: {result.message}")
    return "\n".join(lines)
