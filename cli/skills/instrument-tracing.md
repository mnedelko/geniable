# /instrument-tracing

Verify that Geniable skills, agents, and LangSmith tracing are properly set up in this project. Installs missing components, scans for LLM-calling code, and collaboratively adds `@traceable` instrumentation so conversation traces flow to LangSmith for analysis.

**This skill is the single prerequisite gate for all Geniable commands.** It is triggered automatically by `/geni-init`, `/analyze-latest`, and `/issues`. It is safe to re-run — already-installed skills and already-instrumented files are detected and skipped.

## Prerequisites

- Geniable installed (`pip install geniable`)
- LangSmith account with API key

## Workflow

### Step 0: Verify Skills and Agents Are Installed

Check that all required Geniable files exist in the project:

**Agents** (in `.claude/agents/`):
- `Geni Analyzer.md`
- `Issue Resolver.md`

**Skills** (in `.claude/commands/`):
- `analyze-latest.md`
- `issues.md`
- `instrument-tracing.md`

If any are missing, install them:

```bash
geni init --install-skills
```

If that command is not available, copy the missing files from the geniable package (`cli/skills/` and `cli/agents/`). Use Glob to locate the package:

```
Glob: **/site-packages/cli/skills/*.md
Glob: **/site-packages/cli/agents/*.md
```

Report what was installed (or "All skills and agents already installed" if nothing was missing).

### Step 1: Check LangSmith Configuration

Read `~/.geniable.yaml` and extract the LangSmith config:

```yaml
langsmith:
  api_key: "ls__..."
  project: "..."
```

If the file doesn't exist or `langsmith.api_key` is missing, ask the user:

1. **LangSmith API Key** (starts with `ls`)
2. **LangSmith Project Name** (default: `"default"`)

Store the values for use in later steps. Do NOT write to `~/.geniable.yaml` here — that's `/geni-init`'s job.

### Step 2: Discover LLM-Calling Code

Search the project for files that call LLM providers or agent frameworks. Run these searches **in parallel** using Grep and Glob:

| Framework | Grep Pattern | File Glob |
|-----------|-------------|-----------|
| LangGraph | `from langgraph\|import langgraph\|StateGraph` | `**/*.py` |
| LangChain | `from langchain\|import langchain\|ChatModel\|LLMChain` | `**/*.py` |
| Strands | `from strands\|import strands\|strands.Agent` | `**/*.py` |
| Pi Framework | `invoke_model\|create_agent_config\|register_tool\|TOOL_REGISTRY` | `**/*.py` |
| OpenAI SDK | `from openai\|import openai\|OpenAI()` | `**/*.py` |
| Anthropic SDK | `from anthropic\|import anthropic\|Anthropic()` | `**/*.py` |
| Boto3 Bedrock | `bedrock-runtime\|invoke_model\|\.converse\(` | `**/*.py` |
| Google AI | `from google.generativeai\|from google import genai` | `**/*.py` |
| LiteLLM | `from litellm\|import litellm` | `**/*.py` |
| Ollama | `import ollama\|from ollama` | `**/*.py` |

Also search for **Jupyter notebooks** (`**/*.ipynb`) containing any of the above patterns.

Also search for **already-instrumented** files:
- `@traceable` decorator
- `LANGCHAIN_TRACING_V2`
- `from langsmith` / `import langsmith`

**Exclusions**: Skip `venv/`, `node_modules/`, `.git/`, `__pycache__/`, `dist/`, `build/`, `.tox/`, `.eggs/`.

### Step 3: Classify Discoveries

For each discovered file, read it and classify into one of:

| Classification | Criteria |
|---------------|----------|
| `agent-entrypoint` | Contains a main agent function, `run_agent()`, `main()`, or graph compilation (`app = graph.compile()`) |
| `chain-definition` | Defines LangChain chains, pipelines, or tool registrations |
| `raw-llm-call` | Directly calls an LLM SDK (OpenAI, Anthropic, Bedrock, etc.) without a framework |
| `notebook` | Jupyter notebook (`.ipynb`) with LLM calls |
| `already-instrumented` | Already has `@traceable` or `LANGCHAIN_TRACING_V2` setup |

Files classified as `already-instrumented` are noted but **skipped** for instrumentation.

#### Fast Exit: All Instrumented

If **all** discovered files are classified as `already-instrumented` (or no LLM-calling code is found), report the status and exit:

```markdown
## Tracing Status: All Good

All LLM-calling code in this project is already instrumented with LangSmith tracing.
No changes needed. Proceeding with the original command.
```

**Do not prompt the user** — just report and return so the calling skill can continue.

### Step 4: Present Discovery Report

Display a discovery report table to the user:

```markdown
## Discovery Report

| # | File | Framework | Classification | Action |
|---|------|-----------|---------------|--------|
| 1 | src/agent.py | LangGraph | agent-entrypoint | Add @traceable |
| 2 | src/tools.py | OpenAI SDK | raw-llm-call | Add @traceable |
| 3 | src/chain.py | LangChain | chain-definition | Add env setup |
| 4 | notebooks/eval.ipynb | Anthropic SDK | notebook | Add setup cell |
| 5 | src/main.py | LangGraph | already-instrumented | Skip |
```

Then ask the user using AskUserQuestion:

**"Which files should I instrument?"**
- All candidates (Recommended)
- Let me pick specific files
- None — just show me the plan

If "Let me pick" → ask which file numbers to include.

### Step 5: Ask Tracing Toggle Preference

Ask the user using AskUserQuestion:

**"How would you like to enable/disable tracing?"**

