# Geniable

**AI Agent Framework Harness — scaffold performant, security-hardened agents with proven engineering principles and evaluation-driven development built in.**

Geniable helps you build AI agents that are performant, maintainable, and secure in production. It provides:

- **`geni new`** — Generate production-ready agent projects grounded in 20 architectural principles. Choose your framework (LangGraph, Strands, Pi), model provider (Bedrock, OpenAI, Google, Ollama), and get a fully wired project with identity layers, tool governance, observability, model resilience, and graceful degradation built in.

- **QA Pipeline** — An out-of-the-box evaluation loop that connects to your LangSmith annotation queue, runs cloud-hosted evaluations against conversation threads, detects issues, and creates tickets in Jira or Notion automatically — enabling evaluation-driven development and experimentation from day one.

[![PyPI](https://img.shields.io/pypi/v/geniable)](https://pypi.org/project/geniable/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

<p align="center">
  <img src="assets/logo.png" alt="Geniable Logo" width="200">
</p>

---

## Features

### Agent Project Scaffolding (`geni new`)

- **Multi-framework support** — LangGraph, Strands Agents, and Pi agent frameworks
- **Multi-provider models** — AWS Bedrock (Claude), OpenAI (GPT-4o), Google (Gemini), Ollama (local)
- **20-principle architecture** — Each scaffold embeds production patterns: identity layers, tool governance, observability, model resilience, session persistence, graceful degradation, and more
- **Identity layer system** — Configurable layers for rules, personality, public identity, tool guidance, user context, persistent memory, bootstrap, and scheduled duties
- **LangSmith tracing** — Optional built-in tracing instrumentation

### QA Pipeline (Evaluation-Driven Development)

- **Thread Analysis** — Fetch and analyze threads from your LangSmith annotation queue
- **Automated Evaluations** — Run cloud-hosted MCP evaluators (latency, content quality, error detection, token usage)
- **Issue Detection** — Identify performance, quality, security, and UX issues with structured IssueCards
- **Ticket Creation** — Create standardized tickets in Jira or Notion with affected code and recommendations
- **State Tracking** — Avoids reprocessing already-analyzed threads (local + cloud state sync)
- **Batch Analysis** — Process multiple threads in a single run with configurable limits
- **Multiple Modes** — Interactive (Claude Code), automated CI/CD (`--ci`), or report-only (`--dry-run`)

### Integrations

- **Claude Code** — Installs agents (Geni Analyzer, Issue Resolver) and skills (`/analyze-latest`, `/issues`, `/instrument-tracing`) into your project
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

### 3. Analyze

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
| `geni configure --show` | Display current configuration |
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

aws:
  region: "us-east-1"

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
└── analysis_report_20250125.md    # Batch analysis reports
```

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
- **State management** — Local JSON + cloud DynamoDB with sync

---

## Development

```bash
# Setup
source venv/bin/activate
pip install -e ".[dev]"

# Quality checks
make lint        # Ruff linting
make format      # Black + isort
make typecheck   # Mypy (strict mode)

# Testing
make test        # All tests with coverage (70% threshold)
make test-unit   # Unit tests only
make test-cov    # Tests with HTML coverage report

# Cloud deployment
make build       # SAM build
make deploy-dev  # Deploy to dev environment
make local-api   # Start local API for testing

# PyPI publishing
make package     # Build Python package
make publish     # Publish to PyPI
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

---

## License

MIT

---

## Links

- **Repository**: https://github.com/mnedelko/geniable
- **Issues**: https://github.com/mnedelko/geniable/issues
- **PyPI**: https://pypi.org/project/geniable/
