"""Tests for the mark-done command routing through Lambda backend."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cli.commands.issues import app

runner = CliRunner()


@pytest.fixture()
def mock_auth():
    """Mock authentication to always succeed."""
    with patch("cli.commands.issues._require_auth") as mock:
        yield mock


@pytest.fixture()
def mock_config():
    """Mock ConfigManager to return a valid config."""
    with patch("cli.commands.issues.ConfigManager") as mock_cm:
        config = MagicMock()
        config.provider = "jira"
        config.aws.integration_endpoint = "https://api.example.com/prod"
        config.aws.api_key = "test-key"
        mock_cm.return_value.load.return_value = config
        yield config


@pytest.fixture()
def mock_auth_client():
    """Mock get_auth_client to return valid tokens."""
    with patch("cli.auth.get_auth_client") as mock:
        client = MagicMock()
        tokens = MagicMock()
        tokens.id_token = "test-id-token"
        client.get_current_tokens.return_value = tokens
        mock.return_value = client
        yield client


@pytest.fixture()
def mock_integration_client():
    """Mock IntegrationServiceClient."""
    with patch("agent.api_clients.integration_client.IntegrationServiceClient") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        yield client


class TestMarkDoneCommand:
    """Tests for mark-done command routed through Lambda."""

    def test_success(
        self,
        mock_auth,  # noqa: ARG002
        mock_config,  # noqa: ARG002
        mock_auth_client,  # noqa: ARG002
        mock_integration_client,
    ) -> None:
        """Test successful transition through Lambda."""
        mock_integration_client.transition_ticket.return_value = {
            "success": True,
            "provider": "jira",
            "issue_key": "AIEV-37",
        }

        result = runner.invoke(app, ["mark-done", "AIEV-37"])

        assert result.exit_code == 0
        assert "Done" in result.output
        mock_integration_client.transition_ticket.assert_called_once_with(
            provider="jira",
            issue_key="AIEV-37",
            target_status="Done",
        )

    def test_failure_returns_error(
        self,
        mock_auth,  # noqa: ARG002
        mock_config,  # noqa: ARG002
        mock_auth_client,  # noqa: ARG002
        mock_integration_client,
    ) -> None:
        """Test failed transition shows error message."""
        mock_integration_client.transition_ticket.return_value = {
            "success": False,
            "error": "No 'Done' transition available for AIEV-99",
        }

        result = runner.invoke(app, ["mark-done", "AIEV-99"])

        assert result.exit_code == 1
        assert "No 'Done' transition available" in result.output

    def test_uses_config_provider(
        self,
        mock_auth,  # noqa: ARG002
        mock_config,
        mock_auth_client,  # noqa: ARG002
        mock_integration_client,
    ) -> None:
        """Test that the provider from config is used."""
        mock_config.provider = "notion"
        mock_integration_client.transition_ticket.return_value = {
            "success": True,
            "provider": "notion",
            "issue_key": "PAGE-1",
        }

        result = runner.invoke(app, ["mark-done", "PAGE-1"])

        assert result.exit_code == 0
        mock_integration_client.transition_ticket.assert_called_once_with(
            provider="notion",
            issue_key="PAGE-1",
            target_status="Done",
        )

    def test_api_error_shows_message(
        self,
        mock_auth,  # noqa: ARG002
        mock_config,  # noqa: ARG002
        mock_auth_client,  # noqa: ARG002
        mock_integration_client,
    ) -> None:
        """Test that API errors are caught and displayed."""
        mock_integration_client.transition_ticket.side_effect = Exception(
            "Connection refused"
        )

        result = runner.invoke(app, ["mark-done", "AIEV-37"])

        assert result.exit_code == 1
        assert "Failed to mark issue as done" in result.output
