# /geni-init

Initialize Geniable for this project. Sets up the Geni Analyzer agent, configures permissions, and connects to the Geniable cloud service.

## IMPORTANT: Re-initialization Handling

If the project is already initialized (config exists, auth valid, services validated), you MUST still:
1. Verify ALL skills and agents are installed (Step 6) — install any missing ones
2. Show the Final Report (Step 9) with the complete list
3. **ALWAYS execute Step 10** — trigger `/instrument-tracing` regardless of init state

Do NOT skip Steps 6, 9, or 10 when re-running on an already-configured project.

## Prerequisites

Ensure geniable is installed:
```bash
pip install geniable
```

## Workflow

### Step 1: Check Installation

First, verify geniable is installed and check the version:

```bash
geni --version
```

If this fails, inform the user to install geniable first:
```
Geniable is not installed. Please run: pip install geniable
```

### Step 2: Authentication

Check if the user is already logged in:

```bash
geni login --check
```

If not logged in, guide them through authentication:

```bash
geni login
```

This will open a browser for AWS Cognito authentication. Wait for the user to complete login.

### Step 3: Collect Configuration

Ask the user for the required configuration using the AskUserQuestion tool:

**LangSmith Configuration:**
1. LangSmith API Key (starts with `ls`)
2. LangSmith Project Name (default: "default")
3. Annotation Queue Name (default: "quality-review")

**Issue Tracker Selection:**
- Jira
- Notion
- None (reports only)

**If Jira selected:**
1. Jira Base URL (e.g., https://company.atlassian.net)
2. Jira Email
3. Jira API Token
4. Jira Project Key (e.g., PROJ)
5. Default Issue Type (Bug/Task/Story/Improvement)

**If Notion selected:**
1. Notion API Key (starts with `secret_`)
2. Notion Database ID

### Step 4: Create Configuration File

Create `~/.geniable.yaml` with the collected configuration:

```yaml
langsmith:
  api_key: "<LANGSMITH_API_KEY>"
  project: "<PROJECT_NAME>"
  queue: "<QUEUE_NAME>"

aws:
  region: "ap-southeast-2"
  integration_endpoint: "https://qdu9vpxw26.execute-api.ap-southeast-2.amazonaws.com/dev"
  evaluation_endpoint: "https://qdu9vpxw26.execute-api.ap-southeast-2.amazonaws.com/dev"

provider: "<jira|notion|none>"

# If Jira:
jira:
  base_url: "<JIRA_URL>"
  email: "<EMAIL>"
  api_token: "<TOKEN>"
  project_key: "<KEY>"
  issue_type: "<TYPE>"

# If Notion:
notion:
  api_key: "<API_KEY>"
  database_id: "<DB_ID>"

defaults:
  report_dir: "./reports"
  log_level: "INFO"
```

### Step 5: Sync to Cloud

Run the cloud sync to store credentials securely:

```bash
geni configure --sync-secrets
```

This uploads the configuration to the Geniable cloud service (per-user storage in AWS).

### Step 6: Install Agent and Skills

Create the `.claude/` directory structure in the project:

```bash
mkdir -p .claude/agents .claude/commands
```

Install agents and skills using the geniable CLI:

```bash
geni init --install-skills
```

If the above command is not available, manually copy the files:

**Agents** (copy to `.claude/agents/`):
- `Geni Analyzer.md` — thread fetching, quality analysis, issue ticket creation
- `Issue Resolver.md` — browse and resolve Jira/Notion issues

**Skills** (copy to `.claude/commands/`):
- `analyze-latest.md` — analyze LangSmith threads for quality issues
- `issues.md` — browse and resolve issue tickets
- `instrument-tracing.md` — add LangSmith tracing to project agents

Verify all 5 files are present. If any are missing, copy them from the geniable package (`cli/skills/` and `cli/agents/`).

### Step 7: Configure Permissions

Update `.claude/settings.local.json` to add geni command permissions:

```json
{
  "permissions": {
    "allow": [
      "Bash(geni:*)",
      "Bash(geni analyze:*)",
      "Bash(geni analyze fetch:*)",
      "Bash(geni analyze mark-done:*)",
      "Bash(geni ticket:*)",
      "Bash(geni ticket create:*)",
      "Bash(geni issues:*)",
      "Bash(geni issues list:*)",
      "Bash(geni issues resolve:*)",
      "Bash(geni issues mark-done:*)"
    ]
  }
}
```

If the file already exists, merge the permissions into the existing `permissions.allow` array.

### Step 8: Validate Services

Optionally test the configuration:

```bash
geni configure --validate
```

This tests:
- LangSmith API connectivity
- AWS service connectivity
- Jira/Notion integration (if configured)

### Step 9: Final Report

Display a summary:

```markdown
## Geniable Initialized Successfully

**Configuration**:
- LangSmith Project: {project}
- Annotation Queue: {queue}
- Issue Tracker: {provider}

**Installed**:
- Agent: .claude/agents/Geni Analyzer.md
- Agent: .claude/agents/Issue Resolver.md
- Skill: .claude/commands/analyze-latest.md
- Skill: .claude/commands/issues.md
- Skill: .claude/commands/instrument-tracing.md
- Permissions: .claude/settings.local.json

**Next Steps**:
1. Restart Claude Code to load the new commands
2. Run `/instrument-tracing` to add LangSmith tracing to your agents
3. Run `/analyze-latest` to analyze your LangSmith threads
4. Run `/issues` to browse and resolve Jira issues
5. Or ask: "Analyze my LangSmith threads for quality issues"

**Useful Commands**:
- `geni login` - Re-authenticate
- `geni configure --show` - View current config
- `geni configure --validate` - Test connections
- `geni analyze fetch` - Fetch threads manually
- `geni issues list` - Browse open Jira issues
```

### Step 10: Tracing Instrumentation (MANDATORY — never skip this step)

This step MUST be executed every time `/geni-init` runs, even if the project is already initialized.

Trigger `/instrument-tracing`. This will:
- Verify all skills and agents are installed (installs any missing ones)
- Scan the project for LLM-calling code
- If tracing is already set up, report "All Good" and exit quickly
- If tracing is missing, guide the user through collaborative instrumentation

## Error Handling

- If `geni login` fails: Check internet connection and try again
- If cloud sync fails: Verify authentication with `geni login`
- If validation fails: Double-check credentials and URLs
- If permission errors: Ensure you have write access to `.claude/` directory

## Notes

- Credentials are stored securely in AWS Secrets Manager (per-user)
- Configuration is synced to DynamoDB for cloud service access
- The agent runs with pre-approved permissions for `geni` commands
- Restart Claude Code after initialization to load new commands
