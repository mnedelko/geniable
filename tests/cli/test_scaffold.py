"""Tests for the scaffold generator."""

import ast
from pathlib import Path
from unittest.mock import patch

import pytest

from cli.scaffold import ProviderModel, ScaffoldConfig, ScaffoldGenerator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FRAMEWORKS = ["langgraph", "strands", "pi"]

EXPECTED_FILES = [
    "agent.py",
    "resilience.py",
    "config.yaml",
    "pyproject.toml",
    "README.md",
    "Makefile",
    ".env.example",
    "prompts/system_prompt.md",
    "tests/__init__.py",
    "tests/test_agent.py",
]


def _make_config(
    framework: str = "langgraph",
    tmp_path: Path | None = None,
    fallbacks: list[ProviderModel] | None = None,
) -> ScaffoldConfig:
    output_dir = str(tmp_path / "test-agent") if tmp_path else "./test-agent"
    return ScaffoldConfig(
        project_name="test-agent",
        description="A test agent",
        framework=framework,
        region="us-east-1",
        primary_model=ProviderModel(
            provider="bedrock",
            model_id="anthropic.claude-sonnet-4-20250514-v1:0",
        ),
        fallback_models=fallbacks or [],
        output_dir=output_dir,
    )


def _make_multi_provider_config(
    framework: str = "langgraph",
    tmp_path: Path | None = None,
) -> ScaffoldConfig:
    """Config with primary + 2 fallbacks across different providers."""
    output_dir = str(tmp_path / "test-agent") if tmp_path else "./test-agent"
    return ScaffoldConfig(
        project_name="test-agent",
        description="A test agent",
        framework=framework,
        region="us-east-1",
        primary_model=ProviderModel(
            provider="bedrock",
            model_id="anthropic.claude-sonnet-4-20250514-v1:0",
        ),
        fallback_models=[
            ProviderModel(provider="openai", model_id="gpt-4o"),
            ProviderModel(provider="ollama", model_id="llama3.2"),
        ],
        output_dir=output_dir,
    )


# ---------------------------------------------------------------------------
# ProviderModel tests
# ---------------------------------------------------------------------------


class TestProviderModel:
    """Test ProviderModel dataclass."""

    def test_creation_with_defaults(self) -> None:
        pm = ProviderModel(provider="bedrock", model_id="test-model")
        assert pm.provider == "bedrock"
        assert pm.model_id == "test-model"
        assert pm.api_key == ""

    def test_creation_with_api_key(self) -> None:
        pm = ProviderModel(provider="openai", model_id="gpt-4o", api_key="sk-test")
        assert pm.api_key == "sk-test"

    def test_all_providers(self) -> None:
        for provider in ("bedrock", "openai", "google", "ollama"):
            pm = ProviderModel(provider=provider, model_id="test")
            assert pm.provider == provider


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

    def test_model_id_backward_compat(self) -> None:
        """model_id property returns primary model ID."""
        config = _make_config()
        assert config.model_id == "anthropic.claude-sonnet-4-20250514-v1:0"

    def test_all_providers_single(self) -> None:
        config = _make_config()
        assert config.all_providers == {"bedrock"}

    def test_all_providers_multi(self) -> None:
        config = _make_multi_provider_config()
        assert config.all_providers == {"bedrock", "openai", "ollama"}

    def test_fallback_models_default_empty(self) -> None:
        config = _make_config()
        assert config.fallback_models == []


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
    def test_agent_py_is_valid_python_with_fallbacks(self, framework: str, tmp_path: Path) -> None:
        """Verify generated agent.py with fallbacks is syntactically valid Python."""
        config = _make_multi_provider_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        ast.parse(agent_source)

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


# ---------------------------------------------------------------------------
# Resilience module generation
# ---------------------------------------------------------------------------


