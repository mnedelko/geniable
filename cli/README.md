# Geniable CLI

**The command-line interface for Geniable — scaffold production-ready AI agents and run evaluation-driven QA pipelines from your terminal.**

The Geniable CLI is the local interface for the entire Geniable platform. It provides:

- **`geni new`** — Generate production-ready agent projects grounded in 20 architectural principles. Choose your framework (LangGraph, Strands, Pi), model provider (Bedrock, OpenAI, Google, Ollama), and get a fully wired project with identity layers, tool governance, observability, model resilience, and graceful degradation built in.

- **QA Pipeline** — An out-of-the-box evaluation loop that connects to your LangSmith annotation queue, runs cloud-hosted evaluations against conversation threads, detects issues, and creates tickets in Jira or Notion automatically.

- **Claude Code Integration** — Install AI agents and slash commands into your project for interactive analysis and issue resolution.

[![PyPI](https://img.shields.io/pypi/v/geniable)](https://pypi.org/project/geniable/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](../LICENSE)

<p align="center">
  <img src="../assets/logo.png" alt="Geniable Logo" width="200">
</p>

---

## Features

### Agent Project Scaffolding (`geni new`)

- **Multi-framework support** — LangGraph (StateGraph + LangChain), Strands Agents (`@tool` decorators), and Pi (declarative config with gateway pattern)
- **Multi-provider models** — AWS Bedrock (Claude), OpenAI (GPT-4o), Google (Gemini), Ollama (local)
- **20-principle architecture** — Each scaffold embeds production patterns: identity layers, tool governance, observability, model resilience, session persistence, graceful degradation, and more
- **Identity layer system** — Configurable layers for rules, personality, public identity, tool guidance, user context, persistent memory, bootstrap, and scheduled duties
- **LangSmith tracing** — Optional built-in tracing instrumentation with `--dev` flag
- **Complete project output** — `pyproject.toml`, `README.md`, `Makefile`, `.env.example`, `config.yaml`, `system_prompt.md`, `test_agent.py`

### QA Pipeline (Evaluation-Driven Development)

- **Thread Analysis** — Fetch and analyze threads from your LangSmith annotation queue
- **Automated Evaluations** — Run cloud-hosted MCP evaluators (latency, content quality, error detection, token usage)
- **Issue Detection** — Identify performance, quality, security, and UX issues with structured IssueCards
- **Ticket Creation** — Create standardized tickets in Jira or Notion with affected code and recommendations
- **State Tracking** — Avoids reprocessing already-analyzed threads (local + cloud state sync)
- **Batch Analysis** — Process multiple threads in a single run with configurable limits
- **Multiple Modes** — Interactive (Claude Code), automated CI/CD (`--ci`), or report-only (`--dry-run`)

### Integrations

- **Claude Code** — Installs agents (Geni Analyzer, Issue Resolver) and skills (`/analyze-latest`, `/issues`, `/instrument-tracing`, `/geni-init`) into your project
- **LangSmith** — Annotation queue polling, thread detail fetching, tracing
- **Jira** — Issue creation, status transitions, search, field mapping
- **Notion** — Database entry creation for issue tracking
- **AWS** — Cognito authentication, Secrets Manager for credentials, DynamoDB state sync

---

## Installation

```bash
pip install geniable
```

For CI/CD mode (headless analysis with Anthropic API):

```bash
pip install geniable[llm]
```

**Requirements:** Python 3.11+

### Prerequisites

- AWS CLI configured with credentials
- Access to deployed Integration and Evaluation Services (for QA pipeline)

#### Required AWS Permissions

```json
{
  "Effect": "Allow",
  "Action": [
    "secretsmanager:CreateSecret",
    "secretsmanager:PutSecretValue",
    "secretsmanager:GetSecretValue",
    "secretsmanager:ListSecrets"
  ],
  "Resource": "arn:aws:secretsmanager:*:*:secret:geniable/*"
}
```

---

## Quick Start

### 1. Login

```bash
geni login
```

Authenticates with AWS Cognito. Tokens are stored in your system keyring (macOS Keychain, Windows Credential Store) or encrypted file (`--no-keyring`).

### 2. Initialize

```bash
geni init
```

Interactive wizard that configures:
- LangSmith API credentials and annotation queue
- Issue tracker (Jira, Notion, or none)
- Cloud credential sync (AWS Secrets Manager)
- Claude Code agent and skill installation

### 3. Scaffold an Agent

```bash
geni new
```

Interactive generator that walks you through framework, provider, and identity layer selection.

### 4. Analyze

```bash
geni analyze latest
```

Fetches unanalyzed threads and launches the Geni Analyzer for interactive analysis.

---

## Commands

### Authentication

| Command | Description |
|---------|-------------|
| `geni login` | Login via AWS Cognito (SRP auth) |
| `geni login --reset` | Reset password via email verification |
| `geni logout` | Logout and clear tokens |
| `geni whoami` | Show current user |

### Configuration

| Command | Description |
|---------|-------------|
| `geni init` | Interactive setup wizard |
| `geni configure --show` | Display current configuration (secrets masked) |
| `geni configure --validate` | Test all service connections |
| `geni configure --sync-secrets` | Sync credentials to AWS Secrets Manager |
| `geni configure --list-secrets` | List secrets in AWS Secrets Manager |
| `geni configure --reset` | Reset to template configuration |

### Analysis

| Command | Description |
|---------|-------------|
| `geni analyze latest` | Analyze latest threads from queue |
| `geni analyze latest --limit 10` | Analyze up to 10 threads |
| `geni analyze latest --dry-run` | Analyze without creating tickets |
| `geni analyze latest --ci` | Automated mode for CI/CD pipelines |
| `geni run` | Run full analysis pipeline |
| `geni run --report-only` | Generate reports without tickets |
| `geni run --force` | Reprocess already-processed threads |

### Issue Management

| Command | Description |
|---------|-------------|
| `geni issues` | List issues from your tracker (Jira/Notion) |
| `geni issues list` | List issues with filters |
| `geni issues get <key>` | Get details for a specific issue |
| `geni issues mark-done <key>` | Transition an issue to Done |
| `geni ticket create '<json>'` | Create ticket from IssueCard JSON |

### Agent Project Scaffolding

| Command | Description |
|---------|-------------|
| `geni new` | Interactive scaffold generator for agent projects |

Supports three frameworks:
- **LangGraph** — StateGraph + LangChain, closest to reference architecture
- **Strands** — strands-agents SDK, model-first with `@tool` decorators
- **Pi** — Pi agent framework, declarative config with gateway pattern

### Utilities

| Command | Description |
|---------|-------------|
| `geni status` | Show connection status for all services |
| `geni stats` | Show processing history and statistics |
| `geni discover` | List available evaluation tools from cloud |
| `geni inject` | Copy agent code locally for Claude Code visibility |
| `geni clear-state` | Reset processing state |
| `geni version` | Show version |

---

## Claude Code Integration

Geniable installs agents and skills into your project's `.claude/` directory during `geni init`.

### Agents

| Agent | Purpose |
|-------|---------|
| **Geni Analyzer** | Analyzes LangSmith threads for quality issues and creates tickets |
| **Issue Resolver** | Reviews open issues and suggests fixes with code changes |

### Skills (Slash Commands)

| Skill | Purpose |
|-------|---------|
| `/analyze-latest` | Fetch and analyze threads from the annotation queue |
| `/issues` | Browse and manage issues from your tracker |
| `/instrument-tracing` | Add LangSmith tracing to your codebase |
| `/geni-init` | Initialize Geniable configuration |

---

## Configuration

Configuration is stored in `~/.geniable.yaml`:

```yaml
langsmith:
  api_key: "ls_..."
  project: "my-project"
  queue: "quality-review"

aws:
  region: "ap-southeast-2"
  integration_endpoint: "https://xxx.execute-api.region.amazonaws.com/prod"
  evaluation_endpoint: "https://yyy.execute-api.region.amazonaws.com/prod"
  api_key: ""  # Optional API Gateway key

provider: "jira"  # or "notion" or "none"

jira:
  base_url: "https://company.atlassian.net"
  email: "user@company.com"
  api_token: "..."
  project_key: "PROJ"
  issue_type: "Bug"

notion:
  api_key: "secret_..."
  database_id: "..."

defaults:
  report_dir: "./reports"
  log_level: "INFO"
```

### Environment Variables

Override any config value:

```bash
export LANGSMITH_API_KEY="ls_..."
export JIRA_API_TOKEN="..."
export ANTHROPIC_API_KEY="sk-ant-..."  # Required for --ci mode
```

<details>
<summary>Full environment variable reference</summary>

| Variable | Overrides |
|----------|-----------|
| `LANGSMITH_API_KEY` | `langsmith.api_key` |
| `LANGSMITH_PROJECT` | `langsmith.project` |
| `LANGSMITH_QUEUE` | `langsmith.queue` |
| `AWS_REGION` | `aws.region` |
| `INTEGRATION_ENDPOINT` | `aws.integration_endpoint` |
| `EVALUATION_ENDPOINT` | `aws.evaluation_endpoint` |
| `ISSUE_PROVIDER` | `provider` |
| `JIRA_BASE_URL` | `jira.base_url` |
| `JIRA_EMAIL` | `jira.email` |
| `JIRA_API_TOKEN` | `jira.api_token` |
| `JIRA_PROJECT_KEY` | `jira.project_key` |
| `NOTION_API_KEY` | `notion.api_key` |
| `NOTION_DATABASE_ID` | `notion.database_id` |

</details>

### AWS Secrets Manager

Credentials are stored in AWS Secrets Manager (required for QA pipeline):

| Secret Name | Contents |
|-------------|----------|
| `geniable/langsmith` | LangSmith API key |
| `geniable/jira` | Jira credentials (token, email, URL, project) |
| `geniable/notion` | Notion credentials (API key, database ID) |
| `geniable/aws-gateway` | AWS API Gateway key |

---

## Issue Detection

The evaluation pipeline identifies these issue types:

| Category | Examples | Priority |
|----------|----------|----------|
| **Security** | Data exposure, leaked internals, auth issues | Critical/High |
| **Quality** | Incomplete responses, hallucinations, poor UX | High |
| **Performance** | Slow response (>30s), high tokens (>50K) | High/Medium |
| **Bug** | Errors, exceptions, failures | High |

### IssueCard Schema

All issue tickets use a standardized 9-field schema:

| Field | Description |
|-------|-------------|
| `title` | Issue summary |
| `priority` | Critical, High, Medium, Low |
| `category` | Security, Quality, Performance, Bug |
| `status` | Open, In Progress, Resolved |
| `details` | Detailed issue description |
| `description` | Brief summary |
| `recommendation` | Suggested fix |
| `affected_code` | Location + improvement suggestions |
| `sources` | thread_id, thread_name, run_id, langsmith_url |

---

## Reports

Analysis reports are saved to `./reports/` (configurable):

```
reports/
├── processing_state.json          # Tracks processed threads
├── Thread-ProjectName-abc123.md   # Individual thread reports
├── analysis_report_YYYYMMDD.md    # Batch analysis reports
└── coverage/                      # Test coverage reports
```

Each thread report includes:
- Thread metadata (ID, duration, tokens)
- User query and final response
- Evaluation results from all tools
- Issue classifications
- Links to LangSmith and created tickets

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       LOCAL (geniable CLI)                       │
│                                                                  │
│  cli/main.py → agent/agent.py → API Clients → Cloud Services   │
│       │              │                                           │
│  cli/commands/   agent/mcp_client.py    agent/state_manager.py  │
│  cli/scaffold/   agent/evaluation_orchestrator.py               │
│  cli/wizard.py   agent/report_generator.py                      │
└─────────────────────┬───────────────────────────────────────────┘
                      │ REST API + Cognito Auth
┌─────────────────────▼───────────────────────────────────────────┐
│                    AWS CLOUD (geniable-cloud)                    │
│                                                                  │
│  ┌─────────────────────────┐   ┌──────────────────────────┐     │
│  │ Integration Service     │   │ Evaluation Service       │     │
│  │ • Thread fetching       │   │ • MCP tool discovery     │     │
│  │ • Ticket creation       │   │ • Evaluation execution   │     │
│  │ • Issue search/get      │   │ • Latency analysis       │     │
│  │ • Status transitions    │   │ • Content quality        │     │
│  │ • User config CRUD      │   │ • Error detection        │     │
│  │ • State sync            │   │ • Token usage analysis   │     │
│  └─────────────────────────┘   └──────────────────────────┘     │
│                                                                  │
│  Cognito (auth) │ DynamoDB (state + config) │ Secrets Manager   │
│  KMS (encryption) │ CloudWatch (monitoring) │ API Gateway       │
└──────────────────────────────────────────────────────────────────┘
```

### Key Design Patterns

- **Per-user isolation** — Cognito auth + user-specific configs in DynamoDB + per-user secrets
- **Lazy initialization** — Lambda handlers create clients on-demand
- **Repository pattern** — `*_repository.py` abstracts data access
- **Factory pattern** — `issue_provider_factory.py` for Jira/Notion selection
- **MCP protocol** — Tool discovery and execution via `agent/mcp_client.py`
- **Template pattern** — Scaffold base class with framework-specific overrides
- **State management** — Local JSON + cloud DynamoDB with sync

---

## Development

### Project Structure

```
cli/
├── __init__.py
├── __main__.py             # Entry point
├── main.py                 # CLI commands (Typer app)
├── auth.py                 # AWS Cognito authentication (SRP)
├── auth_middleware.py       # Auth token middleware
├── wizard.py               # Interactive configuration wizard
├── config_manager.py       # Configuration loading/saving
├── service_validator.py    # Service connection testing
├── secrets_manager.py      # AWS Secrets Manager integration
├── validators.py           # Input validation helpers
├── injector.py             # Agent code injection
├── output_formatter.py     # Rich console output
├── issue_display.py        # Issue formatting helpers
├── claude_code_setup.py    # Claude Code agent/skill installer
├── version_check.py        # PyPI version checking
├── commands/
│   ├── analyze.py          # Analysis subcommands
│   ├── issues.py           # Issue management subcommands
│   ├── scaffold.py         # Scaffold subcommands
│   └── ticket.py           # Ticket creation subcommands
├── scaffold/
│   ├── __init__.py         # Scaffold registry
│   ├── base.py             # Base scaffold (20 principles, identity layers)
│   ├── langgraph.py        # LangGraph framework scaffold
│   ├── strands.py          # Strands framework scaffold
│   └── pi.py               # Pi framework scaffold
├── agents/
│   ├── Geni Analyzer.md    # Thread analysis agent
│   └── Issue Resolver.md   # Issue resolution agent
└── skills/
    ├── analyze-latest.md   # /analyze-latest skill
    ├── issues.md           # /issues skill
    ├── instrument-tracing.md  # /instrument-tracing skill
    └── geni-init.md        # /geni-init skill
```

### Setup

```bash
source venv/bin/activate
pip install -e ".[dev]"
```

### Quality Checks

```bash
make lint        # Ruff linting
make format      # Black + isort
make typecheck   # Mypy (strict mode)
```

### Testing

```bash
make test        # All tests with coverage (70% threshold)
make test-unit   # Unit tests only
make test-cov    # Tests with HTML coverage report
```

### Running from Source

```bash
# Using Python module
python -m cli <command>

# Or with the entry point (if installed)
geni <command>
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Authentication required" | `geni login` |
| "Configuration file not found" | `geni init` |
| Service validation failures | `geni configure --validate` |
| Reprocess all threads | `geni clear-state -y` |
| Debug mode | `geni analyze latest --verbose` or `geni run --verbose` |
| Password reset | `geni login --reset` |
| "boto3 is required" | `pip install boto3` |
| "Cannot connect to AWS" | Run `aws configure` or set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` |
| "Invalid API key format" | LangSmith keys must start with `ls_`, Notion keys with `secret_` |

---

## License

MIT

---

## Links

- **Repository**: https://github.com/mnedelko/geniable
- **Issues**: https://github.com/mnedelko/geniable/issues
- **PyPI**: https://pypi.org/project/geniable/
