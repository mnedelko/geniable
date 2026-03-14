# /instrument-tracing

Verify that Geniable skills, agents, and tracing are properly set up in this project. Installs missing components, scans for LLM-calling code, and collaboratively adds tracing instrumentation so conversation traces flow to your chosen provider (LangSmith or Langfuse) for analysis.

**This skill is the single prerequisite gate for all Geniable commands.** It is triggered automatically by `/geni-init`, `/analyze-latest`, and `/issues`. It is safe to re-run — already-installed skills and already-instrumented files are detected and skipped.

## Prerequisites

- Geniable installed (`pip install geniable`)
- A tracing account: [LangSmith](https://smith.langchain.com) or [Langfuse](https://cloud.langfuse.com)

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

### Step 1: Check Tracing Configuration

Read `~/.geniable.yaml` and determine the tracing provider:

```yaml
trace_source: "langsmith"  # or "langfuse"

langsmith:
  api_key: "ls__..."
  project: "..."

# langfuse:
#   public_key: "pk-lf-..."
#   secret_key: "sk-lf-..."
#   host: "https://cloud.langfuse.com"
#   dataset: "annotations"
```

If the file doesn't exist or tracing is not configured, ask the user:

1. **Which tracing provider?** (LangSmith / Langfuse)
2. If **LangSmith**: ask for API Key (starts with `ls`) and Project Name (default: `"default"`)
3. If **Langfuse**: ask for Public Key (starts with `pk-lf`), Secret Key (starts with `sk-lf`), Host (default: `https://cloud.langfuse.com`)

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

Also search for **already-instrumented** files (both providers):
- LangSmith: `@traceable`, `LANGCHAIN_TRACING_V2`, `from langsmith` / `import langsmith`
- Langfuse: `@observe`, `from langfuse`, `CallbackHandler` from langfuse

**Exclusions**: Skip `venv/`, `node_modules/`, `.git/`, `__pycache__/`, `dist/`, `build/`, `.tox/`, `.eggs/`.

### Step 3: Classify Discoveries

For each discovered file, read it and classify into one of:

| Classification | Criteria |
|---------------|----------|
| `agent-entrypoint` | Contains a main agent function, `run_agent()`, `main()`, or graph compilation (`app = graph.compile()`) |
| `chain-definition` | Defines LangChain chains, pipelines, or tool registrations |
| `raw-llm-call` | Directly calls an LLM SDK (OpenAI, Anthropic, Bedrock, etc.) without a framework |
| `notebook` | Jupyter notebook (`.ipynb`) with LLM calls |
| `already-instrumented` | Already has `@traceable`/`@observe` or tracing env var setup |

Files classified as `already-instrumented` are noted but **skipped** for instrumentation.

#### Fast Exit: All Instrumented

If **all** discovered files are classified as `already-instrumented` (or no LLM-calling code is found), report the status and exit:

```markdown
## Tracing Status: All Good

All LLM-calling code in this project is already instrumented with tracing.
No changes needed. Proceeding with the original command.
```

**Do not prompt the user** — just report and return so the calling skill can continue.

### Step 4: Present Discovery Report

Display a discovery report table to the user:

```markdown
## Discovery Report

| # | File | Framework | Classification | Action |
|---|------|-----------|---------------|--------|
| 1 | src/agent.py | LangGraph | agent-entrypoint | Add tracing decorator |
| 2 | src/tools.py | OpenAI SDK | raw-llm-call | Add tracing decorator |
| 3 | src/chain.py | LangChain | chain-definition | Add env/callback setup |
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

**LangSmith options:**

| Option | Description |
|--------|-------------|
| Environment variable (Recommended) | Set `LANGCHAIN_TRACING_V2=true` to enable, `false` to disable |
| .env file | Add toggle to project's `.env` file |
| Skip toggle setup | I'll handle this myself |

**Langfuse options:**

| Option | Description |
|--------|-------------|
| .env file (Recommended) | Add keys to `.env`, load with `python-dotenv` and `--dev` flag |
| Environment variable | Export `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` directly |
| Skip toggle setup | I'll handle this myself |

### Step 6: Generate Instrumentation Plan

For each selected file, generate a **before/after plan** showing exact changes.

**Framework-specific instrumentation patterns by provider:**

#### LangSmith

##### LangChain / LangGraph
- Add `@traceable` on the **entry point function only**
- Inner calls are auto-traced when `LANGCHAIN_TRACING_V2=true`
- Import: `from langsmith import traceable`

##### Raw SDK (OpenAI, Anthropic, Boto3 Bedrock, Google AI, LiteLLM, Ollama)
- Add **conditional import** with graceful fallback:
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

##### Strands / Pi Framework
- Add `@traceable` on entry points (`run_agent()`, `invoke_model()`)
- Import: `from langsmith import traceable`

##### Jupyter Notebooks
- Add a **tracing setup cell** at the top:
  ```python
  # LangSmith Tracing Setup
  import os
  os.environ["LANGCHAIN_TRACING_V2"] = "true"
  os.environ["LANGCHAIN_API_KEY"] = "<api_key>"
  os.environ["LANGCHAIN_PROJECT"] = "<project_name>"
  ```

#### Langfuse

##### LangChain / LangGraph
- Add `@observe` on the **entry point function only**
- For inner LangChain call visibility, add `CallbackHandler`:
  ```python
  from langfuse.callback import CallbackHandler
  langfuse_handler = CallbackHandler()
  # Pass to chain: chain.invoke(input, config={"callbacks": [langfuse_handler]})
  ```
- Import: `from langfuse.decorators import observe`

##### Raw SDK (OpenAI, Anthropic, Boto3 Bedrock, Google AI, LiteLLM, Ollama)
- Add **conditional import** with graceful fallback:
  ```python
  try:
      from langfuse.decorators import observe
  except ImportError:
      def observe(**kwargs):
          def decorator(func):
              return func
          return decorator
  ```
- Add `@observe(name="<function_name>")` on each LLM-calling function

##### Strands / Pi Framework
- Add `@observe` on entry points (`run_agent()`, `invoke_model()`)
- Import: `from langfuse.decorators import observe`

##### Jupyter Notebooks
- Add a **tracing setup cell** at the top:
  ```python
  # Langfuse Tracing Setup
  import os
  os.environ["LANGFUSE_PUBLIC_KEY"] = "<public_key>"
  os.environ["LANGFUSE_SECRET_KEY"] = "<secret_key>"
  os.environ["LANGFUSE_HOST"] = "https://cloud.langfuse.com"  # or self-hosted URL
  ```

#### Toggle Setup
- **LangSmith + Environment variable**: `LANGCHAIN_TRACING_V2=true/false`
- **LangSmith + .env file**: add `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`
- **Langfuse + .env file**: add `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`
- **Langfuse + Environment variable**: export keys directly

Ask user for approval before executing:

**"Ready to apply the instrumentation plan above?"**
- Yes, apply all changes
- Let me review each file individually
- Cancel

### Step 7: Execute Instrumentation Plan

After approval, apply the changes:

1. **Add imports** — use the Edit tool to insert import statements at the top of each file (after existing imports)
2. **Add decorators** — use the Edit tool to add the tracing decorator above target functions
3. **Add dependencies** — check if the tracing SDK is in `requirements.txt` / `pyproject.toml` / `setup.py`. If not, inform the user:
   - LangSmith: `pip install langsmith`
   - Langfuse: `pip install langfuse python-dotenv`
4. **Toggle setup** — based on Step 5 choice:
   - **Environment variable**: show the export commands
   - **.env file**: add/update the `.env` file with tracing variables
5. **Notebooks** — use NotebookEdit to insert the tracing setup cell at the top
6. **LangGraph + Langfuse**: add `CallbackHandler` setup for inner chain visibility

### Step 8: Verify Changes

For each modified file, run verification:

1. **Syntax check**: `python -c "import ast; ast.parse(open('<file>').read())"`
2. **Import check**: verify the tracing SDK is importable
   - LangSmith: `python -c "import importlib.util; spec = importlib.util.find_spec('langsmith'); print('langsmith available' if spec else 'langsmith NOT installed')"`
   - Langfuse: `python -c "import importlib.util; spec = importlib.util.find_spec('langfuse'); print('langfuse available' if spec else 'langfuse NOT installed')"`
3. **Lint** (if ruff/flake8 available): `ruff check <file>` or `flake8 <file>`

Report any issues and offer to fix them.

### Step 9: Final Report

Display a summary of all changes:

**For LangSmith:**
```markdown
## Tracing Instrumentation Complete

**Provider**: LangSmith
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
```

**For Langfuse:**
```markdown
## Tracing Instrumentation Complete

**Provider**: Langfuse
**Files Modified**: {count}
| File | Framework | Changes |
|------|-----------|---------|
| src/agent.py | LangGraph | Added @observe + CallbackHandler |
| src/tools.py | OpenAI SDK | Added conditional import + @observe |

**Dependencies**:
- langfuse: {installed | needs install}
- python-dotenv: {installed | needs install}

**Enable Tracing** (add to `.env`):
```bash
LANGFUSE_PUBLIC_KEY=pk-lf-your-key
LANGFUSE_SECRET_KEY=sk-lf-your-key
LANGFUSE_HOST=https://cloud.langfuse.com
```

**Run with tracing**:
```bash
python agent.py --dev "your query"  # --dev loads .env keys
```
```

**Next Steps**:
1. Install tracing SDK if needed
2. Set the environment variables / `.env` file
3. Run your agent — traces will appear in your tracing dashboard
4. Run `/analyze-latest` to analyze traces with Geniable

## Error Handling

- If no LLM-calling code found: inform user and suggest checking file paths
- If tracing SDK not installed: show install command, continue with instrumentation
- If a file can't be parsed: skip it, report the error, continue with remaining files
- If the user cancels at any step: stop gracefully, report what was done so far
- If imports conflict with existing code: flag the conflict and ask the user how to proceed

## Notes

- This skill only uses Claude Code built-in tools (Glob, Grep, Read, Edit, Write, AskUserQuestion, NotebookEdit) — no custom agent required
- Safe to re-run: already-instrumented files are detected and skipped (both LangSmith and Langfuse patterns)
- The conditional import pattern (`try/except ImportError`) ensures tracing is optional — the code works even if the tracing SDK is not installed
- LangChain/LangGraph + LangSmith auto-trace inner calls when `LANGCHAIN_TRACING_V2=true`, so only the entry point needs `@traceable`
- LangChain/LangGraph + Langfuse needs `CallbackHandler` passed to chain invocations for inner call visibility
