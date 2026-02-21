# Model Resilience — Fallback Cascades & Auth Rotation

**Principle 5** of the agent engineering framework. Implemented in v2.3.0 of the `geni new` scaffold generator.

---

## Overview

When the scaffold generator (`geni new create`) creates an agent project, it now produces a `resilience.py` module alongside `agent.py`. This module implements a two-nested-loop failover strategy:

- **Outer loop** — iterates through model candidates (primary, then fallbacks)
- **Inner loop** — rotates through credential profiles within a single provider

The goal is to keep the agent available when a provider returns auth errors, rate limits, billing blocks, or timeouts — without requiring manual intervention.

---

## Architecture

```
                        ┌──────────────────────────────┐
                        │     ModelFallbackRunner       │
                        │         (outer loop)          │
                        └──────────────┬───────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                        ▼
    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
    │  Primary Model   │     │  Fallback #1     │     │  Fallback #2     │
    │  bedrock/claude  │     │  openai/gpt-4o   │     │  ollama/llama3   │
    └────────┬────────┘     └────────┬────────┘     └────────┬────────┘
             │                       │                       │
             ▼                       ▼                       ▼
    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
    │ CredentialRotator│     │ CredentialRotator│     │ CredentialRotator│
    │  (inner loop)    │     │  (inner loop)    │     │  (inner loop)    │
    │                  │     │                  │     │                  │
    │ profile A ──→    │     │ profile C ──→    │     │ profile E ──→    │
    │ profile B ──→    │     │ profile D ──→    │     │                  │
    └─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Execution Flow

1. `ModelFallbackRunner.run(invoke_fn)` is called
2. For the **primary** candidate, `CredentialRotator.next_profile()` selects the least-recently-used available profile
3. `invoke_fn(provider, model_id, profile)` is called
4. **On success**: reset health counters, return result
5. **On failure**: `classify_error()` determines if the error is failover-eligible
   - If not failover-eligible (e.g. a bug in the prompt) — the error propagates immediately
   - If failover-eligible — `CooldownEngine.apply_cooldown()` is called on the profile, then the inner loop tries the next profile
6. When all profiles for a candidate are exhausted, the outer loop moves to the next fallback candidate
7. If all candidates are exhausted, a `FailoverError` is raised

---

## Components

### 1. Error Classifier (`classify_error`)

Maps exceptions to `FailoverReason` enum values. Two detection strategies:

**HTTP status code extraction** — looks for `status_code`, `status`, `code`, or `http_status` attributes on the exception:

| Status Code | Reason |
|-------------|--------|
| 401, 403 | `AUTH` |
| 429 | `RATE_LIMIT` |
| 402 | `BILLING` |
| 408, 504 | `TIMEOUT` |

**Error message pattern matching** — scans the lowercased error string:

| Patterns | Reason |
|----------|--------|
| "invalid api key", "unauthorized", "forbidden" | `AUTH` |
| "rate limit", "too many requests", "throttl" | `RATE_LIMIT` |
| "billing", "payment", "quota exceeded" | `BILLING` |
| "timeout", "timed out", "deadline exceeded" | `TIMEOUT` |
| "invalid request", "malformed", "bad request" | `FORMAT` |

Returns `None` for non-failover errors, which causes the runner to propagate the original exception without triggering fallback.

### 2. Cooldown Engine (`CooldownEngine`)

Manages tiered cooldown escalation per profile. Consecutive failures increase cooldown duration:

**Transient errors** (rate limit, timeout, auth, format):

| Tier | Cooldown |
|------|----------|
| 1st failure | 60s (1 min) |
| 2nd failure | 300s (5 min) |
| 3rd failure | 1,500s (25 min) |
| 4th+ failure | 3,600s (1 hr) |

**Billing errors** (longer cooldowns since billing issues don't resolve quickly):

| Tier | Cooldown |
|------|----------|
| 1st failure | 18,000s (5 hr) |
| 2nd failure | 36,000s (10 hr) |
| 3rd failure | 72,000s (20 hr) |
| 4th+ failure | 86,400s (24 hr) |

These tiers are configurable in `config.yaml`:

```yaml
resilience:
  auth:
    cooldowns:
      transient_tiers: [60, 300, 1500, 3600]
      billing_tiers: [18000, 36000, 72000, 86400]
