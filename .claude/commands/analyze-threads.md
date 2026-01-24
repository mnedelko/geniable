# /analyze-threads

Analyzes LangSmith annotation queue threads using Claude Code's native intelligence.

## Usage

```
/analyze-threads [--limit N] [--thread-id ID] [--inline]
```

## Options

- `--limit N`: Number of threads to analyze (default: 5)
- `--thread-id ID`: Analyze a specific thread by ID
- `--inline`: Force inline analysis even for large batches (>3 threads)

## Workflow

This skill uses a **hybrid approach**:
- **Inline analysis** for single threads or small batches (<=3) - interactive, allows follow-ups
- **Parallel subagents** for larger batches (>3) - efficient, returns consolidated summary

### Step 1: Fetch Thread Data

Run the geni CLI to fetch thread data:

```bash
geni fetch --limit {limit} --output json
```

If a specific thread ID is provided:
```bash
geni fetch --thread-id {thread_id} --output json
```

### Step 2: Determine Analysis Mode

Check the thread count from the fetched data:
- If thread count <= 3 OR --inline flag is set: Use **Inline Analysis**
- If thread count > 3 (and no --inline flag): Use **Parallel Subagent Analysis**

### Step 3a: Inline Analysis (<=3 threads or --inline)

For each thread, analyze in the main conversation context:

1. **Status & Performance**
   - Duration (flag if >30s)
   - Token usage (flag if >50K)
   - Success/failure status
   - Step timing breakdown

2. **User Query Assessment**
   - Was the query clear and specific?
   - Query complexity (simple/moderate/complex)
   - Any ambiguities that may have affected response?

3. **Response Quality**
   - Based on annotation score (if available)
   - Human feedback analysis
   - Completeness of response

4. **Error Analysis** (if applicable)
   - Root cause identification
   - Error categorization (timeout, validation, auth, etc.)
   - Impact assessment

5. **Improvement Opportunities**
   - Specific, actionable recommendations
   - Priority ranking (critical/high/medium/low)
   - Affected code areas (if identifiable)

Present findings and await follow-up questions from the user. This mode allows for interactive exploration.

### Step 3b: Parallel Subagent Analysis (>3 threads)

For larger batches, spawn Task agents to analyze threads in parallel:

```
For each thread:
  Use Task tool with:
    subagent_type: "general-purpose"
    description: "Analyzing thread {thread_id[:8]}"
    prompt: |
      Analyze this LangSmith thread and provide a structured analysis.

      ## Thread Data
      {thread_json}

      ## Analysis Required
      Provide a JSON response with:

      {
        "thread_id": "string",
        "summary": {
          "status": "success|failure|timeout|error",
          "duration_seconds": number,
          "token_usage": number,
          "quality_indicator": "good|moderate|poor|unknown"
        },
        "key_observations": [
          "Observation 1",
          "Observation 2"
        ],
        "issues": [
          {
            "severity": "critical|high|medium|low",
            "description": "Issue description",
            "affected_step": "Step name or null"
          }
        ],
        "recommendations": [
          {
            "priority": 1,
            "action": "Specific recommendation",
            "expected_impact": "What improvement this would bring"
          }
        ]
      }

      Focus on actionable insights. Be specific about what went wrong and how to fix it.
      Return ONLY the JSON object, no additional text.
```

Launch all Task agents in a **single message** to enable parallel execution.

Wait for all agents to complete, then aggregate results.

### Step 4: Generate Consolidated Report

After analysis (either inline or parallel), output a formatted report:

```markdown
# Thread Analysis Report

**Analyzed**: {count} threads
**Date**: {current_date}
**Mode**: {inline|parallel}

## Executive Summary

- Total threads: {count}
- Success rate: {percentage}%
- Average duration: {avg}s
- Total tokens used: {total}

## Critical Issues

[List any critical/high severity issues with thread references]

## Cross-Thread Patterns

[Identify patterns that appear across multiple threads]

## Recommendations

### Priority 1 (Critical)
[List critical recommendations]

### Priority 2 (High)
[List high priority recommendations]

### Priority 3 (Medium)
[List medium priority recommendations]

---

## Per-Thread Details

[For each thread, show key findings]
```

## Prerequisites

- geniable CLI installed and configured (`pip install geniable`)
- Valid geniable authentication (`geni login`)
- Active venv if running from project directory

## Examples

### Single Thread Deep-Dive
```
/analyze-threads --thread-id abc123def456
```
Performs detailed inline analysis with opportunity for follow-up questions.

### Small Batch (Interactive)
```
/analyze-threads --limit 3
```
Analyzes 3 threads inline, allowing you to ask clarifying questions.

### Large Batch (Efficient)
```
/analyze-threads --limit 10
```
Spawns parallel subagents for efficient batch processing, returns consolidated report.

### Force Inline for Large Batch
```
/analyze-threads --limit 10 --inline
```
Forces inline analysis even for 10 threads (slower but allows follow-ups).

## Tips

1. Start with `--limit 3` for interactive exploration
2. Use `--thread-id` for deep-diving into specific issues
3. Use larger limits without `--inline` when you need a quick overview
4. After batch analysis, you can `/analyze-threads --thread-id X` to deep-dive
