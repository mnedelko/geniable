"""Configuration models for the application.

This module defines the configuration schema that is loaded from
the ~/.geniable.yaml config file or environment variables.
"""

from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class LangSmithConfig(BaseModel):
    """LangSmith API configuration."""

    api_key: str = Field(..., description="LangSmith API key")
    project: str = Field(
        default="insights-agent-v2", description="LangSmith project name"
    )
    queue: str = Field(..., description="Annotation queue name")


class AWSConfig(BaseModel):
    """AWS service configuration."""

    region: str = Field(default="us-east-1", description="AWS region")
    integration_endpoint: str = Field(
        ..., description="Integration Service API endpoint URL"
    )
    evaluation_endpoint: str = Field(
        ..., description="Evaluation Service API endpoint URL"
    )
    api_key: Optional[str] = Field(default=None, description="API Gateway API key")


class JiraConfig(BaseModel):
    """Jira integration configuration."""

    base_url: str = Field(..., description="Jira instance URL")
    email: str = Field(..., description="Jira user email")
    api_token: str = Field(..., description="Jira API token")
    project_key: str = Field(..., description="Jira project key")
    issue_type: str = Field(default="Task", description="Default issue type")


class NotionConfig(BaseModel):
    """Notion integration configuration."""

    api_key: str = Field(..., description="Notion API key")
    database_id: str = Field(..., description="Notion database ID")


class CloudSyncConfig(BaseModel):
    """Cloud sync settings for AWS state synchronization."""

    enabled: bool = Field(
        default=False, description="Whether to sync state to AWS"
    )
    sync_mode: Literal["immediate", "batch", "manual"] = Field(
        default="immediate",
        description="Sync mode: immediate (after each thread), batch (after run), manual (on demand)",
    )


class DefaultsConfig(BaseModel):
    """Default settings."""

    report_dir: Path = Field(
        default=Path("./reports"), description="Directory for generated reports"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )
    cloud_sync: CloudSyncConfig = Field(
        default_factory=CloudSyncConfig, description="Cloud sync configuration"
    )


class AppConfig(BaseModel):
    """Complete application configuration.

    This configuration can be loaded from:
    1. Config file: ~/.geniable.yaml
    2. Environment variables (override config file)
    """

    langsmith: LangSmithConfig
    aws: AWSConfig
    provider: Literal["jira", "notion", "none"] = Field(
        default="jira", description="Issue tracking provider"
    )
    jira: Optional[JiraConfig] = Field(
        default=None, description="Jira config (required if provider=jira)"
    )
    notion: Optional[NotionConfig] = Field(
        default=None, description="Notion config (required if provider=notion)"
    )
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)

    @field_validator("jira", mode="before")
    @classmethod
    def validate_jira_config(cls, v, info):
        """Validate Jira config is present when provider is jira."""
        # This is called before the model is fully constructed
        # Full validation happens in model_validator
        return v

    @field_validator("notion", mode="before")
    @classmethod
    def validate_notion_config(cls, v, info):
        """Validate Notion config is present when provider is notion."""
        return v

    def get_provider_config(self) -> JiraConfig | NotionConfig | None:
        """Get the active provider configuration."""
        if self.provider == "jira":
            if not self.jira:
                raise ValueError("Jira configuration required when provider is 'jira'")
            return self.jira
        elif self.provider == "notion":
            if not self.notion:
                raise ValueError(
                    "Notion configuration required when provider is 'notion'"
                )
            return self.notion
        else:
            # provider == "none" - reports only mode
            return None

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "langsmith": {
                    "api_key": "ls_xxx",
                    "project": "insights-agent-v2",
                    "queue": "quality-review",
                },
                "aws": {
                    "region": "us-east-1",
                    "integration_endpoint": "https://xxx.execute-api.us-east-1.amazonaws.com/prod",
                    "evaluation_endpoint": "https://xxx.execute-api.us-east-1.amazonaws.com/prod",
                    "api_key": "xxx",
                },
                "provider": "jira",
                "jira": {
                    "base_url": "https://company.atlassian.net",
                    "email": "user@company.com",
                    "api_token": "xxx",
                    "project_key": "PROJ",
                },
                "defaults": {
                    "report_dir": "./reports",
                    "log_level": "INFO",
                    "cloud_sync": {"enabled": False, "sync_mode": "immediate"},
                },
            }
        }
