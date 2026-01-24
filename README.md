# Geniable

A hybrid local-cloud QA pipeline for analyzing LangSmith conversation threads, running evaluations, and creating issue tickets.

## Components

| Component | Description | Documentation |
|-----------|-------------|---------------|
| **CLI** | Local command-line interface for analysis | [cli/README.md](cli/README.md) |
| **Integration Service** | AWS Lambda for LangSmith/Jira/Notion integration | [cloud/](cloud/) |
| **Evaluation Service** | AWS Lambda for running evaluation tools | [cloud/](cloud/) |

## Quick Start (CLI)

```bash
# Install
pip install -r requirements.txt

# Initialize (configures credentials and syncs to AWS Secrets Manager)
geni init

# Run analysis
geni analyze-latest
```

See [cli/README.md](cli/README.md) for full CLI documentation.

---

# Lambda Deployment (Legacy)

AWS Lambda function that polls LangSmith annotation queues, analyzes conversation threads for issues, and creates issue pages in Notion.

## Features

- **On-demand invocation** via API Gateway or direct Lambda invoke
- **DynamoDB state persistence** for tracking processed threads
- **Direct Notion SDK integration** with dynamic property detection
- **Automatic issue classification** based on error patterns, performance, and token usage
- **SAM-based deployment** for infrastructure as code

## Architecture

```
LangSmith Annotation Queue
         │
         ▼
    AWS Lambda (geniable)
         │
         ├──► Analyze threads for issues
         │    - Performance (long execution time > 30s)
         │    - Token usage (high token count > 50K)
         │    - Errors in execution steps
         │
         ├──► Create issues in Notion
         │
         └──► Track state in DynamoDB
```

## Quick Start

### Prerequisites

- Python 3.11+
- AWS CLI configured
- AWS SAM CLI installed
- Docker (for building with native dependencies)
- LangSmith API key
- Notion integration token with database access

### Configuration

1. Copy environment template:

```bash
cp .env.example .env
```

2. Fill in your credentials in `.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `LANGSMITH_API_KEY` | Yes | LangSmith API key from https://smith.langchain.com/settings |
| `LANGSMITH_PROJECT` | No | Project name (default: `insights-agent-v2`) |
| `LANGSMITH_QUEUE` | Yes | Annotation queue name (exact match required) |
| `NOTION_API_KEY` | Yes | Notion integration token |
| `NOTION_DATABASE_ID` | Yes | Target Notion database ID |
| `NOTION_DATA_SOURCE_ID` | Yes | Data source ID for page creation |

### Deployment

```bash
# Build with Docker (required for native dependencies)
sam build --use-container

# Deploy to dev environment
make deploy-dev
```

After deployment, update Lambda environment variables directly:

```bash
aws lambda update-function-configuration \
  --function-name geniable-dev \
  --region ap-southeast-2 \
  --environment "Variables={
    LANGSMITH_API_KEY=your_key,
    LANGSMITH_PROJECT=insights-agent-v2,
    LANGSMITH_QUEUE=Your Queue Name,
    NOTION_API_KEY=your_notion_key,
    NOTION_DATABASE_ID=your_db_id,
    NOTION_DATA_SOURCE_ID=your_ds_id,
    DYNAMODB_TABLE_NAME=langsmith-thread-state-dev,
    AWS_REGION_NAME=ap-southeast-2,
    LOG_LEVEL=INFO
  }"
```

## Usage

### Actions

| Action | Description |
|--------|-------------|
| `poll` | Check annotation queue for new threads |
| `full` | Poll + process all new threads (creates Notion issues) |
| `status` | Get processing statistics |
| `process` | Process a specific thread by ID |

### Direct Lambda Invocation (Recommended)

**Poll for new threads:**
```bash
aws lambda invoke \
  --function-name geniable-dev \
  --payload '{"action":"poll"}' \
  --cli-binary-format raw-in-base64-out \
  --region ap-southeast-2 \
  /dev/stdout
```

**Full processing (poll + create issues):**
```bash
aws lambda invoke \
  --function-name geniable-dev \
  --payload '{"action":"full"}' \
  --cli-binary-format raw-in-base64-out \
  --region ap-southeast-2 \
  /dev/stdout
```

**Check status:**
```bash
aws lambda invoke \
  --function-name geniable-dev \
  --payload '{"action":"status"}' \
  --cli-binary-format raw-in-base64-out \
  --region ap-southeast-2 \
  /dev/stdout