```

`is_available(record)` returns `False` if the current time is before either `cooldown_until` or `billing_disabled_until`.

### 3. Credential Rotator (`CredentialRotator`)

The inner loop. Selects the next available credential profile for a given provider.

**Selection strategy**:
1. If a `pinned_id` is provided and that profile is available, use it
2. Otherwise, sort all profiles by `last_used` ascending (oldest first)
3. Filter to only profiles where `CooldownEngine.is_available()` is `True`
4. Return the first available profile

If no profiles are available, raises `FailoverError` to trigger the outer loop.

### 4. Model Fallback Runner (`ModelFallbackRunner`)

The outer loop. Orchestrates the full cascade:

```
primary candidate
  └─ try profile rotation (inner loop)
      └─ on success → return result
      └─ on failover error → cooldown profile, try next profile
          └─ all profiles exhausted → move to next candidate
fallback candidate #1
  └─ (same inner loop)
fallback candidate #2
  └─ (same inner loop)
...
all exhausted → raise FailoverError
```

Accepts an `invoke_fn(provider: str, model_id: str, profile: ProfileHealthRecord) -> Any` callback. Each framework template provides its own implementation of this callback.

### 5. Health Store (`HealthStore`)

File-based persistence for `ProfileHealthRecord` objects. Location: `{project_dir}/.agent/health.json`.

Features:
- JSON serialization of health records
- `fcntl.flock()` file locking for concurrency safety (Unix)
- `load()`, `save()`, `update_record()`, `reset_record()` methods

**Current status**: The generated agent code loads existing records at startup but does not persist mutations back to disk. Health state is in-memory only for the process lifetime. The write API is available for users who want to add persistence.

### 6. Data Models

```python
class FailoverReason(enum.Enum):
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    BILLING = "billing"
    TIMEOUT = "timeout"
    FORMAT = "format"
    UNKNOWN = "unknown"

class FailoverError(Exception):
    reason: FailoverReason
    provider: str

@dataclass
class ProfileHealthRecord:
    profile_id: str
    consecutive_errors: int
    last_error_time: float
    cooldown_until: float
    billing_disabled_until: float
    last_used: float

@dataclass
class ModelCandidate:
    provider: str
    model_id: str
    profiles: list[ProfileHealthRecord]
```

---

## How It's Wired Into Generated Projects

### Wizard Flow

The `geni new create` wizard collects provider/model information:

1. **Primary provider** — Bedrock, OpenAI, Google, or Ollama
2. **Primary model** — provider-specific model list
3. **API key** — prompted for OpenAI and Google (skipped for Bedrock/Ollama)
4. **Fallback loop** — "Add a fallback model?" repeats steps 1-3

### Generated Files

| File | Resilience Content |
|------|-------------------|
| `resilience.py` | Full module — all classes and functions described above |
| `agent.py` Section 2 | `Config` dataclass with `provider`, `fallbacks`, `cooldown_config` fields |
| `agent.py` Section 3 | Framework-specific client creation with `ModelFallbackRunner` wiring (when fallbacks configured) |
| `config.yaml` | `resilience` section with primary model, fallbacks, auth profiles, cooldown tiers |
| `.env.example` | Provider-specific env vars (only for selected providers) |
| `pyproject.toml` | Provider-specific dependencies (only for selected providers) |

### Framework Integration

Each framework template (LangGraph, Strands, Pi) generates a different Section 3, but all follow the same pattern:

**Without fallbacks** — a `_create_*_for_provider()` function that supports multi-provider client creation, but no `ModelFallbackRunner`. Simple lazy-init singleton.

**With fallbacks** — imports from `resilience`, builds `ModelCandidate` objects from config, wires through `ModelFallbackRunner.run()`:

```python
# Simplified pattern (LangGraph example)
from resilience import (
    CooldownEngine, ModelCandidate, ModelFallbackRunner,
    ProfileHealthRecord, HealthStore,
)

def _build_fallback_runner() -> ModelFallbackRunner:
    # Build primary + fallback ModelCandidates from Config
    # Each candidate gets a ProfileHealthRecord
    ...

def get_llm():
    runner = _build_fallback_runner()
    def invoke_fn(provider, model_id, profile):
        return _create_llm_for_provider(provider, model_id)
    return runner.run(invoke_fn)
