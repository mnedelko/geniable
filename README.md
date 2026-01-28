# Geniable

**Hybrid Local-Cloud QA Pipeline for LangSmith Thread Analysis**

Geniable analyzes your LangSmith conversation threads for quality issues, performance problems, and errors—then creates tickets in Jira or Notion automatically.

## Features

- **Thread Analysis** - Fetch and analyze threads from your LangSmith annotation queue
- **Issue Detection** - Identify performance, quality, security, and UX issues
- **Ticket Creation** - Create standardized issue tickets in Jira or Notion
- **Claude Code Integration** - Interactive analysis via `/analyze-latest` command
- **CI/CD Support** - Automated analysis for pipelines using Anthropic API
- **State Tracking** - Avoids reprocessing already-analyzed threads

---

## Installation

```bash
pip install geniable
```

**Requirements:** Python 3.11+

---

## Quick Start

### 1. Login

```bash
geni login
```

Authenticate with your email and password. Tokens are stored securely.

### 2. Initialize

```bash
geni init
```

Interactive wizard that configures:
- LangSmith API credentials and annotation queue
- Issue tracker (Jira, Notion, or none)
- Claude Code integration (optional)

### 3. Analyze

```bash
geni analyze-latest
```

Fetches unanalyzed threads and launches the Geni Analyzer for interactive analysis.

---

## Commands

### Authentication

| Command | Description |
|---------|-------------|
| `geni login` | Login to Geniable |
| `geni logout` | Logout and clear tokens |
| `geni whoami` | Show current user |

### Configuration

| Command | Description |
|---------|-------------|
| `geni init` | Interactive setup wizard |
| `geni configure --show` | Display current configuration |
| `geni configure --validate` | Test all service connections |
| `geni configure --sync-secrets` | Sync credentials to cloud |

### Analysis

| Command | Description |
|---------|-------------|
| `geni analyze latest` | Analyze latest threads from queue |
| `geni analyze latest --limit 10` | Analyze up to 10 threads |
| `geni analyze latest --dry-run` | Analyze without creating tickets |
| `geni analyze latest --ci` | Automated mode for CI/CD pipelines |

### Tickets

| Command | Description |
|---------|-------------|
| `geni ticket create '<json>'` | Create ticket from IssueCard JSON |

### Utilities

| Command | Description |
|---------|-------------|
| `geni status` | Show connection status |
| `geni stats` | Show processing history |
| `geni clear-state` | Reset processing state |
| `geni --version` | Show version |

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

defaults:
  report_dir: "./reports"
  log_level: "INFO"
```

### Environment Variables

Override any config value with environment variables:

```bash
export LANGSMITH_API_KEY="ls_..."
export JIRA_API_TOKEN="..."
export ANTHROPIC_API_KEY="sk-ant-..."  # Required for --ci mode
```

---

## Claude Code Integration

Geniable integrates with Claude Code for interactive analysis.

### Setup

During `geni init`, Geniable installs:
- **Skill**: `.claude/commands/analyze-latest.md`
- **Agent**: `.claude/agents/Geni Analyzer.md`
- **Permissions**: `.claude/settings.local.json`

### Usage

In Claude Code, run:

```
/analyze-latest
```

The Geni Analyzer agent will:
1. Fetch unanalyzed threads from your LangSmith queue
2. Analyze each thread for issues (security, quality, performance, UX)
3. Generate potential solutions for each issue
4. Present findings and ask for ticket creation confirmation
5. Create tickets in Jira/Notion for approved issues

---

## Usage Modes

### Interactive Mode (Default)

```bash
geni analyze-latest
```

Launches Claude Code for real-time, interactive analysis. Best for development and debugging.

### CI/CD Mode

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
geni analyze-latest --ci
```

Automated analysis using Anthropic API directly. Best for scheduled pipelines.

### Report-Only Mode

```bash
geni analyze-latest --dry-run
```

Generates reports without creating tickets. Best for previewing analysis.

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

## Issue Detection

The analyzer identifies these issue types:

| Category | Examples | Priority |
|----------|----------|----------|
| **Security** | Data exposure, leaked internals, auth issues | Critical/High |
| **Quality** | Incomplete responses, hallucinations, poor UX | High |
| **Performance** | Slow response (>30s), high tokens (>50K) | High/Medium |
| **Bug** | Errors, exceptions, failures | High |

---

## Troubleshooting

### "Authentication required"

```bash
geni login
```

### "Configuration file not found"

```bash
geni init
```

### Service validation failures

```bash
geni configure --validate
```

### Reset processing state

To reprocess all threads:

```bash
geni clear-state -y
```

### Debug mode

```bash
geni analyze-latest --verbose
```

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Quality checks
make lint        # Ruff linting
make format      # Black + isort
make typecheck   # Mypy

# Testing
make test        # All tests with coverage
make test-unit   # Unit tests only
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       LOCAL (geniable/)                      │
│  CLI → Agent → API Clients → AWS Cloud Services             │
└─────────────────────┬───────────────────────────────────────┘
                      │ REST API + Cognito Auth
┌─────────────────────▼───────────────────────────────────────┐
│                    AWS CLOUD                                 │
│  ┌─────────────────────────┐   ┌──────────────────────────┐ │
│  │ Integration Service     │   │ Evaluation Service       │ │
│  │ • /threads/annotated    │   │ • /evaluations/discovery │ │
│  │ • /threads/{id}/details │   │ • /evaluations/execute   │ │
│  │ • /integrations/ticket  │   │                          │ │
│  └─────────────────────────┘   └──────────────────────────┘ │
│                                                              │
│  DynamoDB (state) + Secrets Manager (credentials)           │
└──────────────────────────────────────────────────────────────┘
```

---

## License

MIT

---

## Links

- **Repository**: https://github.com/mnedelko/geniable
- **Issues**: https://github.com/mnedelko/geniable/issues
- **PyPI**: https://pypi.org/project/geniable/
