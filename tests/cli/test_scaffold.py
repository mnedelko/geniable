"""Tests for the scaffold generator."""

import ast
from pathlib import Path

import pytest

from cli.scaffold import ScaffoldConfig, ScaffoldGenerator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FRAMEWORKS = ["langgraph", "strands", "pi"]

EXPECTED_FILES = [
    "agent.py",
    "config.yaml",
    "pyproject.toml",
    "README.md",
    "Makefile",
    ".env.example",
    "prompts/system_prompt.md",
    "tests/__init__.py",
    "tests/test_agent.py",
]


def _make_config(framework: str = "langgraph", tmp_path: Path | None = None) -> ScaffoldConfig:
    output_dir = str(tmp_path / "test-agent") if tmp_path else "./test-agent"
    return ScaffoldConfig(
        project_name="test-agent",
        description="A test agent",
        framework=framework,
        region="us-east-1",
        model_id="anthropic.claude-sonnet-4-20250514-v1:0",
        output_dir=output_dir,
    )


# ---------------------------------------------------------------------------
# ScaffoldConfig validation
# ---------------------------------------------------------------------------


class TestScaffoldConfig:
    """Test ScaffoldConfig validation."""

    def test_valid_project_name(self) -> None:
        config = _make_config()
        config.validate()  # Should not raise

    @pytest.mark.parametrize(
        "name",
        [
            "Invalid",  # uppercase
            "1invalid",  # starts with number
            "in valid",  # space
            "in.valid",  # dot
            "",  # empty
        ],
    )
    def test_invalid_project_names(self, name: str) -> None:
        config = _make_config()
        config.project_name = name
        with pytest.raises(ValueError, match="Invalid project name"):
            config.validate()

    def test_valid_project_name_with_hyphens_and_underscores(self) -> None:
        config = _make_config()
        config.project_name = "my-cool_agent-2"
        config.validate()

    def test_invalid_framework(self) -> None:
        config = _make_config()
        config.framework = "unknown"
        with pytest.raises(ValueError, match="Unknown framework"):
            config.validate()

    def test_module_name_replaces_hyphens(self) -> None:
        config = _make_config()
        config.project_name = "my-agent"
        assert config.module_name == "my_agent"


# ---------------------------------------------------------------------------
# File tree generation
# ---------------------------------------------------------------------------


class TestScaffoldGenerator:
    """Test that ScaffoldGenerator creates the expected file tree."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_generates_all_files(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        for rel in EXPECTED_FILES:
            file_path = output_path / rel
            assert file_path.exists(), f"Missing file: {rel} (framework={framework})"

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_py_is_valid_python(self, framework: str, tmp_path: Path) -> None:
        """Verify generated agent.py is syntactically valid Python."""
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        ast.parse(agent_source)  # Raises SyntaxError if invalid

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_py_has_all_sections(self, framework: str, tmp_path: Path) -> None:
        """Verify all 9 section markers (0-8) are present."""
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        for section_num in range(9):
            assert f"# {section_num}." in agent_source, (
                f"Section {section_num} marker missing (framework={framework})"
            )

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_py_has_config_class(self, framework: str, tmp_path: Path) -> None:
        """Config and EvaluatorOutput classes should be defined."""
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        tree = ast.parse(agent_source)
        class_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        assert "Config" in class_names
        assert "EvaluatorOutput" in class_names

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_readme_has_principles(self, framework: str, tmp_path: Path) -> None:
        """README should contain the 20 principles table."""
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        readme = (output_path / "README.md").read_text()
        assert "Design Principles" in readme
        assert "Serverless Agency" in readme
        assert "Graceful Degradation" in readme

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_has_framework(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert f'framework: "{framework}"' in config_yaml

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_test_file_is_valid_python(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        test_source = (output_path / "tests" / "test_agent.py").read_text()
        ast.parse(test_source)

    def test_refuses_non_empty_directory(self, tmp_path: Path) -> None:
        """Should refuse to overwrite a non-empty directory."""
        config = _make_config("langgraph", tmp_path)
        output_path = Path(config.output_dir)
        output_path.mkdir(parents=True)
        (output_path / "existing.txt").write_text("existing content")

        generator = ScaffoldGenerator(config)
        with pytest.raises(FileExistsError, match="not empty"):
            generator.generate()

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_pyproject_has_framework_deps(self, framework: str, tmp_path: Path) -> None:
        """pyproject.toml should include framework-specific dependencies."""
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        pyproject = (output_path / "pyproject.toml").read_text()
        if framework == "langgraph":
            assert "langgraph" in pyproject
            assert "langchain-aws" in pyproject
        elif framework == "strands":
            assert "strands-agents" in pyproject
        elif framework == "pi":
            assert "litellm" in pyproject

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_has_principles_comments(self, framework: str, tmp_path: Path) -> None:
        """agent.py should contain principle references as comments."""
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert "Principle" in agent_source
