"""Configuration manager for loading and validating config."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from shared.models.config import AppConfig


DEFAULT_CONFIG_PATH = Path.home() / ".geniable.yaml"


class ConfigManager:
    """Manages application configuration from file and environment."""

    def __init__(self, config_path: Path = None):
        """Initialize the config manager.

        Args:
            config_path: Path to config file (uses default if not provided)
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self._config: Optional[AppConfig] = None

    def load(self) -> AppConfig:
        """Load configuration from file and environment.

        Environment variables override file values.

        Returns:
            Loaded configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If configuration is invalid
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                f"Run 'geni configure' to create it."
            )

        # Load from file
        with open(self.config_path) as f:
            file_config = yaml.safe_load(f)

        # Apply environment variable overrides
        config_dict = self._apply_env_overrides(file_config)

        # Validate and create config
        self._config = AppConfig(**config_dict)
        return self._config

    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to config.

        Supports:
        - LANGSMITH_API_KEY
        - LANGSMITH_PROJECT
        - LANGSMITH_QUEUE
        - JIRA_API_TOKEN
        - NOTION_API_KEY
        - etc.
        """
        # LangSmith overrides
        if "langsmith" not in config:
            config["langsmith"] = {}

        if os.environ.get("LANGSMITH_API_KEY"):
            config["langsmith"]["api_key"] = os.environ["LANGSMITH_API_KEY"]
        if os.environ.get("LANGSMITH_PROJECT"):
            config["langsmith"]["project"] = os.environ["LANGSMITH_PROJECT"]
        if os.environ.get("LANGSMITH_QUEUE"):
            config["langsmith"]["queue"] = os.environ["LANGSMITH_QUEUE"]

        # AWS overrides
        if "aws" not in config:
            config["aws"] = {}

        if os.environ.get("AWS_REGION"):
            config["aws"]["region"] = os.environ["AWS_REGION"]
        if os.environ.get("INTEGRATION_ENDPOINT"):
            config["aws"]["integration_endpoint"] = os.environ["INTEGRATION_ENDPOINT"]
        if os.environ.get("EVALUATION_ENDPOINT"):
            config["aws"]["evaluation_endpoint"] = os.environ["EVALUATION_ENDPOINT"]

        # Provider overrides
        if os.environ.get("ISSUE_PROVIDER"):
            config["provider"] = os.environ["ISSUE_PROVIDER"]

        # Jira overrides
        if config.get("provider") == "jira":
            if "jira" not in config:
                config["jira"] = {}
            if os.environ.get("JIRA_BASE_URL"):
                config["jira"]["base_url"] = os.environ["JIRA_BASE_URL"]
            if os.environ.get("JIRA_EMAIL"):
                config["jira"]["email"] = os.environ["JIRA_EMAIL"]
            if os.environ.get("JIRA_API_TOKEN"):
                config["jira"]["api_token"] = os.environ["JIRA_API_TOKEN"]
            if os.environ.get("JIRA_PROJECT_KEY"):
                config["jira"]["project_key"] = os.environ["JIRA_PROJECT_KEY"]

        # Notion overrides
        if config.get("provider") == "notion":
            if "notion" not in config:
                config["notion"] = {}
            if os.environ.get("NOTION_API_KEY"):
                config["notion"]["api_key"] = os.environ["NOTION_API_KEY"]
            if os.environ.get("NOTION_DATABASE_ID"):
                config["notion"]["database_id"] = os.environ["NOTION_DATABASE_ID"]

        return config

    def get_config(self) -> AppConfig:
        """Get the loaded configuration.

        Returns:
            Configuration (loads if not already loaded)
        """
        if self._config is None:
            return self.load()
        return self._config

    def validate(self) -> bool:
        """Validate the configuration.

        Returns:
            True if valid
        """
        try:
            config = self.load()
            config.get_provider_config()
            return True
        except Exception:
            return False

    @staticmethod
    def create_template(path: Path = None) -> Path:
        """Create a configuration template file.

        Args:
            path: Output path (uses default if not provided)

        Returns:
            Path to created file
        """
        path = path or DEFAULT_CONFIG_PATH

        template = """\
# Geniable Configuration
# Created by: geni configure

langsmith:
  api_key: "ls_your_api_key"
  project: "insights-agent-v2"
  queue: "quality-review"

aws:
  region: "ap-southeast-2"
  integration_endpoint: "https://xxx.execute-api.ap-southeast-2.amazonaws.com/prod"
  evaluation_endpoint: "https://xxx.execute-api.ap-southeast-2.amazonaws.com/prod"
  api_key: ""  # Optional API Gateway key

provider: "jira"  # or "notion"

jira:
  base_url: "https://your-company.atlassian.net"
  email: "your.email@company.com"
  api_token: "your_jira_api_token"
  project_key: "PROJ"

# notion:
#   api_key: "secret_xxx"
#   database_id: "xxx"

defaults:
  report_dir: "./reports"
  log_level: "INFO"
"""

        path.write_text(template)
        path.chmod(0o600)  # Secure permissions

        return path

    @staticmethod
    def save_config(config: Dict[str, Any], path: Path = None) -> Path:
        """Save configuration dictionary to YAML file.

        Args:
            config: Configuration dictionary from wizard
            path: Output path (uses default if not provided)

        Returns:
            Path to saved file
        """
        path = path or DEFAULT_CONFIG_PATH

        # Transform wizard config to YAML format
        yaml_config = ConfigManager._transform_to_yaml_format(config)

        # Generate YAML content with comments
        content = ConfigManager._generate_yaml_content(yaml_config)

        path.write_text(content)
        path.chmod(0o600)  # Secure permissions

        return path

    @staticmethod
    def _transform_to_yaml_format(wizard_config: Dict[str, Any]) -> Dict[str, Any]:
        """Transform wizard configuration to YAML structure.

        Args:
            wizard_config: Configuration from wizard

        Returns:
            Configuration in expected YAML format
        """
        # The wizard config should already be in the correct format
        # Just ensure all required sections exist
        config = wizard_config.copy()

        # Ensure defaults exist
        if "defaults" not in config:
            config["defaults"] = {
                "report_dir": "./reports",
                "log_level": "INFO",
            }

        return config

    @staticmethod
    def _generate_yaml_content(config: Dict[str, Any]) -> str:
        """Generate YAML content with comments.

        Args:
            config: Configuration dictionary

        Returns:
            YAML string with comments
        """
        lines = [
            "# Geniable Configuration",
            "# Created by: geni init",
            "",
        ]

        # LangSmith section
        if "langsmith" in config:
            lines.extend([
                "langsmith:",
                f'  api_key: "{config["langsmith"]["api_key"]}"',
                f'  project: "{config["langsmith"]["project"]}"',
                f'  queue: "{config["langsmith"]["queue"]}"',
                "",
            ])

        # AWS section
        if "aws" in config:
            lines.extend([
                "aws:",
                f'  region: "{config["aws"]["region"]}"',
                f'  integration_endpoint: "{config["aws"]["integration_endpoint"]}"',
                f'  evaluation_endpoint: "{config["aws"]["evaluation_endpoint"]}"',
                f'  api_key: "{config["aws"].get("api_key", "")}"',
                "",
            ])

        # Provider
        provider = config.get("provider", "none")
        lines.append(f'provider: "{provider}"')
        lines.append("")

        # Jira section
        if "jira" in config:
            lines.extend([
                "jira:",
                f'  base_url: "{config["jira"]["base_url"]}"',
                f'  email: "{config["jira"]["email"]}"',
                f'  api_token: "{config["jira"]["api_token"]}"',
                f'  project_key: "{config["jira"]["project_key"]}"',
            ])
            if "issue_type" in config["jira"]:
                lines.append(f'  issue_type: "{config["jira"]["issue_type"]}"')
            lines.append("")

        # Notion section
        if "notion" in config:
            lines.extend([
                "notion:",
                f'  api_key: "{config["notion"]["api_key"]}"',
                f'  database_id: "{config["notion"]["database_id"]}"',
                "",
            ])

        # Defaults section
        if "defaults" in config:
            lines.extend([
                "defaults:",
                f'  report_dir: "{config["defaults"]["report_dir"]}"',
                f'  log_level: "{config["defaults"]["log_level"]}"',
            ])

        return "\n".join(lines) + "\n"
