# /analyze-latest

Analyzes LangSmith annotation queue threads using Claude Code's native intelligence with a seamless, low-interruption workflow.

## Usage

```
/analyze-latest [--limit N]
```

## Options

- `--limit N`: Number of threads to analyze (default: 5)

## Workflow Overview

This skill uses a **subagent architecture** for a smooth user experience:

1. **Subagent** fetches and analyzes threads autonomously (no permission prompts)
2. **Orchestrator** presents results and asks for ticket confirmation
3. **User confirms** which tickets to create
4. **Tickets created** and summary displayed

---

## Step 1: Spawn Analyzer Subagent

Use the Task tool to spawn a subagent with pre-approved permissions for `geni` commands:

```
Task tool parameters:
  subagent_type: "general-purpose"
  allowed_tools: ["Bash(geni *)"]
  description: "Analyze LangSmith threads"
  prompt: |
    You are analyzing LangSmith threads for quality issues. Execute the following steps autonomously.

    ## Step 1: Fetch Threads

    Run this command to fetch unanalyzed threads:
    ```bash
    geni analyze fetch --limit {limit} --output json
    ```

    If no threads are returned, report "No unanalyzed threads found" and exit.

    ## Step 2: Analyze Each Thread

    For each thread, analyze:

    1. **Status & Performance**
       - Duration (flag if >30s)
       - Token usage (flag if >50K)
       - Success/failure status
       - Step timing breakdown

    2. **Quality Issues**
       - Evaluator feedback exposed to users?
       - Implementation details (SQL, etc.) exposed?
       - Response completeness
       - Error handling

    3. **Patterns**
       - Cross-thread patterns
       - Repeated issues
       - Root causes

    ## Step 3: Generate IssueCards

    For each CRITICAL or HIGH severity issue, create an IssueCard JSON:

    ```json
    {
      "title": "Brief, descriptive issue title",
      "priority": "CRITICAL|HIGH",
      "category": "BUG|PERFORMANCE|OPTIMIZATION|QUALITY",
      "status": "BACKLOG",
      "details": "Technical details including metrics, error messages, affected threads",
      "description": "User-facing summary of the issue impact",
      "recommendation": "Specific, actionable fix recommendation",
      "affected_code": {
        "component": "Affected component or step name",
        "suggestion": "Specific improvement suggestion"
      },
      "sources": {
        "thread_id": "thread UUID",
        "thread_name": "thread name",
        "run_id": null,
        "langsmith_url": "https://smith.langchain.com/..."
      },
      "evaluation_results": []
    }
    ```

    ## Step 4: Mark Threads as Analyzed

    After analysis, mark threads as done:
    ```bash
    geni analyze mark-done --thread-ids "id1,id2,id3"
    ```

    ## Step 5: Return Results

    Return a JSON response with this structure:

    ```json
    {
      "threads_analyzed": 5,
      "threads_marked_done": 5,
      "summary": {
        "total_threads": 5,
        "success_rate": 100,
        "avg_duration_seconds": 55.99,
        "total_tokens": 1355775,
        "critical_issues": 2,
        "high_issues": 2,
        "patterns": ["Evaluator feedback exposure", "High token consumption"]
      },
      "issue_cards": [
        { "title": "...", "priority": "CRITICAL", ... },
        { "title": "...", "priority": "HIGH", ... }
      ]
    }
    ```

    Return ONLY the JSON object, no additional text or markdown.
```

Wait for the subagent to complete and return results.

---

## Step 2: Present Results to User

After receiving the subagent's response, present a formatted summary:

```markdown
## Thread Analysis Complete

**Analyzed**: {threads_analyzed} threads
**Success Rate**: {success_rate}%
**Avg Duration**: {avg_duration}s
**Total Tokens**: {total_tokens}

### Issues Found

{For each issue_card, display:}

**{index}. [{priority}] {title}**
- **Category**: {category}
- **Details**: {details (truncated)}
- **Recommendation**: {recommendation}
- **Thread**: [{thread_name}]({langsmith_url})

---

**Create tickets?** (yes / no / select specific: "1,3")
```

---

## Step 3: Handle User Confirmation

Based on user response:

- **"yes"**: Create all tickets
- **"no"**: Skip ticket creation, end workflow
- **"1,2"** or **"1,3,4"**: Create only selected tickets
- **"details 2"**: Show full details of issue #2

---

## Step 4: Create Tickets

For each approved IssueCard, run:

```bash
geni ticket create '<ISSUECARD_JSON>'
```

Capture the ticket ID and URL from the response.

---

## Step 5: Report Results

Display final summary:

```markdown
## Tickets Created

| Ticket | Priority | Title | URL |
|--------|----------|-------|-----|
| PROJ-123 | CRITICAL | Evaluator feedback visible... | [Link](url) |
| PROJ-124 | HIGH | Response latency exceeds... | [Link](url) |

Analysis complete. {N} tickets created in Jira/Notion.
```

---

## Prerequisites

- geniable CLI installed and configured (`pip install geniable`)
- Valid geniable authentication (`geni login` + `geni init`)
- Claude Code restarted after `geni init` (to detect this skill)

## Category Reference

| Category | When to Use |
|----------|-------------|
| BUG | Errors, exceptions, failures, incorrect behavior |
| PERFORMANCE | Slow execution, high latency, timeouts |
| OPTIMIZATION | Token efficiency, cost concerns, resource usage |
| QUALITY | Poor responses, incomplete answers, UX issues |

## Priority Mapping

| Severity | Priority | Description |
|----------|----------|-------------|
| Critical | CRITICAL | Blocks users, data loss, security issue |
| High | HIGH | Significant impact, needs prompt fix |
| Medium | MEDIUM | Moderate impact, can be scheduled |
| Low | LOW | Minor issue, nice-to-have fix |

## Tips

1. Review the issue details before confirming ticket creation
2. Use "select" option to create only the most important tickets
3. Run periodically to catch new issues in your annotation queue