| Option | Description |
|--------|-------------|
| Environment variable (Recommended) | Set `LANGCHAIN_TRACING_V2=true` to enable, `false` to disable |
| .env file | Add toggle to project's `.env` file |
| Skip toggle setup | I'll handle this myself |

### Step 6: Generate Instrumentation Plan

For each selected file, generate a **before/after plan** showing exact changes. Display as a table:

```markdown
## Instrumentation Plan

### src/agent.py (LangGraph, agent-entrypoint)

**Changes:**
1. Add import: `from langsmith import traceable`
2. Add `@traceable(name="run_agent")` to `run_agent()` function
3. Inner LangGraph calls auto-traced via `LANGCHAIN_TRACING_V2=true`

### src/tools.py (OpenAI SDK, raw-llm-call)

**Changes:**
1. Add conditional import:
   ```python
   try:
       from langsmith import traceable
   except ImportError:
       def traceable(**kwargs):
           def decorator(func):
               return func
           return decorator
   ```
2. Add `@traceable(name="call_openai")` to `call_openai()` function
```

**Framework-specific instrumentation patterns:**

#### LangChain / LangGraph
- Add `@traceable` on the **entry point function only**
- Inner calls are auto-traced when `LANGCHAIN_TRACING_V2=true`
- Import: `from langsmith import traceable`

#### Raw SDK (OpenAI, Anthropic, Boto3 Bedrock, Google AI, LiteLLM, Ollama)
- Add **conditional import** with graceful fallback (so tracing is optional):
  ```python
  try:
      from langsmith import traceable
  except ImportError:
      def traceable(**kwargs):
          def decorator(func):
              return func
          return decorator
  ```
- Add `@traceable(name="<function_name>")` on each LLM-calling function

#### Strands
- Add `@traceable` on the `run_agent()` entry point
- Import: `from langsmith import traceable`

#### Pi Framework
- Add `@traceable` on `run_agent()` entry point
- Add `@traceable` on `invoke_model()` — this wraps all provider calls (`_invoke_bedrock`, `_invoke_openai`, `_invoke_google`, `_invoke_ollama`) through Pi's provider abstraction layer
- Import: `from langsmith import traceable`

#### Jupyter Notebooks
- Add a **tracing setup cell** at the top of the notebook:
  ```python
  # LangSmith Tracing Setup
  import os
  os.environ["LANGCHAIN_TRACING_V2"] = "true"
  os.environ["LANGCHAIN_API_KEY"] = "<api_key>"  # or load from ~/.geniable.yaml
  os.environ["LANGCHAIN_PROJECT"] = "<project_name>"
  ```

#### Toggle Setup (if environment variable chosen)
- If `.env` file exists: add `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`
- If no `.env`: create a shell snippet the user can source

Ask user for approval before executing:

**"Ready to apply the instrumentation plan above?"**
- Yes, apply all changes
- Let me review each file individually
- Cancel

### Step 7: Execute Instrumentation Plan

After approval, apply the changes:

1. **Add imports** — use the Edit tool to insert import statements at the top of each file (after existing imports)
2. **Add decorators** — use the Edit tool to add `@traceable(name="...")` above target functions
3. **Add dependencies** — check if `langsmith` is in `requirements.txt` / `pyproject.toml` / `setup.py`. If not, inform the user:
   ```
   langsmith is not in your dependencies. Add it with:
   pip install langsmith
   ```
4. **Toggle setup** — based on Step 5 choice:
   - **Environment variable**: show the export commands
   - **.env file**: add/update the `.env` file with tracing variables
5. **Notebooks** — use NotebookEdit to insert the tracing setup cell at the top

### Step 8: Verify Changes

For each modified file, run verification:

1. **Syntax check**: `python -c "import ast; ast.parse(open('<file>').read())"`
2. **Import check**: `python -c "import importlib.util; spec = importlib.util.find_spec('langsmith'); print('langsmith available' if spec else 'langsmith NOT installed')"`
3. **Lint** (if ruff/flake8 available): `ruff check <file>` or `flake8 <file>`

Report any issues and offer to fix them.

### Step 9: Final Report

Display a summary of all changes:

```markdown
## Tracing Instrumentation Complete

**Files Modified**: {count}
| File | Framework | Changes |
|------|-----------|---------|
| src/agent.py | LangGraph | Added @traceable to run_agent() |
| src/tools.py | OpenAI SDK | Added conditional import + @traceable |

**Dependencies**:
- langsmith: {installed | needs install}

**Enable Tracing**:
```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=<your-key>
export LANGCHAIN_PROJECT=<your-project>
```

**Disable Tracing**:
```bash
export LANGCHAIN_TRACING_V2=false
```

**Next Steps**:
1. Install langsmith if needed: `pip install langsmith`
2. Set the environment variables above (or add to `.env`)
3. Run your agent — traces will appear in LangSmith
4. Run `/analyze-latest` to analyze traces with Geniable
```

## Error Handling

- If no LLM-calling code found: inform user and suggest checking file paths
- If `langsmith` not installed: show install command, continue with instrumentation
- If a file can't be parsed: skip it, report the error, continue with remaining files
- If the user cancels at any step: stop gracefully, report what was done so far
- If imports conflict with existing code: flag the conflict and ask the user how to proceed

## Notes

- This skill only uses Claude Code built-in tools (Glob, Grep, Read, Edit, Write, AskUserQuestion, NotebookEdit) — no custom agent required
- Safe to re-run: already-instrumented files are detected and skipped
- The conditional import pattern (`try/except ImportError`) ensures tracing is optional — the code works even if `langsmith` is not installed
- LangChain/LangGraph auto-trace inner calls when `LANGCHAIN_TRACING_V2=true`, so only the entry point needs `@traceable`
