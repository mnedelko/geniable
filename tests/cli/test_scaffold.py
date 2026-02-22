"""Tests for the scaffold generator."""

import ast
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from cli.scaffold import (
    IdentityLayerConfig,
    LangSmithConfig,
    ObservabilityConfig,
    ProviderModel,
    ScaffoldConfig,
    ScaffoldGenerator,
    SessionConfig,
    SkillsConfig,
    ToolGovernanceConfig,
    ToolsConfig,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FRAMEWORKS = ["langgraph", "strands", "pi"]

EXPECTED_FILES = [
    "agent.py",
    "resilience.py",
    "tool_policy.py",
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
    identity: IdentityLayerConfig | None = None,
    tool_governance: ToolGovernanceConfig | None = None,
    langsmith: LangSmithConfig | None = None,
    sessions: SessionConfig | None = None,
    skills: SkillsConfig | None = None,
    tools: ToolsConfig | None = None,
    observability: ObservabilityConfig | None = None,
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
        identity=identity or IdentityLayerConfig(),
        tool_governance=tool_governance or ToolGovernanceConfig(),
        langsmith=langsmith or LangSmithConfig(),
        sessions=sessions or SessionConfig(),
        skills=skills or SkillsConfig(),
        tools=tools or ToolsConfig(),
        observability=observability or ObservabilityConfig(),
    )


def _make_identity_config(
    framework: str = "langgraph",
    tmp_path: Path | None = None,
    preset: str = "professional",
    rules_focus: list[str] | None = None,
    layers: list[str] | None = None,
) -> ScaffoldConfig:
    """Create a config with identity layers enabled."""
    identity = IdentityLayerConfig(
        enabled=True,
        layers=layers or [
            "rules", "personality", "identity", "tools",
            "user", "memory", "bootstrap", "duties",
        ],
        personality_preset=preset,
        rules_focus=rules_focus or ["safety", "tool_governance", "output_quality"],
    )
    return _make_config(framework=framework, tmp_path=tmp_path, identity=identity)


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


def _make_langsmith_config(
    framework: str = "langgraph",
    tmp_path: Path | None = None,
) -> ScaffoldConfig:
    """Create a config with LangSmith tracing enabled."""
    return _make_config(
        framework=framework,
        tmp_path=tmp_path,
        langsmith=LangSmithConfig(enabled=True, project="test-project"),
    )


def _make_session_config(
    framework: str = "langgraph",
    tmp_path: Path | None = None,
    maintenance_mode: str = "warn",
) -> ScaffoldConfig:
    """Create a config with session persistence enabled."""
    return _make_config(
        framework=framework,
        tmp_path=tmp_path,
        sessions=SessionConfig(enabled=True, maintenance_mode=maintenance_mode),
    )


def _make_skills_config(
    framework: str = "langgraph",
    tmp_path: Path | None = None,
) -> ScaffoldConfig:
    """Create a config with skills enabled."""
    return _make_config(
        framework=framework,
        tmp_path=tmp_path,
        skills=SkillsConfig(enabled=True),
    )


def _make_tools_config(
    framework: str = "langgraph",
    tmp_path: Path | None = None,
) -> ScaffoldConfig:
    """Create a config with tools enabled."""
    return _make_config(
        framework=framework,
        tmp_path=tmp_path,
        tools=ToolsConfig(enabled=True),
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


# ---------------------------------------------------------------------------
# Identity Layer Config (Principle 3)
# ---------------------------------------------------------------------------


class TestIdentityLayerConfig:
    """Test IdentityLayerConfig dataclass."""

    def test_defaults(self) -> None:
        config = IdentityLayerConfig()
        assert config.enabled is False
        assert len(config.layers) == 8
        assert config.personality_preset == "professional"
        assert "safety" in config.rules_focus

    def test_custom_layers(self) -> None:
        config = IdentityLayerConfig(enabled=True, layers=["rules", "tools"])
        assert config.layers == ["rules", "tools"]

    def test_custom_preset(self) -> None:
        config = IdentityLayerConfig(personality_preset="friendly")
        assert config.personality_preset == "friendly"

    def test_custom_rules_focus(self) -> None:
        config = IdentityLayerConfig(rules_focus=["data_privacy", "error_handling"])
        assert config.rules_focus == ["data_privacy", "error_handling"]

    def test_scaffold_config_default_identity(self) -> None:
        """ScaffoldConfig should have identity disabled by default."""
        config = _make_config()
        assert config.identity.enabled is False


# ---------------------------------------------------------------------------
# Brief packet generation
# ---------------------------------------------------------------------------


class TestBriefPacketGeneration:
    """Test render_brief_packet_py() produces valid Python."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_brief_packet_is_valid_python(self, framework: str, tmp_path: Path) -> None:
        config = _make_identity_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "brief_packet.py").read_text()
        ast.parse(source)

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_brief_packet_has_key_functions(self, framework: str, tmp_path: Path) -> None:
        config = _make_identity_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "brief_packet.py").read_text()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        assert "assemble_brief_packet" in func_names
        assert "_truncate" in func_names
        assert "_read_layer" in func_names

    def test_brief_packet_not_generated_when_disabled(self, tmp_path: Path) -> None:
        config = _make_config("langgraph", tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        assert not (output_path / "brief_packet.py").exists()


# ---------------------------------------------------------------------------
# Identity layer file content
# ---------------------------------------------------------------------------


class TestIdentityLayerFiles:
    """Test each render_identity_*() method produces non-empty markdown."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_all_8_layer_files_generated(self, framework: str, tmp_path: Path) -> None:
        config = _make_identity_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        identity_dir = output_path / "identity"
        assert identity_dir.is_dir()
        expected_files = [
            "RULES.md", "PERSONALITY.md", "IDENTITY.md", "TOOLS.md",
            "USER.md", "MEMORY.md", "BOOTSTRAP.md", "DUTIES.md",
        ]
        for f in expected_files:
            path = identity_dir / f
            assert path.exists(), f"Missing identity file: {f}"
            assert len(path.read_text()) > 0, f"Empty identity file: {f}"

    def test_identity_dir_not_created_when_disabled(self, tmp_path: Path) -> None:
        config = _make_config("langgraph", tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        assert not (output_path / "identity").exists()

    @pytest.mark.parametrize(
        "preset",
        ["professional", "friendly", "technical", "concise", "custom"],
    )
    def test_personality_presets_differ(self, preset: str, tmp_path: Path) -> None:
        config = _make_identity_config("langgraph", tmp_path, preset=preset)
        generator = ScaffoldGenerator(config)
        template = generator._get_template()
        content = template.render_identity_personality()
        assert "# Personality" in content
        assert len(content) > 20

    def test_personality_presets_produce_different_content(self, tmp_path: Path) -> None:
        contents = set()
        for preset in ["professional", "friendly", "technical", "concise", "custom"]:
            config = _make_identity_config("langgraph", tmp_path, preset=preset)
            template = ScaffoldGenerator(config)._get_template()
            contents.add(template.render_identity_personality())
        assert len(contents) == 5, "Each preset should produce unique content"

    def test_rules_focus_areas_produce_correct_blocks(self) -> None:
        for focus in ["safety", "tool_governance", "data_privacy", "output_quality", "error_handling"]:
            config = _make_identity_config(rules_focus=[focus])
            template = ScaffoldGenerator(config)._get_template()
            content = template.render_identity_rules()
            assert "# Operational Rules" in content
            # Each focus area should add at least one sub-heading
            assert "## " in content

    def test_rules_all_focus_areas(self) -> None:
        all_focus = ["safety", "tool_governance", "data_privacy", "output_quality", "error_handling"]
        config = _make_identity_config(rules_focus=all_focus)
        template = ScaffoldGenerator(config)._get_template()
        content = template.render_identity_rules()
        assert "Safety" in content
        assert "Tool Governance" in content
        assert "Data Privacy" in content
        assert "Output Quality" in content
        assert "Error Handling" in content

    def test_identity_uses_project_name(self) -> None:
        config = _make_identity_config()
        template = ScaffoldGenerator(config)._get_template()
        content = template.render_identity_identity()
        assert "test-agent" in content
        assert "A test agent" in content


# ---------------------------------------------------------------------------
# Framework-specific identity tools
# ---------------------------------------------------------------------------


class TestIdentityFrameworkSpecific:
    """Test render_identity_tools() differs per framework."""

    def test_langgraph_tools_mention_stategraph(self) -> None:
        config = _make_identity_config("langgraph")
        template = ScaffoldGenerator(config)._get_template()
        content = template.render_identity_tools()
        assert "StateGraph" in content
        assert "bind_tools" in content

    def test_strands_tools_mention_tool_decorator(self) -> None:
        config = _make_identity_config("strands")
        template = ScaffoldGenerator(config)._get_template()
        content = template.render_identity_tools()
        assert "@tool" in content
        assert "Strands" in content

    def test_pi_tools_mention_register_tool(self) -> None:
        config = _make_identity_config("pi")
        template = ScaffoldGenerator(config)._get_template()
        content = template.render_identity_tools()
        assert "register_tool" in content
        assert "TOOL_REGISTRY" in content

    def test_all_frameworks_produce_different_tools_content(self) -> None:
        contents = set()
        for fw in FRAMEWORKS:
            config = _make_identity_config(fw)
            template = ScaffoldGenerator(config)._get_template()
            contents.add(template.render_identity_tools())
        assert len(contents) == 3, "Each framework should produce unique TOOLS.md"


# ---------------------------------------------------------------------------
# Section 2 with identity
# ---------------------------------------------------------------------------


class TestSection2WithIdentity:
    """Test render_section_2_config() changes when identity is enabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_section_2_with_identity_uses_brief_packet(self, framework: str, tmp_path: Path) -> None:
        config = _make_identity_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert "from brief_packet import assemble_brief_packet" in agent_source

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_section_2_without_identity_uses_prompt_file(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert "prompt_file = PROMPT_DIR" in agent_source
        assert "assemble_brief_packet" not in agent_source

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_py_valid_python_with_identity(self, framework: str, tmp_path: Path) -> None:
        config = _make_identity_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        ast.parse(agent_source)


# ---------------------------------------------------------------------------
# Config YAML identity section
# ---------------------------------------------------------------------------


class TestConfigYamlIdentity:
    """Test config.yaml includes identity section when enabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_has_identity_when_enabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_identity_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert "identity:" in config_yaml
        assert "enabled: true" in config_yaml
        assert "personality_preset:" in config_yaml

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_no_identity_when_disabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert "identity:" not in config_yaml


# ---------------------------------------------------------------------------
# Generator identity file tree
# ---------------------------------------------------------------------------


class TestGeneratorIdentityFiles:
    """Test generate() creates identity/ dir with correct files."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_full_identity_file_tree(self, framework: str, tmp_path: Path) -> None:
        config = _make_identity_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        assert (output_path / "identity").is_dir()
        assert (output_path / "brief_packet.py").exists()
        assert (output_path / "prompts" / "system_prompt.md").exists()

    def test_subset_layers_only_creates_selected(self, tmp_path: Path) -> None:
        config = _make_identity_config(
            "langgraph", tmp_path, layers=["rules", "tools"]
        )
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        identity_dir = output_path / "identity"
        assert (identity_dir / "RULES.md").exists()
        assert (identity_dir / "TOOLS.md").exists()
        assert not (identity_dir / "PERSONALITY.md").exists()
        assert not (identity_dir / "DUTIES.md").exists()


# ---------------------------------------------------------------------------
# Wizard identity flow
# ---------------------------------------------------------------------------


class TestWizardIdentityFlow:
    """Test _ask_identity_layers with mocked questionary."""

    def test_identity_disabled(self) -> None:
        from cli.commands.scaffold import _ask_identity_layers

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = False
            result = _ask_identity_layers()
            assert result.enabled is False

    def test_identity_enabled_all_defaults(self) -> None:
        from cli.commands.scaffold import _ask_identity_layers

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = True
            mock_q.checkbox.return_value.ask.side_effect = [
                ["rules", "personality", "identity", "tools", "user", "memory", "bootstrap", "duties"],
                ["safety", "tool_governance", "output_quality"],
            ]
            mock_q.select.return_value.ask.return_value = "professional"
            result = _ask_identity_layers()
            assert result.enabled is True
            assert len(result.layers) == 8
            assert result.personality_preset == "professional"

    def test_identity_enabled_subset_layers(self) -> None:
        from cli.commands.scaffold import _ask_identity_layers

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = True
            mock_q.checkbox.return_value.ask.side_effect = [
                ["rules", "tools"],
                ["safety"],
            ]
            # No personality select since personality not in layers
            result = _ask_identity_layers()
            assert result.enabled is True
            assert result.layers == ["rules", "tools"]
            assert result.rules_focus == ["safety"]

    def test_identity_abort_on_none(self) -> None:
        from click.exceptions import Abort

        from cli.commands.scaffold import _ask_identity_layers

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = None
            with pytest.raises(Abort):
                _ask_identity_layers()


# ---------------------------------------------------------------------------
# Tool Governance Config (Principle 9)
# ---------------------------------------------------------------------------


class TestToolGovernanceConfig:
    """Test ToolGovernanceConfig dataclass."""

    def test_defaults(self) -> None:
        config = ToolGovernanceConfig()
        assert config.profile == "minimal"
        assert config.deny == []
        assert config.sub_agent_restrictions is True

    def test_custom_profile(self) -> None:
        config = ToolGovernanceConfig(profile="coding")
        assert config.profile == "coding"

    def test_custom_deny_list(self) -> None:
        config = ToolGovernanceConfig(deny=["shell_exec", "delete_file"])
        assert config.deny == ["shell_exec", "delete_file"]

    def test_scaffold_config_default_tool_governance(self) -> None:
        """ScaffoldConfig should have minimal tool governance by default."""
        config = _make_config()
        assert config.tool_governance.profile == "minimal"
        assert config.tool_governance.deny == []
        assert config.tool_governance.sub_agent_restrictions is True


# ---------------------------------------------------------------------------
# Tool Policy generation
# ---------------------------------------------------------------------------


class TestToolPolicyGeneration:
    """Test render_tool_policy_py() produces valid Python with required components."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tool_policy_is_valid_python(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        template = generator._get_template()
        source = template.render_tool_policy_py()
        ast.parse(source)

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tool_policy_has_tool_groups(self, framework: str) -> None:
        config = _make_config(framework)
        template = ScaffoldGenerator(config)._get_template()
        source = template.render_tool_policy_py()
        assert "TOOL_GROUPS" in source

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tool_policy_has_profiles(self, framework: str) -> None:
        config = _make_config(framework)
        template = ScaffoldGenerator(config)._get_template()
        source = template.render_tool_policy_py()
        assert "PROFILES" in source

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tool_policy_has_subagent_deny(self, framework: str) -> None:
        config = _make_config(framework)
        template = ScaffoldGenerator(config)._get_template()
        source = template.render_tool_policy_py()
        assert "DEFAULT_SUBAGENT_DENY" in source

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tool_policy_has_key_functions(self, framework: str) -> None:
        config = _make_config(framework)
        template = ScaffoldGenerator(config)._get_template()
        source = template.render_tool_policy_py()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        for expected in [
            "expand_groups", "matches_policy", "filter_tools",
            "validate_tool_config", "load_tool_policy",
        ]:
            assert expected in func_names, f"{expected} not found in tool_policy.py"


# ---------------------------------------------------------------------------
# Config YAML tool governance section
# ---------------------------------------------------------------------------


class TestConfigYamlToolGovernance:
    """Test config.yaml contains correct tool governance settings."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_has_profile(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert 'profile: "minimal"' in config_yaml

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_has_deny(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert "deny:" in config_yaml

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_has_sub_agent_restrictions(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert "sub_agent_restrictions:" in config_yaml

    def test_config_yaml_reflects_custom_profile(self, tmp_path: Path) -> None:
        config = _make_config(
            "langgraph", tmp_path,
            tool_governance=ToolGovernanceConfig(profile="coding"),
        )
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert 'profile: "coding"' in config_yaml

    def test_config_yaml_reflects_custom_deny(self, tmp_path: Path) -> None:
        config = _make_config(
            "langgraph", tmp_path,
            tool_governance=ToolGovernanceConfig(deny=["shell_exec"]),
        )
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert '["shell_exec"]' in config_yaml


# ---------------------------------------------------------------------------
# Tool Governance framework integration
# ---------------------------------------------------------------------------


class TestToolGovernanceFrameworkIntegration:
    """Test each framework's section 6 includes tool governance integration."""

    def test_strands_section_6_has_filter_tools(self) -> None:
        config = _make_config("strands")
        template = ScaffoldGenerator(config)._get_template()
        source = template.render_section_6_graph()
        assert "from tool_policy import filter_tools" in source

    def test_pi_section_6_has_filter_tools(self) -> None:
        config = _make_config("pi")
        template = ScaffoldGenerator(config)._get_template()
        source = template.render_section_6_graph()
        assert "from tool_policy import filter_tools" in source

    def test_langgraph_section_6_has_tool_policy_comment(self) -> None:
        config = _make_config("langgraph")
        template = ScaffoldGenerator(config)._get_template()
        source = template.render_section_6_graph()
        assert "tool_policy" in source


# ---------------------------------------------------------------------------
# Section 6 with tool governance (full agent.py validation)
# ---------------------------------------------------------------------------


class TestSection6WithToolGovernance:
    """Test each framework's section 6 output includes tool governance."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_py_valid_python_with_tool_governance(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        ast.parse(agent_source)

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_py_references_tool_policy(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert "tool_policy" in agent_source


# ---------------------------------------------------------------------------
# Generator tool_policy.py file
# ---------------------------------------------------------------------------


class TestGeneratorToolPolicyFile:
    """Test generate() creates tool_policy.py in output dir."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tool_policy_file_created(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        assert (output_path / "tool_policy.py").exists()

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tool_policy_file_is_valid_python(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "tool_policy.py").read_text()
        ast.parse(source)

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tool_policy_has_6_groups(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "tool_policy.py").read_text()
        for group in ["group:fs", "group:runtime", "group:web", "group:memory", "group:sessions", "group:messaging"]:
            assert group in source, f"Missing tool group: {group}"

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tool_policy_has_3_profiles(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "tool_policy.py").read_text()
        for profile in ["minimal", "coding", "full"]:
            assert f'"{profile}"' in source, f"Missing profile: {profile}"

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tool_policy_deny_wins_over_allow(self, framework: str, tmp_path: Path) -> None:
        """Verify matches_policy checks deny first (structural guarantee)."""
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "tool_policy.py").read_text()
        # The deny check must appear before the allow check in matches_policy
        deny_pos = source.index("if tool_name in deny_list")
        allow_pos = source.index("return tool_name in allow_list")
        assert deny_pos < allow_pos, "Deny must be checked before allow"


# ---------------------------------------------------------------------------
# Wizard tool governance flow
# ---------------------------------------------------------------------------


class TestWizardToolGovernanceFlow:
    """Test _ask_tool_governance with mocked questionary."""

    def test_tool_governance_defaults(self) -> None:
        from cli.commands.scaffold import _ask_tool_governance

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = "minimal"
            mock_q.confirm.return_value.ask.return_value = True
            result = _ask_tool_governance()
            assert result.profile == "minimal"
            assert result.sub_agent_restrictions is True

    def test_tool_governance_coding_profile(self) -> None:
        from cli.commands.scaffold import _ask_tool_governance

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = "coding"
            mock_q.confirm.return_value.ask.return_value = False
            result = _ask_tool_governance()
            assert result.profile == "coding"
            assert result.sub_agent_restrictions is False

    def test_tool_governance_abort_on_none(self) -> None:
        from click.exceptions import Abort

        from cli.commands.scaffold import _ask_tool_governance

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = None
            with pytest.raises(Abort):
                _ask_tool_governance()


# ---------------------------------------------------------------------------
# LangSmith Config (Principle 16)
# ---------------------------------------------------------------------------


class TestLangSmithConfig:
    """Test LangSmithConfig dataclass."""

    def test_defaults(self) -> None:
        config = LangSmithConfig()
        assert config.enabled is False
        assert config.project == ""

    def test_enabled_with_project(self) -> None:
        config = LangSmithConfig(enabled=True, project="my-project")
        assert config.enabled is True
        assert config.project == "my-project"

    def test_scaffold_config_default_langsmith(self) -> None:
        """ScaffoldConfig should have LangSmith disabled by default."""
        config = _make_config()
        assert config.langsmith.enabled is False
        assert config.langsmith.project == ""


# ---------------------------------------------------------------------------
# LangSmith .env.example
# ---------------------------------------------------------------------------


class TestLangSmithEnvExample:
    """Test .env.example includes LangSmith vars when enabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_env_has_langchain_vars_when_enabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_langsmith_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        env = (output_path / ".env.example").read_text()
        assert "LANGCHAIN_TRACING_V2" in env  # referenced in --dev flag comment
        assert "LANGCHAIN_API_KEY" in env
        assert "LANGCHAIN_PROJECT=test-project" in env

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_env_no_langchain_vars_when_disabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        env = (output_path / ".env.example").read_text()
        assert "LANGCHAIN_TRACING_V2" not in env
        assert "LANGCHAIN_API_KEY" not in env
        assert "LANGCHAIN_PROJECT" not in env


# ---------------------------------------------------------------------------
# LangSmith config.yaml
# ---------------------------------------------------------------------------


class TestLangSmithConfigYaml:
    """Test config.yaml includes tracing section when enabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_has_tracing_when_enabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_langsmith_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert "tracing:" in config_yaml
        assert 'provider: "langsmith"' in config_yaml
        assert 'project: "test-project"' in config_yaml

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_no_tracing_when_disabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert "tracing:" not in config_yaml


# ---------------------------------------------------------------------------
# LangSmith pyproject.toml
# ---------------------------------------------------------------------------


class TestLangSmithPyproject:
    """Test pyproject.toml includes langsmith dep when enabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_pyproject_has_langsmith_when_enabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_langsmith_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        pyproject = (output_path / "pyproject.toml").read_text()
        assert "langsmith" in pyproject

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_pyproject_no_langsmith_when_disabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        pyproject = (output_path / "pyproject.toml").read_text()
        assert "langsmith" not in pyproject


# ---------------------------------------------------------------------------
# LangSmith agent.py integration
# ---------------------------------------------------------------------------


class TestLangSmithAgentIntegration:
    """Test agent.py contains @traceable and langsmith import when enabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_has_traceable_when_enabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_langsmith_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert "@traceable" in agent_source
        assert "from langsmith import traceable" in agent_source

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_no_traceable_when_disabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert "@traceable" not in agent_source
        assert "from langsmith" not in agent_source

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_py_valid_python_with_langsmith(self, framework: str, tmp_path: Path) -> None:
        """Verify generated agent.py with LangSmith is syntactically valid Python."""
        config = _make_langsmith_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        ast.parse(agent_source)

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_readme_has_observability_when_enabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_langsmith_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        readme = (output_path / "README.md").read_text()
        assert "Observability" in readme
        assert "LangSmith" in readme
        assert "tracing.project" in readme

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_has_dev_flag_when_enabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_langsmith_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert '"--dev"' in agent_source
        assert "LANGCHAIN_TRACING_V2" in agent_source
        assert "[--dev]" in agent_source  # usage message

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_no_dev_flag_when_disabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert "--dev" not in agent_source
        assert "LANGCHAIN_TRACING_V2" not in agent_source

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_readme_no_observability_section_when_disabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        readme = (output_path / "README.md").read_text()
        assert "## Observability" not in readme
        assert "tracing.project" not in readme


# ---------------------------------------------------------------------------
# Wizard LangSmith flow
# ---------------------------------------------------------------------------


class TestWizardLangSmithFlow:
    """Test _ask_langsmith with mocked questionary."""

    def test_langsmith_enabled(self) -> None:
        from cli.commands.scaffold import _ask_langsmith

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = True
            mock_q.text.return_value.ask.return_value = "my-project"
            result = _ask_langsmith("my-project")
            assert result.enabled is True
            assert result.project == "my-project"

    def test_langsmith_disabled(self) -> None:
        from cli.commands.scaffold import _ask_langsmith

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = False
            result = _ask_langsmith("my-project")
            assert result.enabled is False

    def test_langsmith_abort_on_none_confirm(self) -> None:
        from click.exceptions import Abort

        from cli.commands.scaffold import _ask_langsmith

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = None
            with pytest.raises(Abort):
                _ask_langsmith("my-project")

    def test_langsmith_abort_on_none_project(self) -> None:
        from click.exceptions import Abort

        from cli.commands.scaffold import _ask_langsmith

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = True
            mock_q.text.return_value.ask.return_value = None
            with pytest.raises(Abort):
                _ask_langsmith("my-project")


# ---------------------------------------------------------------------------
# Session Config (Principle 11)
# ---------------------------------------------------------------------------


class TestSessionConfig:
    """Test SessionConfig dataclass."""

    def test_defaults(self) -> None:
        config = SessionConfig()
        assert config.enabled is False
        assert config.storage_dir == ".agent/sessions"
        assert config.prune_after_days == 30
        assert config.max_entries == 500
        assert config.rotate_bytes == 10_485_760
        assert config.history_limit == 50
        assert config.compaction_threshold == 50
        assert config.maintenance_mode == "warn"

    def test_enabled_with_custom_values(self) -> None:
        config = SessionConfig(
            enabled=True,
            maintenance_mode="enforce",
            history_limit=100,
        )
        assert config.enabled is True
        assert config.maintenance_mode == "enforce"
        assert config.history_limit == 100

    def test_scaffold_config_default_sessions(self) -> None:
        """ScaffoldConfig should have sessions disabled by default."""
        config = _make_config()
        assert config.sessions.enabled is False


# ---------------------------------------------------------------------------
# Sessions generation
# ---------------------------------------------------------------------------


class TestSessionsGeneration:
    """Test sessions.py is generated when enabled and valid Python."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_sessions_py_exists_when_enabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_session_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        assert (output_path / "sessions.py").exists()

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_sessions_py_is_valid_python(self, framework: str, tmp_path: Path) -> None:
        config = _make_session_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "sessions.py").read_text()
        ast.parse(source)

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_sessions_py_has_key_classes(self, framework: str, tmp_path: Path) -> None:
        config = _make_session_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "sessions.py").read_text()
        tree = ast.parse(source)
        class_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        for expected in [
            "MessageRole", "SessionStore", "RepairResult", "CompactionResult",
        ]:
            assert expected in class_names, f"{expected} class not found in sessions.py"

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_sessions_py_has_key_functions(self, framework: str, tmp_path: Path) -> None:
        config = _make_session_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "sessions.py").read_text()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        for expected in [
            "build_session_key", "append_message", "load_transcript",
            "session_write_lock", "sanitise_for_provider",
            "repair_session_file", "compact_session",
        ]:
            assert expected in func_names, f"{expected} function not found in sessions.py"


# ---------------------------------------------------------------------------
# Sessions NOT generated when disabled
# ---------------------------------------------------------------------------


class TestSessionsNotGeneratedWhenDisabled:
    """Test sessions.py is absent when sessions are disabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_sessions_py_absent_when_disabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        assert not (output_path / "sessions.py").exists()


# ---------------------------------------------------------------------------
# Sessions config.yaml
# ---------------------------------------------------------------------------


class TestSessionsConfigYaml:
    """Test config.yaml has/lacks sessions section."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_has_sessions_when_enabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_session_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert "sessions:" in config_yaml
        assert "enabled: true" in config_yaml
        assert "storage_dir:" in config_yaml
        assert "maintenance:" in config_yaml

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_no_sessions_when_disabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert "sessions:" not in config_yaml


# ---------------------------------------------------------------------------
# Sessions README
# ---------------------------------------------------------------------------


class TestSessionsReadme:
    """Test README has/lacks session persistence section."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_readme_has_sessions_when_enabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_session_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        readme = (output_path / "README.md").read_text()
        assert "Session Persistence" in readme
        assert "sessions.maintenance.mode" in readme

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_readme_no_sessions_when_disabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        readme = (output_path / "README.md").read_text()
        assert "## Session Persistence" not in readme
        assert "sessions.maintenance.mode" not in readme


# ---------------------------------------------------------------------------
# Section 8 with sessions
# ---------------------------------------------------------------------------


class TestSection8WithSessions:
    """Test agent.py contains session imports + wrapper when sessions enabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_has_session_imports_when_enabled(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_session_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert "from sessions import" in agent_source
        assert "run_agent_with_session" in agent_source
        assert "SessionStore" in agent_source

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_no_session_imports_when_disabled(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert "from sessions import" not in agent_source
        assert "run_agent_with_session" not in agent_source

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_py_valid_python_with_sessions(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_session_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        ast.parse(agent_source)

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_main_block_calls_session_wrapper(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_session_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        # The __main__ block should call run_agent_with_session
        assert "run_agent_with_session(user_query)" in agent_source


# ---------------------------------------------------------------------------
# Wizard session flow
# ---------------------------------------------------------------------------


class TestWizardSessionFlow:
    """Test _ask_session_persistence with mocked questionary."""

    def test_session_enabled(self) -> None:
        from cli.commands.scaffold import _ask_session_persistence

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = True
            mock_q.select.return_value.ask.return_value = "warn"
            result = _ask_session_persistence()
            assert result.enabled is True
            assert result.maintenance_mode == "warn"

    def test_session_disabled(self) -> None:
        from cli.commands.scaffold import _ask_session_persistence

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = False
            result = _ask_session_persistence()
            assert result.enabled is False

    def test_session_abort_on_none(self) -> None:
        from click.exceptions import Abort

        from cli.commands.scaffold import _ask_session_persistence

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = None
            with pytest.raises(Abort):
                _ask_session_persistence()


# ---------------------------------------------------------------------------
# Skills Config (Principle 7)
# ---------------------------------------------------------------------------


class TestSkillsConfig:
    """Test SkillsConfig dataclass."""

    def test_defaults(self) -> None:
        config = SkillsConfig()
        assert config.enabled is False
        assert config.skills_dir == "skills"
        assert config.max_description_chars == 150
        assert config.read_tool_name == "read_file"

    def test_enabled(self) -> None:
        config = SkillsConfig(enabled=True)
        assert config.enabled is True

    def test_scaffold_config_default_skills(self) -> None:
        """ScaffoldConfig should have skills disabled by default."""
        config = _make_config()
        assert config.skills.enabled is False


# ---------------------------------------------------------------------------
# Capabilities generation
# ---------------------------------------------------------------------------


class TestCapabilitiesGeneration:
    """Test capabilities.py is generated when enabled and valid Python."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_capabilities_py_exists_when_enabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_skills_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        assert (output_path / "capabilities.py").exists()

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_capabilities_py_is_valid_python(self, framework: str, tmp_path: Path) -> None:
        config = _make_skills_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "capabilities.py").read_text()
        ast.parse(source)

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_capabilities_py_has_key_classes(self, framework: str, tmp_path: Path) -> None:
        config = _make_skills_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "capabilities.py").read_text()
        tree = ast.parse(source)
        class_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        for expected in [
            "SkillSource", "SkillRequirements", "SkillMetadata",
            "SkillSnapshot", "SnapshotCache",
        ]:
            assert expected in class_names, f"{expected} class not found in capabilities.py"

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_capabilities_py_has_key_functions(self, framework: str, tmp_path: Path) -> None:
        config = _make_skills_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "capabilities.py").read_text()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        for expected in [
            "parse_skill_file", "extract_description",
            "scan_skill_directory", "discover_all_skills",
            "filter_eligible_skills", "build_snapshot",
            "format_skills_for_prompt", "build_skills_system_prompt_section",
            "load_full_instructions", "load_resource",
        ]:
            assert expected in func_names, f"{expected} function not found in capabilities.py"


