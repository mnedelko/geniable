# /issues

Browse and resolve open issues from your Jira project using the Issue Resolver agent.

## Usage

```
/issues
```

## Behavior

This command lists open Jira issues from your configured project and lets you pick one to resolve interactively with the Issue Resolver agent.

### Step 1: List Open Issues

Fetch and display open issues:

```bash
geni issues list
```

This shows an interactive list of open issues sorted by priority. The user selects one to work on.

If `geni issues list` is not available or fails, fetch issues directly:

```bash
geni issues list --limit 25
```

### Step 2: Resolve Selected Issue

Once the user selects an issue (e.g., AIEV-37), work through it using the Issue Resolver agent workflow:

1. **Understand** - Present the issue details and ask how to approach it
2. **Research** (optional) - Search for best practices if the user wants
3. **Explore** - Search the codebase for relevant files using Grep, Glob, and Read
4. **Plan** - Create a numbered implementation plan with specific file changes
5. **Confirm** - Wait for explicit user approval before making changes
6. **Execute** - Implement the approved changes
7. **Verify** - Run tests and linters, summarize changes
8. **Close** - Ask if the user wants to mark the issue as Done:
   ```bash
   geni issues mark-done <ISSUE-KEY>
   ```

### Alternative: Resolve a Specific Issue

If the user already knows the issue key:

```bash
geni issues resolve <ISSUE-KEY>
```

This fetches the issue details and launches directly into the resolution workflow.

## Prerequisites

- geniable CLI installed and configured (`pip install geniable`)
- Valid geniable authentication (`geni login` + `geni init`)
- Jira provider configured in `~/.geniable.yaml`
- Claude Code restarted after `geni init` (to detect this command)

## Related Commands

- `geni issues list` - List open issues interactively
- `geni issues resolve AIEV-37` - Resolve a specific issue
- `geni issues mark-done AIEV-37` - Mark an issue as Done
- `/analyze-latest` - Analyze LangSmith threads for quality issues
