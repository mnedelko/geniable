"""Claude Code agents for Geniable.

This module contains Claude Code agent files (.md) that define
specialized agents with pre-approved tool permissions.
"""

import logging
import shutil
from importlib import resources
from pathlib import Path

logger = logging.getLogger(__name__)

# Agents included in this package
AGENTS = [
    "Geni Analyzer.md",
]


def get_agents_dir() -> Path:
    """Get the path to the agents directory in the package.

    Returns:
        Path to the agents directory
    """
    # Use importlib.resources for Python 3.9+
    with resources.as_file(resources.files(__package__)) as agents_path:
        return agents_path


def install_agents(
    target_dir: Path | None = None,
    force: bool = False,
    project_root: Path | None = None,
) -> dict[str, bool]:
    """Install Claude Code agents to the project's agents directory.

    Args:
        target_dir: Target directory for agents. Defaults to .claude/agents/ in project root
        force: Overwrite existing files if True
        project_root: Project root directory. Defaults to current working directory

    Returns:
        Dict mapping agent name to success status
    """
    if target_dir is None:
        if project_root is None:
            project_root = Path.cwd()
        target_dir = project_root / ".claude" / "agents"

    # Create target directory if it doesn't exist
    target_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, bool] = {}

    # Get the source agents directory
    source_dir = get_agents_dir()

    for agent_name in AGENTS:
        source_file = source_dir / agent_name
        target_file = target_dir / agent_name

        try:
            if target_file.exists() and not force:
                logger.info(f"Agent already exists: {agent_name} (use force=True to overwrite)")
                results[agent_name] = True
                continue

            shutil.copy2(source_file, target_file)
            logger.info(f"Installed agent: {agent_name} -> {target_file}")
            results[agent_name] = True

        except Exception as e:
            logger.error(f"Failed to install agent {agent_name}: {e}")
            results[agent_name] = False

    return results


def get_installed_agents(
    target_dir: Path | None = None,
    project_root: Path | None = None,
) -> list[str]:
    """Get list of installed Geniable agents.

    Args:
        target_dir: Directory to check. Defaults to .claude/agents/ in project root
        project_root: Project root directory. Defaults to current working directory

    Returns:
        List of installed agent names
    """
    if target_dir is None:
        if project_root is None:
            project_root = Path.cwd()
        target_dir = project_root / ".claude" / "agents"

    installed = []
    for agent_name in AGENTS:
        if (target_dir / agent_name).exists():
            installed.append(agent_name)

    return installed
