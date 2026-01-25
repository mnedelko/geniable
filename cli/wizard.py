"""Interactive configuration wizard for onboarding."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import questionary
from rich.console import Console

from cli.claude_code_setup import ClaudeCodeSetup
from cli.service_validator import ServiceValidator, ValidationResult
from cli.validators import validate_api_key, validate_email, validate_project_key, validate_url

console = Console()
logger = logging.getLogger(__name__)


class ConfigWizard:
    """Interactive wizard for capturing configuration."""

    INTEGRATION_CHOICES = [
        {"name": "Jira", "value": "jira"},
        {"name": "Notion", "value": "notion"},
        {"name": "None (reports only)", "value": "none"},
    ]

    # Hardcoded AWS configuration - users connect to our cloud service
    AWS_CONFIG = {
        "region": "ap-southeast-2",
        "integration_endpoint": "https://qdu9vpxw26.execute-api.ap-southeast-2.amazonaws.com/dev",
        "evaluation_endpoint": "https://qdu9vpxw26.execute-api.ap-southeast-2.amazonaws.com/dev",
        "api_key": "",  # Not required for Cognito-authenticated endpoints
    }

    def __init__(self) -> None:
        """Initialize the wizard."""
        self.config: Dict[str, Any] = {}
        self._user_email: Optional[str] = None
        self._user_id: Optional[str] = None
        self._id_token: Optional[str] = None

    def _load_auth_context(self) -> None:
        """Load authentication context from current session.

        The init command requires authentication, so we can assume
        the user is already authenticated when this runs.
        """
        try:
            from cli.auth import get_auth_client

            auth_client = get_auth_client()
            tokens = auth_client.get_current_tokens()
            if tokens:
                self._user_email = tokens.email
                self._user_id = tokens.user_id
                self._id_token = tokens.id_token
        except Exception as e:
            logger.warning(f"Failed to load auth context: {e}")

    def _setup_claude_code(self) -> None:
        """Set up Claude Code agent integration.

        Checks for CLAUDE.md and guides user through /init setup if needed.
        This enables the /agent workflow in Claude Code to work effectively
        with the Geniable project.

        Also installs Geniable skills to ~/.claude/commands/ for the
        /analyze-latest slash command.
        """
        setup = ClaudeCodeSetup(project_root=Path.cwd())
        setup.run_setup_check()

        # Install Geniable skills
        self._install_skills()

    def _install_skills(self) -> None:
        """Install Geniable Claude Code skills and agents to project directory."""
        from cli.skills import install_agents, install_skills

        project_root = Path.cwd()
        console.print("\n[dim]Installing Geniable skills and agents to project...[/dim]")

        try:
            # Install skills to .claude/commands/ in project
            skill_results = install_skills(force=True, project_root=project_root)
            skill_installed = [name for name, success in skill_results.items() if success]
            skill_failed = [name for name, success in skill_results.items() if not success]

            if skill_installed:
                console.print(f"[green]✓[/green] Installed {len(skill_installed)} skill(s):")
                for skill in skill_installed:
                    console.print(f"  - .claude/commands/{skill}")

            if skill_failed:
                console.print(f"[yellow]![/yellow] Failed to install {len(skill_failed)} skill(s):")
                for skill in skill_failed:
                    console.print(f"  - {skill}")

            # Install agents to .claude/agents/ in project
            agent_results = install_agents(force=True, project_root=project_root)
            agent_installed = [name for name, success in agent_results.items() if success]
            agent_failed = [name for name, success in agent_results.items() if not success]

            if agent_installed:
                console.print(f"[green]✓[/green] Installed {len(agent_installed)} agent(s):")
                for agent in agent_installed:
                    console.print(f"  - .claude/agents/{agent}")

            if agent_failed:
                console.print(f"[yellow]![/yellow] Failed to install {len(agent_failed)} agent(s):")
                for agent in agent_failed:
                    console.print(f"  - {agent}")

            # Configure Claude Code permissions for geni commands
            self._configure_claude_code_permissions()

            console.print("\n[dim]Available: /analyze-latest (uses Geni Analyzer agent)[/dim]")
            console.print(
                "\n[yellow]Note:[/yellow] If Claude Code is currently running, "
                "restart it to detect the new command."
            )

        except Exception as e:
            console.print(f"[yellow]![/yellow] Failed to install skills/agents: {e}")
            console.print("[dim]You can install manually later.[/dim]")

    def _configure_claude_code_permissions(self) -> None:
        """Configure Claude Code to pre-approve geni commands.

        Updates .claude/settings.local.json in the project to add geni command permissions
        to permissions.allow, so the Geni Analyzer agent can run without permission prompts.

        Claude Code uses colon-based patterns: Bash(command:*) matches any command starting with 'command'.
        """
        import json

        project_root = Path.cwd()
        settings_path = project_root / ".claude" / "settings.local.json"

        # Permission patterns using Claude Code's colon format
        # Bash(prefix:*) matches any command starting with 'prefix'
        geni_permissions = [
            "Bash(geni:*)",                    # All geni commands
            "Bash(geni analyze:*)",            # geni analyze subcommands
            "Bash(geni analyze fetch:*)",      # geni analyze fetch
            "Bash(geni analyze mark-done:*)",  # geni analyze mark-done
            "Bash(geni ticket:*)",             # geni ticket subcommands
            "Bash(geni ticket create:*)",      # geni ticket create
        ]

        try:
            # Load existing settings or create new
            if settings_path.exists():
                with open(settings_path) as f:
                    settings = json.load(f)
            else:
                settings = {}

            # Ensure permissions.allow structure exists
            if "permissions" not in settings:
                settings["permissions"] = {}
            if "allow" not in settings["permissions"]:
                settings["permissions"]["allow"] = []
            elif not isinstance(settings["permissions"]["allow"], list):
                settings["permissions"]["allow"] = []

            # Add geni permissions if not already present
            added = []
            for permission in geni_permissions:
                if permission not in settings["permissions"]["allow"]:
                    settings["permissions"]["allow"].append(permission)
                    added.append(permission)

            if added:
                # Write back settings
                settings_path.parent.mkdir(parents=True, exist_ok=True)
                with open(settings_path, "w") as f:
                    json.dump(settings, f, indent=2)

                console.print(f"[green]✓[/green] Configured Claude Code permissions:")
                console.print(f"  - Added {len(added)} permission(s) to .claude/settings.local.json")
            else:
                console.print(f"[green]✓[/green] Claude Code permissions already configured")

        except Exception as e:
            console.print(f"[yellow]![/yellow] Could not configure Claude Code permissions: {e}")
            console.print(
                "[dim]You can manually add geni permissions to "
                ".claude/settings.local.json permissions.allow[/dim]"
            )

    def run(self, skip_validation: bool = False) -> Dict[str, Any]:
        """Run the complete wizard flow.

        Args:
            skip_validation: Skip service validation step

        Returns:
            Configuration dictionary ready for saving

        Raises:
            RuntimeError: If cloud sync fails (required)
        """
        console.print("\n[bold cyan]Geni Setup Wizard[/bold cyan]")
        console.print("This wizard will help you configure the analyzer.\n")

        # Load authentication context (user is already authenticated)
        self._load_auth_context()
        console.print(f"[green]✓ Logged in as {self._user_email}[/green]\n")

        total_steps = 5

        # Step 1: Claude Code Agent Setup
        console.print(f"[bold]Step 1/{total_steps}: Claude Code Agent Setup[/bold]")
        self._setup_claude_code()

        # Step 2: LangSmith configuration
        console.print(f"\n[bold]Step 2/{total_steps}: LangSmith Configuration[/bold]")
        self._capture_langsmith_config()

        # Set hardcoded AWS configuration (users connect to our cloud service)
        self.config["aws"] = self.AWS_CONFIG.copy()

        # Step 3: Integration selection
        console.print(f"\n[bold]Step 3/{total_steps}: Issue Tracker Integration[/bold]")
        integration = self._select_integration()

        if integration == "jira":
            self._capture_jira_credentials()
        elif integration == "notion":
            self._capture_notion_credentials()
        else:
            self.config["provider"] = "none"

        # Set defaults
        self.config["defaults"] = {
            "report_dir": "./reports",
            "log_level": "INFO",
        }

        # Step 4: Sync to cloud FIRST (required - credentials must be stored before validation)
        console.print(f"\n[bold]Step 4/{total_steps}: Cloud Sync[/bold]")
        self._sync_to_cloud()

        # Step 5: Validate services (now Lambda has the credentials)
        if not skip_validation:
            console.print(f"\n[bold]Step 5/{total_steps}: Service Validation[/bold]")
            self._validate_services()

        return self.config

    def _sync_to_cloud(self) -> None:
        """Sync configuration to cloud backend.

        Uses the authenticated API to store user configuration and secrets.
        This is required - there is no local-only mode.

        Raises:
            RuntimeError: If cloud sync fails
        """
        console.print("[dim]Syncing configuration to cloud (per-user storage)...[/dim]")

        import requests

        # Use stored token from auth context
        if not self._id_token:
            raise RuntimeError(
                "No authentication token available.\n" "Please run 'geni login' first."
            )

        # Get API endpoint from config
        endpoint = self.config.get("aws", {}).get("integration_endpoint", "")
        if not endpoint:
            raise RuntimeError(
                "No integration endpoint configured.\n"
                "Please provide the Integration Service Endpoint URL."
            )

        # Prepare config and secrets for API
        # Separate sensitive credentials from config
        secrets = {}
        config_to_save = {}

        # LangSmith
        if self.config.get("langsmith"):
            secrets["langsmith_api_key"] = self.config["langsmith"].get("api_key", "")
            config_to_save["langsmith"] = {
                "project": self.config["langsmith"].get("project"),
                "queue": self.config["langsmith"].get("queue"),
            }

        # AWS
        if self.config.get("aws"):
            secrets["aws_api_key"] = self.config["aws"].get("api_key", "")
            config_to_save["aws"] = {
                "region": self.config["aws"].get("region"),
                "integration_endpoint": self.config["aws"].get("integration_endpoint"),
                "evaluation_endpoint": self.config["aws"].get("evaluation_endpoint"),
            }

        # Provider
        config_to_save["provider"] = self.config.get("provider", "none")

        # Jira
        if self.config.get("jira"):
            secrets["jira_api_token"] = self.config["jira"].get("api_token", "")
            config_to_save["jira"] = {
                "base_url": self.config["jira"].get("base_url"),
                "email": self.config["jira"].get("email"),
                "project_key": self.config["jira"].get("project_key"),
                "issue_type": self.config["jira"].get("issue_type"),
            }

        # Notion
        if self.config.get("notion"):
            secrets["notion_api_key"] = self.config["notion"].get("api_key", "")
            config_to_save["notion"] = {
                "database_id": self.config["notion"].get("database_id"),
            }

        # Call authenticated API to save config
        headers = {
            "Authorization": f"Bearer {self._id_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "config": config_to_save,
            "secrets": secrets,
        }

        try:
            url = f"{endpoint.rstrip('/')}/users/me/config"
            response = requests.post(url, json=payload, headers=headers, timeout=30)

            if response.status_code == 200:
                console.print("\n[green]✓ Configuration synced to cloud[/green]")
                console.print("[dim]Your credentials are stored securely per-user in AWS.[/dim]")
            elif response.status_code == 401:
                raise RuntimeError(
                    "Session expired.\n" "Please run 'geni login' to re-authenticate."
                )
            else:
                error_detail = ""
                try:
                    error_detail = response.json().get("message", response.text)
                except Exception:
                    error_detail = response.text
                raise RuntimeError(
                    f"Cloud sync failed (HTTP {response.status_code}): {error_detail}"
                )

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Cloud sync failed: {e}")

    def _validate_services(self) -> None:
        """Validate all configured services."""
        validate = questionary.confirm(
            "Test credentials and endpoints now?",
            default=True,
        ).ask()

        if validate is None:
            raise KeyboardInterrupt("Wizard cancelled")

        if not validate:
            console.print("[dim]Skipping validation. Run 'geni configure --validate' later.[/dim]")
            return

        console.print("\n[dim]Testing connections...[/dim]")

        validator = ServiceValidator()
        results = validator.validate_all(self.config, auth_token=self._id_token)

        # Display results
        all_passed = True
        for result in results:
            status = "[green]✓[/green]" if result.success else "[red]✗[/red]"
            console.print(f"  {status} {result.service}: {result.message}")
            if not result.success:
                all_passed = False

        if not all_passed:
            console.print("\n[yellow]Some validations failed.[/yellow]")
            console.print(
                "[dim]Your configuration has been saved. You can re-validate with 'geni validate'[/dim]"
            )
        else:
            console.print("\n[green]All services validated successfully![/green]")

    def _select_integration(self) -> str:
        """Select issue tracker integration.

        Returns:
            Selected integration: 'jira', 'notion', or 'none'
        """
        choice = questionary.select(
            "Select your issue tracker:",
            choices=[c["name"] for c in self.INTEGRATION_CHOICES],
        ).ask()

        if choice is None:
            raise KeyboardInterrupt("Wizard cancelled")

        # Map display name back to value
        for c in self.INTEGRATION_CHOICES:
            if c["name"] == choice:
                return c["value"]

        return "none"

    def _capture_langsmith_config(self) -> None:
        """Capture LangSmith configuration."""
        api_key = questionary.password(
            "LangSmith API Key:",
            validate=lambda x: validate_api_key(x, prefix="ls")
            or "Invalid API key format (should start with 'ls')",
        ).ask()

        if api_key is None:
            raise KeyboardInterrupt("Wizard cancelled")

        project = questionary.text(
            "LangSmith Project Name:",
            default="default",
            validate=lambda x: len(x) > 0 or "Project name is required",
        ).ask()

        if project is None:
            raise KeyboardInterrupt("Wizard cancelled")

        queue = questionary.text(
            "Annotation Queue Name:",
            default="quality-review",
            validate=lambda x: len(x) > 0 or "Queue name is required",
        ).ask()

        if queue is None:
            raise KeyboardInterrupt("Wizard cancelled")

        self.config["langsmith"] = {
            "api_key": api_key,
            "project": project,
            "queue": queue,
        }

    def _capture_jira_credentials(self) -> None:
        """Capture Jira integration credentials."""
        console.print("\n[dim]Configure Jira integration[/dim]")

        base_url = questionary.text(
            "Jira Base URL (e.g., https://company.atlassian.net):",
            validate=lambda x: validate_url(x) or "Invalid URL format",
        ).ask()

        if base_url is None:
            raise KeyboardInterrupt("Wizard cancelled")

        email = questionary.text(
            "Jira Email:",
            validate=lambda x: validate_email(x) or "Invalid email format",
        ).ask()

        if email is None:
            raise KeyboardInterrupt("Wizard cancelled")

        api_token = questionary.password(
            "Jira API Token:",
            validate=lambda x: len(x) > 10 or "API token seems too short",
        ).ask()

        if api_token is None:
            raise KeyboardInterrupt("Wizard cancelled")

        project_key = questionary.text(
            "Jira Project Key (e.g., PROJ):",
            validate=lambda x: validate_project_key(x)
            or "Invalid project key format (use uppercase letters)",
        ).ask()

        if project_key is None:
            raise KeyboardInterrupt("Wizard cancelled")

        issue_type = questionary.select(
            "Default Issue Type:",
            choices=["Bug", "Task", "Story", "Improvement"],
            default="Bug",
        ).ask()

        if issue_type is None:
            raise KeyboardInterrupt("Wizard cancelled")

        self.config["provider"] = "jira"
        self.config["jira"] = {
            "base_url": base_url.rstrip("/"),
            "email": email,
            "api_token": api_token,
            "project_key": project_key.upper(),
            "issue_type": issue_type,
        }

    def _capture_notion_credentials(self) -> None:
        """Capture Notion integration credentials."""
        console.print("\n[dim]Configure Notion integration[/dim]")

        api_key = questionary.password(
            "Notion API Key (starts with 'secret_'):",
            validate=lambda x: x.startswith("secret_")
            or "Notion API key should start with 'secret_'",
        ).ask()

        if api_key is None:
            raise KeyboardInterrupt("Wizard cancelled")

        database_id = questionary.text(
            "Notion Database ID:",
            validate=lambda x: len(x) == 32
            or len(x) == 36
            or "Database ID should be 32 characters (without dashes) or 36 (with dashes)",
        ).ask()

        if database_id is None:
            raise KeyboardInterrupt("Wizard cancelled")

        self.config["provider"] = "notion"
        self.config["notion"] = {
            "api_key": api_key,
            "database_id": database_id.replace("-", ""),
        }