class TestResilienceGeneration:
    """Test resilience.py rendering and content."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_resilience_py_is_valid_python(self, framework: str, tmp_path: Path) -> None:
        """Verify generated resilience.py is syntactically valid Python."""
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "resilience.py").read_text()
        ast.parse(source)

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_resilience_py_has_key_classes(self, framework: str, tmp_path: Path) -> None:
        """Verify resilience.py contains all required classes."""
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "resilience.py").read_text()
        tree = ast.parse(source)
        class_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        for expected in [
            "FailoverReason",
            "FailoverError",
            "ProfileHealthRecord",
            "ModelCandidate",
            "CooldownEngine",
            "CredentialRotator",
            "ModelFallbackRunner",
            "HealthStore",
        ]:
            assert expected in class_names, f"{expected} class not found in resilience.py"

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_resilience_py_has_key_functions(self, framework: str, tmp_path: Path) -> None:
        """Verify resilience.py contains key functions."""
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "resilience.py").read_text()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        for expected in ["classify_error", "load_resilience_config"]:
            assert expected in func_names, f"{expected} function not found in resilience.py"

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_resilience_py_with_fallbacks_is_valid(self, framework: str, tmp_path: Path) -> None:
        """Verify resilience.py is valid even with multi-provider config."""
        config = _make_multi_provider_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "resilience.py").read_text()
        ast.parse(source)


# ---------------------------------------------------------------------------
# Config YAML resilience section
# ---------------------------------------------------------------------------


class TestConfigYamlResilience:
    """Test config.yaml includes resilience section."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_has_resilience_section(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert "resilience:" in config_yaml
        assert "primary:" in config_yaml
        assert 'provider: "bedrock"' in config_yaml

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_has_fallbacks_when_configured(self, framework: str, tmp_path: Path) -> None:
        config = _make_multi_provider_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert "fallbacks:" in config_yaml
        assert 'provider: "openai"' in config_yaml
        assert 'provider: "ollama"' in config_yaml

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_has_cooldowns(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert "cooldowns:" in config_yaml
        assert "transient_tiers:" in config_yaml
        assert "billing_tiers:" in config_yaml


# ---------------------------------------------------------------------------
# .env.example provider-specific vars
# ---------------------------------------------------------------------------


class TestEnvExample:
    """Test .env.example includes correct provider-specific env vars."""

    def test_env_bedrock_only(self, tmp_path: Path) -> None:
        config = _make_config("langgraph", tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        env = (output_path / ".env.example").read_text()
        assert "AWS_REGION" in env
        assert "AWS_PROFILE" in env
        assert "OPENAI_API_KEY" not in env
        assert "GOOGLE_API_KEY" not in env
        assert "OLLAMA_BASE_URL" not in env

    def test_env_multi_provider(self, tmp_path: Path) -> None:
        config = _make_multi_provider_config("langgraph", tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        env = (output_path / ".env.example").read_text()
        assert "AWS_REGION" in env
        assert "OPENAI_API_KEY" in env
        assert "OLLAMA_BASE_URL" in env

    def test_env_google_provider(self, tmp_path: Path) -> None:
        config = ScaffoldConfig(
            project_name="test-agent",
            description="A test agent",
            framework="langgraph",
            region="us-east-1",
            primary_model=ProviderModel(provider="google", model_id="gemini-2.0-flash"),
            fallback_models=[],
            output_dir=str(tmp_path / "test-agent"),
        )
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        env = (output_path / ".env.example").read_text()
        assert "GOOGLE_API_KEY" in env
        assert "AWS_REGION" not in env


# ---------------------------------------------------------------------------
# pyproject.toml provider dependencies
# ---------------------------------------------------------------------------


class TestPyprojectProviderDeps:
    """Test pyproject.toml includes correct provider-specific deps."""

    def test_bedrock_only_has_boto3(self, tmp_path: Path) -> None:
        config = _make_config("langgraph", tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        pyproject = (output_path / "pyproject.toml").read_text()
        assert "boto3" in pyproject
        assert "openai>=" not in pyproject
        assert "google-genai" not in pyproject
        assert "ollama>=" not in pyproject

    def test_multi_provider_has_all_deps(self, tmp_path: Path) -> None:
        config = _make_multi_provider_config("langgraph", tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        pyproject = (output_path / "pyproject.toml").read_text()
        assert "boto3" in pyproject
        assert "openai" in pyproject
        assert "ollama" in pyproject

    def test_google_provider_has_genai(self, tmp_path: Path) -> None:
        config = ScaffoldConfig(
            project_name="test-agent",
            description="A test agent",
            framework="pi",
            region="us-east-1",
            primary_model=ProviderModel(provider="google", model_id="gemini-2.0-flash"),
            fallback_models=[],
            output_dir=str(tmp_path / "test-agent"),
        )
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        pyproject = (output_path / "pyproject.toml").read_text()
        assert "google-genai" in pyproject


# ---------------------------------------------------------------------------
# Section 3 resilience references in framework templates
# ---------------------------------------------------------------------------


class TestSection3Resilience:
    """Test that Section 3 references resilience module when fallbacks present."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_section_3_references_resilience_with_fallbacks(
        self, framework: str, tmp_path: Path
    ) -> None:
        config = _make_multi_provider_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert "from resilience import" in agent_source
        assert "ModelFallbackRunner" in agent_source

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_section_3_without_fallbacks_no_runner(
        self, framework: str, tmp_path: Path
    ) -> None:
        """Without fallbacks, agent.py should not import ModelFallbackRunner."""
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert "ModelFallbackRunner" not in agent_source


# ---------------------------------------------------------------------------
# Agent Section 2 config with fallbacks
# ---------------------------------------------------------------------------


class TestSection2Config:
    """Test Section 2 config reflects provider/fallback settings."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_has_provider_field(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert 'provider: str = "bedrock"' in agent_source

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_has_fallbacks_when_configured(self, framework: str, tmp_path: Path) -> None:
        config = _make_multi_provider_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert "fallbacks" in agent_source
        assert "cooldown_config" in agent_source


# ---------------------------------------------------------------------------
# Wizard flow (mock questionary)
# ---------------------------------------------------------------------------


class TestWizardFlow:
    """Test scaffold wizard with mocked questionary inputs."""

    def test_wizard_creates_config_with_provider(self) -> None:
        """Verify _ask_provider_model returns correct tuple."""
        from cli.commands.scaffold import _ask_provider_model

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.select.return_value.ask.side_effect = ["bedrock", "anthropic.claude-sonnet-4-20250514-v1:0"]
            result = _ask_provider_model("Primary")
            assert result == ("bedrock", "anthropic.claude-sonnet-4-20250514-v1:0", "")

    def test_wizard_asks_api_key_for_openai(self) -> None:
        """Verify API key is requested for OpenAI provider."""
        from cli.commands.scaffold import _ask_provider_model

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.select.return_value.ask.side_effect = ["openai", "gpt-4o"]
            mock_q.text.return_value.ask.return_value = "sk-test"
            result = _ask_provider_model("Primary")
            assert result == ("openai", "gpt-4o", "sk-test")

    def test_wizard_skips_api_key_for_bedrock(self) -> None:
        """Verify API key is NOT requested for Bedrock provider."""
        from cli.commands.scaffold import _ask_provider_model

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.select.return_value.ask.side_effect = ["bedrock", "anthropic.claude-sonnet-4-20250514-v1:0"]
            result = _ask_provider_model("Primary")
            # text() should NOT have been called for api key
            assert result is not None
            assert result[2] == ""  # No API key

    def test_wizard_returns_none_on_abort(self) -> None:
        """Verify wizard returns None when user aborts."""
        from cli.commands.scaffold import _ask_provider_model

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = None
            result = _ask_provider_model("Primary")
            assert result is None