# ---------------------------------------------------------------------------
# Skills NOT generated when disabled
# ---------------------------------------------------------------------------


class TestSkillsNotGeneratedWhenDisabled:
    """Test capabilities.py and skills/ are absent when skills are disabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_capabilities_py_absent_when_disabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        assert not (output_path / "capabilities.py").exists()

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_skills_dir_absent_when_disabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        assert not (output_path / "skills").exists()


# ---------------------------------------------------------------------------
# Skills directory
# ---------------------------------------------------------------------------


class TestSkillsDirectory:
    """Test skills/example-skill/SKILL.md is generated correctly."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_example_skill_exists(self, framework: str, tmp_path: Path) -> None:
        config = _make_skills_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        skill_file = output_path / "skills" / "example-skill" / "SKILL.md"
        assert skill_file.exists()

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_example_skill_has_frontmatter(self, framework: str, tmp_path: Path) -> None:
        config = _make_skills_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        skill_content = (output_path / "skills" / "example-skill" / "SKILL.md").read_text()
        assert skill_content.startswith("---")
        assert "description:" in skill_content
        assert "metadata:" in skill_content


# ---------------------------------------------------------------------------
# Skills config.yaml
# ---------------------------------------------------------------------------


class TestSkillsConfigYaml:
    """Test config.yaml has/lacks skills section."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_has_skills_when_enabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_skills_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert "skills:" in config_yaml
        assert "enabled: true" in config_yaml
        assert "skills_dir:" in config_yaml
        assert "max_description_chars:" in config_yaml

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_no_skills_when_disabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert "skills:" not in config_yaml


# ---------------------------------------------------------------------------
# Skills README
# ---------------------------------------------------------------------------


class TestSkillsReadme:
    """Test README has/lacks skills section."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_readme_has_skills_when_enabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_skills_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        readme = (output_path / "README.md").read_text()
        assert "Progressive Capability Disclosure" in readme
        assert "skills.skills_dir" in readme

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_readme_no_skills_when_disabled(self, framework: str, tmp_path: Path) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        readme = (output_path / "README.md").read_text()
        assert "## Progressive Capability Disclosure" not in readme
        assert "skills.skills_dir" not in readme