```

The `invoke_fn` callback is framework-specific:
- **LangGraph**: returns a `ChatBedrockConverse` / `ChatOpenAI` / `ChatGoogleGenerativeAI` / `ChatOllama` instance
- **Strands**: returns a `BedrockModel` / `OpenAIModel` / `OllamaModel` instance
- **Pi**: directly invokes the model and returns the response text

---

## Provider/Model Matrix

| Provider | Models | Auth Method | Env Var |
|----------|--------|-------------|---------|
| Bedrock | Claude Sonnet 4, Haiku 4.5, Opus 4 | AWS profile/creds | `AWS_PROFILE` |
| OpenAI | gpt-4o, gpt-4o-mini, o3-mini | API key | `OPENAI_API_KEY` |
| Google | Gemini 2.0 Flash, Gemini 2.5 Pro | API key | `GOOGLE_API_KEY` |
| Ollama | Llama 3.2, Mistral, DeepSeek R1 | None (local) | `OLLAMA_BASE_URL` |

---

## Config Example

A generated `config.yaml` with Bedrock primary + OpenAI and Ollama fallbacks:

```yaml
agent:
  name: "my-agent"
  description: "A production AI agent"
  framework: "langgraph"

resilience:
  model:
    primary:
      provider: "bedrock"
      model_id: "anthropic.claude-sonnet-4-20250514-v1:0"
      region: "us-east-1"
    fallbacks:
      - provider: "openai"
        model_id: "gpt-4o"
      - provider: "ollama"
        model_id: "llama3.2"

  auth:
    profiles:
      bedrock:
        type: "aws"
      openai:
        type: "api_key"
        env_var: "OPENAI_API_KEY"
      ollama:
        type: "none"
        base_url: "http://localhost:11434"

    cooldowns:
      transient_tiers: [60, 300, 1500, 3600]
      billing_tiers: [18000, 36000, 72000, 86400]

operational:
  max_iterations: 10
  timeout_seconds: 120
  log_level: "INFO"
```

---

## Implementation Details

### Source Location

The resilience module is **not** a runtime dependency of the geniable CLI. It is a generated file — its source lives as a string literal in `geniable/cli/scaffold/base.py:render_resilience_py()`. When a user runs `geni new create`, this method produces the `resilience.py` file in their new project directory.

### Files Modified in This Implementation

| File | Change |
|------|--------|
| `geniable/cli/scaffold/__init__.py` | `ProviderModel` dataclass, updated `ScaffoldConfig`, `resilience.py` in file tree |
| `geniable/cli/scaffold/base.py` | `render_resilience_py()`, updated `render_config_yaml()`, `render_env_example()`, `render_section_2_config()`, `render_pyproject_toml()` |
| `geniable/cli/scaffold/langgraph.py` | Updated `render_section_3_client()` |
| `geniable/cli/scaffold/strands.py` | Updated `render_section_3_client()` |
| `geniable/cli/scaffold/pi.py` | Updated `render_section_3_client()` |
| `geniable/cli/commands/scaffold.py` | Multi-provider wizard flow |
| `geniable/tests/cli/test_scaffold.py` | 90 tests covering all resilience features |

### Backward Compatibility

- `ScaffoldConfig.model_id` property preserved — returns `primary_model.model_id`
- Single-provider configs (no fallbacks) generate simplified Section 3 without `ModelFallbackRunner`
- The `resilience.py` file is always generated regardless of fallback configuration

### Known Limitations

1. **Health state is in-memory only** — `HealthStore` has full read/write API but the generated agent code does not call `save()`. Cooldowns and error counts reset on process restart.
2. **Single profile per provider** — the generated code creates one `ProfileHealthRecord` per provider (`"bedrock/default"`). The rotator supports multiple profiles, but the wizard does not collect multiple credentials per provider.
3. **`fcntl.flock()` is Unix-only** — the `HealthStore` uses POSIX file locking. On Windows, `msvcrt` would be needed instead.

---

## Test Coverage

90 tests in `tests/cli/test_scaffold.py` covering:

- `TestProviderModel` — dataclass creation, defaults, all providers
- `TestScaffoldConfig` — validation, backward compat, `all_providers`, fallback defaults
- `TestScaffoldGenerator` — file tree, valid Python (with and without fallbacks), sections, classes, principles
- `TestResilienceGeneration` — valid Python, key classes (`FailoverError`, `CooldownEngine`, `CredentialRotator`, `ModelFallbackRunner`, `HealthStore`), key functions (`classify_error`, `load_resilience_config`)
- `TestConfigYamlResilience` — resilience section, fallbacks, cooldowns
- `TestEnvExample` — provider-specific env vars (bedrock-only, multi-provider, google)
- `TestPyprojectProviderDeps` — conditional dependencies per provider
- `TestSection3Resilience` — resilience imports present with fallbacks, absent without
- `TestSection2Config` — provider field, fallbacks/cooldown in config
- `TestWizardFlow` — provider selection, API key prompting, abort handling
