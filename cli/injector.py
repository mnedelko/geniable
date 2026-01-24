"""Agent code injection for Claude Code visibility."""

import shutil
from pathlib import Path
from typing import Optional, Set

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def get_agent_source_dir() -> Path:
    """Get the source directory for agent code.

    Returns:
        Path to the agent source directory
    """
    # Try to find agent directory relative to this file
    # This works for both installed packages and development
    cli_dir = Path(__file__).parent
    project_root = cli_dir.parent

    agent_dir = project_root / "agent"
    if agent_dir.exists():
        return agent_dir

    # Try importlib.resources for installed packages
    try:
        import importlib.resources as resources

        # For Python 3.9+
        if hasattr(resources, "files"):
            agent_path = resources.files("agent")
            if hasattr(agent_path, "_path"):
                return Path(agent_path._path)
    except (ImportError, ModuleNotFoundError, AttributeError):
        pass

    raise FileNotFoundError(
        "Agent source directory not found. " "Ensure the package is installed correctly."
    )


def get_shared_source_dir() -> Optional[Path]:
    """Get the source directory for shared code.

    Returns:
        Path to the shared source directory, or None if not found
    """
    cli_dir = Path(__file__).parent
    project_root = cli_dir.parent

    shared_dir = project_root / "shared"
    if shared_dir.exists():
        return shared_dir

    return None


def _ignore_patterns(directory: str, files: list) -> Set[str]:
    """Return files to ignore during copy.

    Args:
        directory: Current directory being processed
        files: List of files in the directory

    Returns:
        Set of filenames to ignore
    """
    ignored = set()
    for f in files:
        # Ignore Python cache and compiled files
        if f == "__pycache__" or f.endswith(".pyc") or f.endswith(".pyo"):
            ignored.add(f)
        # Ignore version control
        if f == ".git" or f == ".gitignore":
            ignored.add(f)
        # Ignore IDE settings
        if f == ".idea" or f == ".vscode":
            ignored.add(f)
        # Ignore pytest cache
        if f == ".pytest_cache" or f == ".coverage":
            ignored.add(f)
        # Ignore egg info
        if f.endswith(".egg-info"):
            ignored.add(f)

    return ignored


def inject_agent_code(
    target_dir: Path,
    overwrite: bool = False,
    include_shared: bool = True,
) -> dict:
    """Inject agent code into target directory.

    Args:
        target_dir: Target directory for agent code
        overwrite: Whether to overwrite existing files
        include_shared: Whether to include shared module

    Returns:
        Dictionary with injection results

    Raises:
        FileExistsError: If target exists and overwrite is False
        FileNotFoundError: If source directory not found
    """
    results = {
        "agent_dir": None,
        "shared_dir": None,
        "files_copied": 0,
        "errors": [],
    }

    # Get source directories
    agent_source = get_agent_source_dir()
    shared_source = get_shared_source_dir() if include_shared else None

    # Resolve target paths
    agent_target = target_dir / "agent" if target_dir.name != "agent" else target_dir
    shared_target = target_dir / "shared" if shared_source else None

    # Check for existing directories
    if agent_target.exists() and not overwrite:
        raise FileExistsError(
            f"Agent directory already exists: {agent_target}\n" "Use --force to overwrite."
        )

    if shared_target and shared_target.exists() and not overwrite:
        raise FileExistsError(
            f"Shared directory already exists: {shared_target}\n" "Use --force to overwrite."
        )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Copy agent directory
        task = progress.add_task("Copying agent code...", total=None)

        try:
            # Remove existing if overwriting
            if agent_target.exists():
                shutil.rmtree(agent_target)

            # Copy with ignore patterns
            shutil.copytree(
                agent_source,
                agent_target,
                ignore=_ignore_patterns,
                dirs_exist_ok=False,
            )

            # Count copied files
            agent_files = sum(1 for _ in agent_target.rglob("*.py"))
            results["agent_dir"] = str(agent_target)
            results["files_copied"] += agent_files

        except Exception as e:
            results["errors"].append(f"Agent copy failed: {e}")

        progress.update(task, description="Agent code copied")

        # Copy shared directory if available
        if shared_source:
            progress.update(task, description="Copying shared module...")

            try:
                if shared_target.exists():
                    shutil.rmtree(shared_target)

                shutil.copytree(
                    shared_source,
                    shared_target,
                    ignore=_ignore_patterns,
                    dirs_exist_ok=False,
                )

                shared_files = sum(1 for _ in shared_target.rglob("*.py"))
                results["shared_dir"] = str(shared_target)
                results["files_copied"] += shared_files

            except Exception as e:
                results["errors"].append(f"Shared copy failed: {e}")

            progress.update(task, description="Shared module copied")

        progress.remove_task(task)

    return results