```

**Process specific thread:**
```bash
aws lambda invoke \
  --function-name geniable-dev \
  --payload '{"action":"process","thread_id":"your-thread-uuid"}' \
  --cli-binary-format raw-in-base64-out \
  --region ap-southeast-2 \
  /dev/stdout
```

### Makefile Commands

```bash
make invoke-dev-full    # Poll + process all new threads
make invoke-dev-poll    # Just poll for new threads
make invoke-dev-status  # Get processing statistics
make logs-dev           # Tail Lambda logs
make outputs-dev        # Show stack outputs
```

### API Gateway (requires API key)

```bash
# Poll
curl -X POST https://{api-id}.execute-api.ap-southeast-2.amazonaws.com/dev/analyze \
  -H "x-api-key: {api-key}" \
  -H "Content-Type: application/json" \
  -d '{"action": "poll"}'

# Full processing
curl -X POST https://{api-id}.execute-api.ap-southeast-2.amazonaws.com/dev/analyze \
  -H "x-api-key: {api-key}" \
  -H "Content-Type: application/json" \
  -d '{"action": "full"}'

# Status
curl https://{api-id}.execute-api.ap-southeast-2.amazonaws.com/dev/status \
  -H "x-api-key: {api-key}"
```

Get API key: `make get-api-key-dev`

## Issue Detection

The analyzer identifies these issue types:

| Issue Type | Trigger | Priority |
|------------|---------|----------|
| Long Execution | Duration > 30 seconds | Medium |
| High Token Usage | Tokens > 50,000 | Medium |
| Step Errors | Any step with error | Based on severity |
| Thread Errors | Thread-level errors | Based on severity |

## Notion Database

The client automatically detects your database schema and adapts to available properties.

**Supported properties:**
- Title property (required, auto-detected)
- Priority (select)
- Category (select)
- Complexity (select)
- Status (status or select)

## AWS Resources Created

| Resource | Name |
|----------|------|
| Lambda Function | `geniable-{env}` |
| DynamoDB Table | `langsmith-thread-state-{env}` |
| API Gateway | `geniable-api-{env}` |
| CloudWatch Logs | `/aws/lambda/geniable-{env}` |
| CloudWatch Alarm | Error threshold monitoring |

## Project Structure

```
langsmith-lambda/
├── src/
│   ├── handler.py              # Lambda entry point
│   ├── config.py               # Environment configuration
│   ├── langsmith_client.py     # LangSmith API client
│   ├── notion_issue_client.py  # Notion SDK integration
│   ├── state_manager.py        # DynamoDB state operations
│   ├── issue_classifier.py     # Issue classification logic
│   └── models/                 # Data models
├── template.yaml               # SAM template
├── samconfig.toml              # SAM configuration
├── Makefile                    # Build/deploy commands
├── requirements.txt            # Python dependencies
└── .env                        # Environment variables (not committed)
```

## Troubleshooting

### Check Lambda Logs
```bash
make logs-dev
# or
aws logs tail /aws/lambda/geniable-dev --since 10m --region ap-southeast-2
```

### Reset Processed State
To reprocess a thread, delete it from DynamoDB:
```bash
aws dynamodb delete-item \
  --table-name langsmith-thread-state-dev \
  --region ap-southeast-2 \
  --key '{"pk": {"S": "THREAD#your-thread-id"}, "sk": {"S": "METADATA"}}'
```

### Common Issues

1. **Missing environment variables**: SAM parameter overrides may not work correctly with special characters. Update Lambda configuration directly via AWS CLI or console.

2. **Notion property errors**: The client auto-detects database properties. Check logs to see detected properties: `Database properties: [...]`

3. **Queue not found**: Verify the exact queue name matches (including any typos in the original name).

4. **No new threads found**: Threads are tracked in DynamoDB. Use the reset command above to reprocess.

## Development

```bash
# Install dependencies
make install-dev

# Run tests
make test

# Run with coverage
make test-coverage

# Format code
make format

# Lint
make lint

# Local testing with SAM
make local
```

## Estimated Costs

| Usage | Lambda | DynamoDB | API Gateway | Total |
|-------|--------|----------|-------------|-------|
| 10 invocations/day | $0.50 | $1.00 | $0.50 | ~$2/month |
| 100 invocations/day | $2.00 | $5.00 | $3.50 | ~$10/month |

## Cleanup

```bash
# Delete dev stack
make delete-dev
```