# ---------------------------------------------------------------------------
# Section 2 with skills
# ---------------------------------------------------------------------------


class TestSection2WithSkills:
    """Test render_section_2_config() changes when skills are enabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_section_2_with_skills_has_capabilities_import(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_skills_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert "from capabilities import" in agent_source

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_section_2_without_skills_no_capabilities_import(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert "from capabilities import" not in agent_source

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_py_valid_python_with_skills(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_skills_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        ast.parse(agent_source)


# ---------------------------------------------------------------------------
# Section 2 with skills AND identity
# ---------------------------------------------------------------------------


class TestSection2WithSkillsAndIdentity:
    """Test agent.py is valid with both skills and identity enabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_py_valid_python_with_both(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(
            framework, tmp_path,
            identity=IdentityLayerConfig(enabled=True),
            skills=SkillsConfig(enabled=True),
        )
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        ast.parse(agent_source)

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_py_has_both_imports(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(
            framework, tmp_path,
            identity=IdentityLayerConfig(enabled=True),
            skills=SkillsConfig(enabled=True),
        )
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert "from brief_packet import" in agent_source
        assert "from capabilities import" in agent_source


# ---------------------------------------------------------------------------
# Observability helpers
# ---------------------------------------------------------------------------


def _make_observability_config(
    framework: str = "langgraph",
    tmp_path: Path | None = None,
) -> ScaffoldConfig:
    """Create a config with observability enabled."""
    return _make_config(
        framework=framework,
        tmp_path=tmp_path,
        observability=ObservabilityConfig(enabled=True),
    )


# ---------------------------------------------------------------------------
# ObservabilityConfig dataclass
# ---------------------------------------------------------------------------


class TestObservabilityConfig:
    """Test ObservabilityConfig dataclass."""

    def test_defaults(self) -> None:
        config = ObservabilityConfig()
        assert config.enabled is False
        assert config.log_dir == ".agent/logs"
        assert config.transcript_dir == ".agent/transcripts"
        assert config.log_level == "INFO"
        assert config.cloudwatch_log_group == ""
        assert config.cloudwatch_region == ""
        assert config.enable_transcripts is True
        assert config.enable_cost_tracking is True
        assert config.enable_config_audit is True
        assert config.enable_prompt_log is True
        assert config.enable_diagnostics is True

    def test_enabled(self) -> None:
        config = ObservabilityConfig(enabled=True, log_level="DEBUG")
        assert config.enabled is True
        assert config.log_level == "DEBUG"

    def test_scaffold_config_default_observability(self) -> None:
        """ScaffoldConfig should have observability disabled by default."""
        config = _make_config()
        assert config.observability.enabled is False


# ---------------------------------------------------------------------------
# Observability generation
# ---------------------------------------------------------------------------


class TestObservabilityGeneration:
    """Test observability.py is generated when enabled and valid Python."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_observability_py_exists_when_enabled(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_observability_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        assert (output_path / "observability.py").exists()

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_observability_py_is_valid_python(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_observability_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "observability.py").read_text()
        ast.parse(source)

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_observability_py_has_key_classes(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_observability_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "observability.py").read_text()
        tree = ast.parse(source)
        class_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        for expected in [
            "TokenUsage", "CostBreakdown", "ModelCostConfig",
            "SessionTranscript", "PromptLog", "ConfigAuditLog",
            "ObservabilityContext",
        ]:
            assert expected in class_names, (
                f"{expected} class not found in observability.py"
            )

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_observability_py_has_key_functions(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_observability_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        source = (output_path / "observability.py").read_text()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        for expected in [
            "setup_logging", "get_logger", "setup_observability",
            "calculate_cost", "hash_content", "subscribe", "emit",
        ]:
            assert expected in func_names, (
                f"{expected} function not found in observability.py"
            )


# ---------------------------------------------------------------------------
# Observability NOT generated when disabled
# ---------------------------------------------------------------------------


class TestObservabilityNotGeneratedWhenDisabled:
    """Test observability.py is absent when observability is disabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_observability_py_absent_when_disabled(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        assert not (output_path / "observability.py").exists()


# ---------------------------------------------------------------------------
# Observability config.yaml
# ---------------------------------------------------------------------------


class TestObservabilityConfigYaml:
    """Test config.yaml has/lacks observability section."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_has_observability_when_enabled(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_observability_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert "observability:" in config_yaml
        assert "enabled: true" in config_yaml
        assert "log_dir:" in config_yaml
        assert "transcript_dir:" in config_yaml
        assert "enable_transcripts:" in config_yaml

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_no_observability_when_disabled(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        config_yaml = (output_path / "config.yaml").read_text()
        assert "observability:" not in config_yaml


# ---------------------------------------------------------------------------
# Observability README
# ---------------------------------------------------------------------------


class TestObservabilityReadme:
    """Test README has/lacks observability section."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_readme_has_observability_when_enabled(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_observability_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        readme = (output_path / "README.md").read_text()
        assert "Operational Observability" in readme
        assert "observability.log_level" in readme

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_readme_no_observability_when_disabled(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        readme = (output_path / "README.md").read_text()
        assert "Operational Observability" not in readme
        assert "observability.log_level" not in readme


# ---------------------------------------------------------------------------
# Section 7 with observability
# ---------------------------------------------------------------------------


class TestSection7WithObservability:
    """Test agent.py section 7 integrates observability when enabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_py_has_observability_imports(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_observability_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert "from observability import" in agent_source
        assert "setup_observability" in agent_source
        assert "get_logger" in agent_source

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_py_valid_python_with_observability(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_observability_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        ast.parse(agent_source)

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_py_no_observability_imports_when_disabled(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        assert "from observability import" not in agent_source


# ---------------------------------------------------------------------------
# Observability .env.example
# ---------------------------------------------------------------------------


class TestObservabilityEnv:
    """Test .env.example has/lacks CloudWatch vars."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_env_has_cloudwatch_when_enabled(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_observability_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        env = (output_path / ".env.example").read_text()
        assert "CLOUDWATCH_LOG_GROUP" in env
        assert "CLOUDWATCH_REGION" in env

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_env_no_cloudwatch_when_disabled(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(framework, tmp_path)
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        env = (output_path / ".env.example").read_text()
        assert "CLOUDWATCH_LOG_GROUP" not in env
        assert "CLOUDWATCH_REGION" not in env


# ---------------------------------------------------------------------------
# Wizard observability flow
# ---------------------------------------------------------------------------


class TestWizardObservabilityFlow:
    """Test the wizard _ask_observability() function."""

    def test_observability_enabled(self) -> None:
        from cli.commands.scaffold import _ask_observability

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = True
            result = _ask_observability()
            assert result.enabled is True

    def test_observability_disabled(self) -> None:
        from cli.commands.scaffold import _ask_observability

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = False
            result = _ask_observability()
            assert result.enabled is False

    def test_observability_abort(self) -> None:
        from cli.commands.scaffold import _ask_observability

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = None
            with pytest.raises(typer.Abort):
                _ask_observability()


# ---------------------------------------------------------------------------
# Observability + LangSmith combined
# ---------------------------------------------------------------------------


class TestObservabilityWithLangSmith:
    """Test observability.py and LangSmith tracing work together."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_py_valid_with_both(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(
            framework, tmp_path,
            langsmith=LangSmithConfig(enabled=True, project="test"),
            observability=ObservabilityConfig(enabled=True),
        )
        generator = ScaffoldGenerator(config)
        output_path = generator.generate()

        agent_source = (output_path / "agent.py").read_text()
        ast.parse(agent_source)
        assert "from observability import" in agent_source


# ---------------------------------------------------------------------------
# ToolsConfig tests
# ---------------------------------------------------------------------------


class TestToolsConfig:
    """Test ToolsConfig dataclass."""

    def test_defaults(self) -> None:
        tc = ToolsConfig()
        assert tc.enabled is False
        assert tc.tools_dir == "tools"

    def test_enabled(self) -> None:
        tc = ToolsConfig(enabled=True)
        assert tc.enabled is True

    def test_scaffold_config_default(self) -> None:
        config = _make_config()
        assert config.tools.enabled is False


# ---------------------------------------------------------------------------
# Tools generation tests
# ---------------------------------------------------------------------------


class TestToolsGeneration:
    """Test that tools/ directory is generated correctly when enabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tools_init_exists(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_tools_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        assert (output_path / "tools" / "__init__.py").exists()

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tools_example_exists(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_tools_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        assert (output_path / "tools" / "example_tool.py").exists()

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tools_init_valid_python(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_tools_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        source = (output_path / "tools" / "__init__.py").read_text()
        ast.parse(source)

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tools_example_valid_python(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_tools_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        source = (output_path / "tools" / "example_tool.py").read_text()
        ast.parse(source)

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tools_init_has_key_classes(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_tools_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        source = (output_path / "tools" / "__init__.py").read_text()
        tree = ast.parse(source)
        class_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        for expected in ["AgentTool", "ToolParameter", "ToolMetadata", "ToolDefinition", "ToolRegistry"]:
            assert expected in class_names, f"{expected} not found"

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tools_init_has_key_functions(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_tools_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        source = (output_path / "tools" / "__init__.py").read_text()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        for expected in ["discover_tools", "get_permitted_tools"]:
            assert expected in func_names, f"{expected} not found"

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_example_tool_is_agent_tool(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_tools_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        source = (output_path / "tools" / "example_tool.py").read_text()
        assert "class ExampleTool" in source
        assert "AgentTool" in source
        assert "resources" in source

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tools_init_has_agent_tool_abc(
        self, framework: str, tmp_path: Path,
    ) -> None:
        """Verify AgentTool is an ABC with abstract execute method."""
        config = _make_tools_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        source = (output_path / "tools" / "__init__.py").read_text()
        assert "class AgentTool(ABC):" in source
        assert "def execute(self" in source
        assert "@abstractmethod" in source
        assert "def as_function(self" in source


class TestToolsNotGeneratedWhenDisabled:
    """Test that tools/ directory is NOT generated when disabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tools_dir_absent(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        assert not (output_path / "tools").exists()


# ---------------------------------------------------------------------------
# Tools config.yaml tests
# ---------------------------------------------------------------------------


class TestToolsConfigYaml:
    """Test config.yaml tools section."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_has_tools_section(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_tools_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        config_yaml = (output_path / "config.yaml").read_text()
        assert "tool_functions:" in config_yaml

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_config_yaml_no_tools_section_when_disabled(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        config_yaml = (output_path / "config.yaml").read_text()
        assert "tool_functions:" not in config_yaml


# ---------------------------------------------------------------------------
# Tools README tests
# ---------------------------------------------------------------------------


class TestToolsReadme:
    """Test README.md tools section."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_readme_has_tools_section(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_tools_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        readme = (output_path / "README.md").read_text()
        assert "tools/" in readme
        assert "Unified Tool Interface" in readme

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_readme_no_tools_section_when_disabled(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        readme = (output_path / "README.md").read_text()
        assert "Uniform Tool Format" not in readme


# ---------------------------------------------------------------------------
# Section 5/6 with tools tests
# ---------------------------------------------------------------------------


class TestSection5WithTools:
    """Test section 5 has tools imports when enabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_section_5_has_tools_import(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_tools_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        agent_source = (output_path / "agent.py").read_text()
        assert "from tools import get_permitted_tools" in agent_source

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_section_5_no_tools_import_when_disabled(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        agent_source = (output_path / "agent.py").read_text()
        assert "from tools import" not in agent_source


class TestSection6WithTools:
    """Test section 6 has active tool governance when enabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_section_6_valid_python(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_tools_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        agent_source = (output_path / "agent.py").read_text()
        ast.parse(agent_source)


class TestToolsFailover:
    """Test section 6 contains inference-only fallback when tools enabled."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_inference_only_fallback_present(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_tools_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        agent_source = (output_path / "agent.py").read_text()
        assert "inference-only mode" in agent_source


# ---------------------------------------------------------------------------
# Tools + Observability combined
# ---------------------------------------------------------------------------


class TestToolsWithObservability:
    """Test tools and observability work together."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_py_valid_with_both(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(
            framework, tmp_path,
            tools=ToolsConfig(enabled=True),
            observability=ObservabilityConfig(enabled=True),
        )
        output_path = ScaffoldGenerator(config).generate()
        agent_source = (output_path / "agent.py").read_text()
        ast.parse(agent_source)
        tools_init = (output_path / "tools" / "__init__.py").read_text()
        ast.parse(tools_init)
        assert "from observability import get_logger" in tools_init

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_tools_init_uses_stdlib_logging_without_observability(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_tools_config(framework, tmp_path)
        output_path = ScaffoldGenerator(config).generate()
        tools_init = (output_path / "tools" / "__init__.py").read_text()
        assert "import logging" in tools_init
        assert "from observability" not in tools_init


# ---------------------------------------------------------------------------
# Tools + Skills combined
# ---------------------------------------------------------------------------


class TestToolsWithSkills:
    """Test tools and skills work together (complementary, not conflicting)."""

    @pytest.mark.parametrize("framework", FRAMEWORKS)
    def test_agent_py_valid_with_both(
        self, framework: str, tmp_path: Path,
    ) -> None:
        config = _make_config(
            framework, tmp_path,
            tools=ToolsConfig(enabled=True),
            skills=SkillsConfig(enabled=True),
        )
        output_path = ScaffoldGenerator(config).generate()
        agent_source = (output_path / "agent.py").read_text()
        ast.parse(agent_source)
        assert (output_path / "tools" / "__init__.py").exists()
        assert (output_path / "capabilities.py").exists()


# ---------------------------------------------------------------------------
# Wizard tools flow tests
# ---------------------------------------------------------------------------


class TestWizardToolsFlow:
    """Test _ask_tools wizard step."""

    def test_ask_tools_enabled(self) -> None:
        from cli.commands.scaffold import _ask_tools

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = True
            result = _ask_tools()
            assert result.enabled is True

    def test_ask_tools_disabled(self) -> None:
        from cli.commands.scaffold import _ask_tools

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = False
            result = _ask_tools()
            assert result.enabled is False

    def test_ask_tools_abort(self) -> None:
        from cli.commands.scaffold import _ask_tools

        with patch("cli.commands.scaffold.questionary") as mock_q:
            mock_q.confirm.return_value.ask.return_value = None
            with pytest.raises(typer.Abort):
                _ask_tools()

