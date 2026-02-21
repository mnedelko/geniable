"""Tests for the scaffold generator."""

import ast
from pathlib import Path
from unittest.mock import patch

import pytest

from cli.scaffold import IdentityLayerConfig, ProviderModel, ScaffoldConfig, ScaffoldGenerator

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
    identity: IdentityLayerConfig | None = None,
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
