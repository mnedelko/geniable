"""Service validation for testing credentials and endpoints during init."""

import logging
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""

    service: str
    success: bool
    message: str
    details: dict[str, Any] | None = None


class ServiceValidator:
    """Validates service credentials and endpoints.

    Used during init to verify configuration before saving.
    """

    # Integration Service can be slow due to LangSmith API calls
    INTEGRATION_SERVICE_TIMEOUT = 30

    def __init__(self, timeout: int = 15):
        """Initialize the validator.

        Args:
            timeout: Request timeout in seconds (default 15s, Integration Service uses 30s)
        """
        self.timeout = timeout

    def validate_langsmith(
        self, api_key: str, queue_name: str | None = None
    ) -> ValidationResult:
        """Validate LangSmith API key and optionally the annotation queue.

        Args:
            api_key: LangSmith API key (should start with 'ls_')
            queue_name: Optional annotation queue name to validate

        Returns:
            Validation result
        """
        try:
            # First validate API key
            response = requests.get(
                "https://api.smith.langchain.com/api/v1/workspaces",
                headers={"x-api-key": api_key},
                timeout=self.timeout,
            )

            if response.status_code == 401:
                return ValidationResult(
                    service="LangSmith",
                    success=False,
                    message="Invalid API key",
                    details={"status_code": 401},
                )
            elif response.status_code != 200:
                return ValidationResult(
                    service="LangSmith",
                    success=False,
                    message=f"Unexpected response: {response.status_code}",
                    details={"status_code": response.status_code},
                )

            data = response.json()
            workspace_count = len(data) if isinstance(data, list) else 1

            # If queue name provided, validate it exists
            if queue_name:
                queue_response = requests.get(
                    "https://api.smith.langchain.com/api/v1/annotation-queues",
                    headers={"x-api-key": api_key},
                    timeout=self.timeout,
                )

                if queue_response.status_code == 200:
                    queues = queue_response.json()
                    queue_names = [q.get("name", "") for q in queues]
                    if queue_name not in queue_names:
                        # Provide helpful suggestion for typos
                        suggestion = ""
                        for q in queue_names:
                            if q.lower().replace(" ", "") == queue_name.lower().replace(" ", ""):
                                suggestion = f" Did you mean '{q}'?"
                                break
                        return ValidationResult(
                            service="LangSmith",
                            success=False,
                            message=f"Annotation queue '{queue_name}' not found.{suggestion}",
                            details={
                                "status_code": 200,
                                "available_queues": queue_names[:5],  # Show first 5
                            },
                        )

            return ValidationResult(
                service="LangSmith",
                success=True,
                message=f"Connected ({workspace_count} workspace(s))",
                details={"status_code": 200},
            )

        except requests.exceptions.Timeout:
            return ValidationResult(
                service="LangSmith",
                success=False,
                message="Connection timeout",
            )
        except requests.exceptions.ConnectionError:
            return ValidationResult(
                service="LangSmith",
                success=False,
                message="Connection failed - check network",
            )
        except Exception as e:
            return ValidationResult(
                service="LangSmith",
                success=False,
                message=f"Validation error: {str(e)}",
            )

    def validate_integration_endpoint(
        self, endpoint: str, api_key: str | None = None, auth_token: str | None = None
    ) -> ValidationResult:
        """Validate Integration Service endpoint.

        Args:
            endpoint: Integration Service URL
            api_key: Optional API Gateway key
            auth_token: Optional Cognito auth token (Bearer token)

        Returns:
            Validation result
        """
        try:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["X-Api-Key"] = api_key
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"

            # Try to fetch threads with limit=1 as a health check
            # Use longer timeout as this endpoint calls LangSmith API
            params: dict[str, str | int] = {"limit": 1, "with_details": "false"}
            response = requests.get(
                f"{endpoint.rstrip('/')}/threads/annotated",
                params=params,
                headers=headers,
                timeout=self.INTEGRATION_SERVICE_TIMEOUT,
            )

            if response.status_code == 200:
                return ValidationResult(
                    service="Integration Service",
                    success=True,
                    message="Connected",
                    details={"status_code": 200},
                )
            elif response.status_code == 403:
                return ValidationResult(
                    service="Integration Service",
                    success=False,
                    message="Access denied - check API key",
                    details={"status_code": 403},
                )
            else:
                return ValidationResult(
                    service="Integration Service",
                    success=False,
                    message=f"Unexpected response: {response.status_code}",
                    details={"status_code": response.status_code},
                )

        except requests.exceptions.Timeout:
            return ValidationResult(
                service="Integration Service",
                success=False,
                message="Connection timeout",
            )
        except requests.exceptions.ConnectionError:
            return ValidationResult(
                service="Integration Service",
                success=False,
                message="Connection failed - check URL",
            )
        except Exception as e:
            return ValidationResult(
                service="Integration Service",
                success=False,
                message=f"Validation error: {str(e)}",
            )

    def validate_evaluation_endpoint(
        self, endpoint: str, api_key: str | None = None, auth_token: str | None = None
    ) -> ValidationResult:
        """Validate Evaluation Service endpoint.

        Args:
            endpoint: Evaluation Service URL
            api_key: Optional API Gateway key (legacy)
            auth_token: Optional Cognito auth token (Bearer token)

        Returns:
            Validation result
        """
        try:
            headers = {"Content-Type": "application/json"}
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"
            if api_key:
                headers["X-Api-Key"] = api_key

            # Try to discover tools as a health check
            response = requests.get(
                f"{endpoint.rstrip('/')}/evaluations/discovery",
                headers=headers,
                timeout=self.timeout,
            )

            if response.status_code == 200:
                data = response.json()
                tools = data.get("tools", [])
                return ValidationResult(
                    service="Evaluation Service",
                    success=True,
                    message=f"Connected ({len(tools)} tools)",
                    details={"status_code": 200, "tool_count": len(tools)},
                )
            elif response.status_code == 403:
                return ValidationResult(
                    service="Evaluation Service",
                    success=False,
                    message="Access denied - check API key",
                    details={"status_code": 403},
                )
            else:
                return ValidationResult(
                    service="Evaluation Service",
                    success=False,
                    message=f"Unexpected response: {response.status_code}",
                    details={"status_code": response.status_code},
                )

        except requests.exceptions.Timeout:
            return ValidationResult(
                service="Evaluation Service",
                success=False,
                message="Connection timeout",
            )
        except requests.exceptions.ConnectionError:
            return ValidationResult(
                service="Evaluation Service",
                success=False,
                message="Connection failed - check URL",
            )
        except Exception as e:
            return ValidationResult(
                service="Evaluation Service",
                success=False,
                message=f"Validation error: {str(e)}",
            )

    def validate_provider_via_lambda(
        self,
        endpoint: str,
        provider: str,
        auth_token: str | None = None,
        api_key: str | None = None,
    ) -> ValidationResult:
        """Validate a provider connection via the Lambda backend.

        Routes the validation through the Lambda backend so that per-user
        credentials stored in AWS are used (no direct Jira/Notion API calls).

        Args:
            endpoint: Integration Service URL
            provider: Provider name ('jira' or 'notion')
            auth_token: Cognito auth token (Bearer token)
            api_key: Optional API Gateway key

        Returns:
            Validation result
        """
        service_name = provider.capitalize()
        try:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"
            if api_key:
                headers["X-Api-Key"] = api_key

            response = requests.post(
                f"{endpoint.rstrip('/')}/integrations/provider/validate",
                json={"provider": provider},
                headers=headers,
                timeout=self.INTEGRATION_SERVICE_TIMEOUT,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    info = data.get("provider_info", {})
                    detail = info.get("project_name") or info.get("base_url") or ""
                    msg = f"Connected{f' to {detail}' if detail else ''}"
                    return ValidationResult(
                        service=service_name,
                        success=True,
                        message=msg,
                        details=info,
                    )
                else:
                    error = data.get("provider_info", {}).get("error", "Validation failed")
                    return ValidationResult(
                        service=service_name,
                        success=False,
                        message=error,
                        details=data.get("provider_info"),
                    )
            elif response.status_code == 401:
                return ValidationResult(
                    service=service_name,
                    success=False,
                    message="Authentication required - run 'geni login'",
                    details={"status_code": 401},
                )
            else:
                return ValidationResult(
                    service=service_name,
                    success=False,
                    message=f"Unexpected response: {response.status_code}",
                    details={"status_code": response.status_code},
                )

        except requests.exceptions.Timeout:
            return ValidationResult(
                service=service_name,
                success=False,
                message="Connection timeout",
            )
        except requests.exceptions.ConnectionError:
            return ValidationResult(
                service=service_name,
                success=False,
                message="Connection failed - check network",
            )
        except Exception as e:
            return ValidationResult(
                service=service_name,
                success=False,
                message=f"Validation error: {str(e)}",
            )

    def validate_all(
        self, config: dict[str, Any], auth_token: str | None = None
    ) -> list[ValidationResult]:
        """Validate all services based on configuration.

        Args:
            config: Configuration dictionary from wizard
            auth_token: Optional Cognito auth token for authenticated endpoints

        Returns:
            List of validation results
        """
        results = []

        # Validate LangSmith (API key + queue name)
        if "langsmith" in config:
            results.append(
                self.validate_langsmith(
                    api_key=config["langsmith"]["api_key"],
                    queue_name=config["langsmith"].get("queue"),
                )
            )

        # Validate AWS endpoints
        endpoint = ""
        api_key_val: str | None = None
        if "aws" in config:
            aws = config["aws"]
            api_key_val = aws.get("api_key") or None
            endpoint = aws["integration_endpoint"]

            results.append(
                self.validate_integration_endpoint(endpoint, api_key_val, auth_token)
            )
            results.append(
                self.validate_evaluation_endpoint(aws["evaluation_endpoint"], api_key_val, auth_token)
            )

        # Validate provider via Lambda (uses per-user credentials)
        provider = config.get("provider", "none")
        if provider in ("jira", "notion") and endpoint:
            results.append(
                self.validate_provider_via_lambda(
                    endpoint=endpoint,
                    provider=provider,
                    auth_token=auth_token,
                    api_key=api_key_val,
                )
            )

        return results

    def format_results(self, results: list[ValidationResult]) -> tuple[bool, str]:
        """Format validation results for display.

        Args:
            results: List of validation results

        Returns:
            Tuple of (all_passed, formatted_string)
        """
        lines = []
        all_passed = True

        for result in results:
            status = "[green]✓[/green]" if result.success else "[red]✗[/red]"
            lines.append(f"  {status} {result.service}: {result.message}")
            if not result.success:
                all_passed = False

        return all_passed, "\n".join(lines)
