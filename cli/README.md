# Geniable CLI

Command-line interface for analyzing LangSmith conversation threads, running evaluations via cloud services, and creating issue tickets in Jira or Notion.

## Overview

The CLI provides a local interface to the LangSmith Thread Analyzer pipeline:

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│   LangSmith     │────▶│  Integration Service │────▶│  Evaluation     │
│ Annotation Queue│     │  (AWS Lambda)        │     │  Service (AWS)  │
└─────────────────┘     └──────────────────────┘     └─────────────────┘
                                  │                          │
                                  ▼                          ▼
                        ┌──────────────────┐      ┌──────────────────┐
                        │   Jira/Notion    │      │   Evaluation     │
                        │   Ticket Creation│      │   Results        │
                        └──────────────────┘      └──────────────────┘
                                  │                          │
                                  └──────────┬───────────────┘
                                             ▼
                                  ┌──────────────────┐
                                  │  Local Reports   │
                                  │  (./reports/)    │
                                  └──────────────────┘
```

## Prerequisites

- Python 3.11+
- AWS CLI configured with credentials
- boto3 (for AWS Secrets Manager)
- Access to deployed Integration and Evaluation Services

### Required AWS Permissions

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

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd geniable

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install CLI in development mode (optional)
pip install -e .
```

## Quick Start

### 1. Initialize Configuration

```bash
geniinit
```

This interactive wizard will:
1. Collect LangSmith API credentials
2. Collect AWS service endpoints
3. Configure issue tracker (Jira, Notion, or none)
4. Validate all service connections
5. **Sync credentials to AWS Secrets Manager** (required)
6. Create local config file and reports directory

### 2. Inject Agent Code (Optional)

For Claude Code visibility into the evaluation pipeline:

```bash
geniinject ./agent
```

### 3. Run Analysis

```bash
# Analyze latest threads from the annotation queue
genianalyze-latest

# Or select a specific thread interactively
genianalyze-specific
```

## Commands Reference

### `init`

Initialize configuration with interactive wizard.

```bash
geniinit [OPTIONS]

Options:
  -f, --force           Overwrite existing configuration
  --skip-validation     Skip service validation step
```

**What happens during init:**
- Step 1: LangSmith Configuration (API key, project, queue)
- Step 2: AWS Configuration (region, Integration/Evaluation endpoints)
- Step 3: Issue Tracker Integration (Jira, Notion, or none)
- Step 4: Service Validation (tests all connections)
- Step 5: AWS Secrets Manager Sync (stores credentials securely)

**Files created:**
- `~/.geniable.yaml` - Local configuration
- `./reports/` - Reports directory
- `./reports/processing_state.json` - Processing state tracker

### `configure`

Manage configuration and credentials.

```bash
geniconfigure [OPTIONS]

Options:
  --show           Show current configuration (secrets masked)
  --validate       Validate configuration and test connections
  --reset          Reset to template configuration
  --sync-secrets   Sync credentials to AWS Secrets Manager
  --list-secrets   List secrets in AWS Secrets Manager
```

**Examples:**

```bash
# View current config
geniconfigure --show

# Validate all services
geniconfigure --validate

# Re-sync credentials to AWS after manual config edit
geniconfigure --sync-secrets

# List stored secrets
geniconfigure --list-secrets
```

### `analyze-latest`

Analyze latest annotated threads from the LangSmith queue.

```bash
genianalyze-latest [OPTIONS]

Options:
  -l, --limit INTEGER   Maximum threads to analyze (default: 50)
  --dry-run             Analyze without creating tickets
  -v, --verbose         Verbose output
```

**Examples:**

```bash
# Analyze up to 10 threads
genianalyze-latest --limit 10

# Dry run (no tickets created)
genianalyze-latest --dry-run

# Verbose output for debugging
genianalyze-latest -v
```

### `analyze-specific`

Select and analyze a specific thread interactively.

```bash
genianalyze-specific [OPTIONS]

Options:
  -c, --count INTEGER   Number of recent threads to show (default: 10)
  -v, --verbose         Verbose output
```

### `run`

Run the full analysis pipeline with more control.

```bash
genirun [OPTIONS]

Options:
  -l, --limit INTEGER     Maximum threads to analyze (default: 50)
  --dry-run               Analyze without creating tickets
  --report-only           Generate report only (no tickets)
  -q, --queue TEXT        Override annotation queue name
  -p, --provider TEXT     Override provider (jira/notion)
  -f, --force             Reprocess already-processed threads
  -v, --verbose           Verbose output
```

