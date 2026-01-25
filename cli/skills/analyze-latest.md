# /analyze-latest

Analyzes LangSmith annotation queue threads using the Geni Analyzer agent.

## Usage

```
/analyze-latest
```

## Behavior

This command invokes the `Geni Analyzer` agent which:

1. Fetches unanalyzed threads from your LangSmith annotation queue
2. Analyzes each thread for quality issues (performance, bugs, exposed internals)
3. Presents findings and asks for ticket creation confirmation
4. Creates tickets in Jira/Notion for approved issues

The agent runs with pre-approved permissions for `geni` commands, so you won't see permission prompts during analysis.

## Visual Indicator

When running, you'll see:
```
● Geni Analyzer(Analyzing threads)
```

The agent name appears in cyan to indicate an active Geni analysis session.

## Prerequisites

- geniable CLI installed and configured (`pip install geniable`)
- Valid geniable authentication (`geni login` + `geni init`)
- Claude Code restarted after `geni init` (to detect this agent)

## Related Commands

- `geni analyze fetch` - Fetch threads directly (used by agent)
- `geni analyze mark-done` - Mark threads as analyzed (used by agent)
- `geni ticket create` - Create tickets (used by agent)
