"""Claude Code skills for Geniable.

This module contains Claude Code skill files (.md) that define
custom slash commands for the /analyze-latest workflow.
"""

import logging
import shutil
from importlib import resources
from pathlib import Path

logger = logging.getLogger(__name__)

# Skills included in this package
SKILLS = [
    "analyze-latest.md",
]


def get_skills_dir() -> Path:
    """Get the path to the skills directory in the package.

    Returns:
        Path to the skills directory
    """
    # Use importlib.resources for Python 3.9+
    with resources.as_file(resources.files(__package__)) as skills_path:
        return skills_path


def install_skills(target_dir: Path | None = None, force: bool = False) -> dict[str, bool]:
    """Install Claude Code skills to the user's commands directory.

    Args:
        target_dir: Target directory for skills. Defaults to ~/.claude/commands/
        force: Overwrite existing files if True

    Returns:
        Dict mapping skill name to success status
    """
    if target_dir is None:
        target_dir = Path.home() / ".claude" / "commands"

    # Create target directory if it doesn't exist
    target_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, bool] = {}

    # Get the source skills directory
    source_dir = get_skills_dir()

    for skill_name in SKILLS:
        source_file = source_dir / skill_name
        target_file = target_dir / skill_name

        try:
            if target_file.exists() and not force:
                logger.info(f"Skill already exists: {skill_name} (use force=True to overwrite)")
                results[skill_name] = True
                continue

            shutil.copy2(source_file, target_file)
            logger.info(f"Installed skill: {skill_name} -> {target_file}")
            results[skill_name] = True

        except Exception as e:
            logger.error(f"Failed to install skill {skill_name}: {e}")
            results[skill_name] = False

    return results


def get_installed_skills(target_dir: Path | None = None) -> list[str]:
    """Get list of installed Geniable skills.

    Args:
        target_dir: Directory to check. Defaults to ~/.claude/commands/

    Returns:
        List of installed skill names
    """
    if target_dir is None:
        target_dir = Path.home() / ".claude" / "commands"

    installed = []
    for skill_name in SKILLS:
        if (target_dir / skill_name).exists():
            installed.append(skill_name)

    return installed