### `inject`

Inject agent code for Claude Code visibility.

```bash
geniinject [TARGET] [OPTIONS]

Arguments:
  TARGET    Target directory (default: ./agent)

Options:
  -f, --force      Overwrite existing files
  --no-shared      Skip shared module
```

### `status`

Show current processing status and test connections.

```bash
genistatus [OPTIONS]

Options:
  -v, --verbose    Show detailed status
```

### `stats`

Show processing statistics and history.

```bash
genistats
```

### `discover`

Discover available evaluation tools from the Evaluation Service.

```bash
genidiscover
```

### `clear-state`

Clear processing state to allow reprocessing all threads.

```bash
geniclear-state [OPTIONS]

Options:
  -y, --yes    Skip confirmation prompt
```

### `version`

Show version information.

```bash
geniversion
```

## Configuration

### Configuration File

Location: `~/.geniable.yaml`

```yaml
langsmith:
  api_key: "ls_..."
  project: "my-project"
  queue: "quality-review"

aws:
  region: "ap-southeast-2"
  integration_endpoint: "https://xxx.execute-api.ap-southeast-2.amazonaws.com/prod"
  evaluation_endpoint: "https://yyy.execute-api.ap-southeast-2.amazonaws.com/prod"
  api_key: ""  # Optional API Gateway key

provider: "jira"  # or "notion" or "none"

jira:
  base_url: "https://company.atlassian.net"
  email: "user@company.com"
  api_token: "..."
  project_key: "PROJ"
  issue_type: "Bug"

# notion:
#   api_key: "secret_..."
#   database_id: "..."

defaults:
  report_dir: "./reports"
  log_level: "INFO"
```

### Environment Variable Overrides

Environment variables can override config file values:

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

### AWS Secrets Manager

Credentials are stored in AWS Secrets Manager (required):

| Secret Name | Contents |
|-------------|----------|
| `geniable/langsmith` | LangSmith API key |
| `geniable/jira` | Jira credentials (token, email, URL, project) |
| `geniable/notion` | Notion credentials (API key, database ID) |
| `geniable/aws-gateway` | AWS API Gateway key |

## Reports

Analysis reports are saved to `./reports/` (configurable):

```
reports/
├── processing_state.json           # Tracks processed threads
├── Thread-ProjectName-abc123.md    # Individual thread reports
├── analysis_report_YYYYMMDD.md     # Batch analysis reports
└── coverage/                       # Test coverage reports
```

### Report Contents

Each thread report includes:
- Thread metadata (ID, duration, tokens)
- User query and final response
- Evaluation results from all tools
- Issue classifications
- Links to LangSmith and created tickets

## Troubleshooting

### Common Issues

**"boto3 is required for AWS Secrets Manager"**
```bash
pip install boto3
```

**"Cannot connect to AWS Secrets Manager"**
```bash
# Configure AWS credentials
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=ap-southeast-2
```

**"Configuration file not found"**
```bash
geniinit
```

**"Invalid API key format"**
- LangSmith keys must start with `ls_`
- Notion keys must start with `secret_`

**Service validation failures**
```bash
# Check individual service connections
geniconfigure --validate

# View detailed error messages
genistatus -v
```

### Logs

Enable verbose logging:
```bash
genianalyze-latest -v
```

Or set log level in config:
```yaml
defaults:
  log_level: "DEBUG"
```

### Reset State

To reprocess all threads:
```bash
geniclear-state -y
```

Or manually delete the state file:
```bash
rm ./reports/processing_state.json
```

## Development

### Project Structure

```
cli/
├── __init__.py
├── __main__.py           # Entry point
├── main.py               # CLI commands (Typer app)
├── wizard.py             # Interactive configuration wizard
├── config_manager.py     # Configuration loading/saving
├── service_validator.py  # Service connection testing
├── secrets_manager.py    # AWS Secrets Manager integration
├── validators.py         # Input validation helpers
├── injector.py           # Agent code injection
├── output_formatter.py   # Rich console output
└── commands/
    └── analyze.py        # Analysis subcommands
```

### Running from Source

```bash
# Using Python module
python -m cli.main <command>

# Or with the entry point (if installed)
geni<command>
```

### Testing

```bash
# Run tests
pytest tests/cli/ -v

# With coverage
pytest tests/cli/ --cov=cli --cov-report=html
```

## License

[Add license information]
