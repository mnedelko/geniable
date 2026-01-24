"""Report generator for creating markdown analysis reports.

Generates enriched thread analysis reports with AI-powered insights:
- Detailed metadata and conversation traces
- AI-generated key observations and success patterns
- Codebase-aware recommendations using LLM analysis
- Processing summaries with issue breakdowns

The report generator uses an LLM to analyze thread data and generate
contextual insights based on the project's codebase understanding.
"""

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from agent.models.evaluation import EvaluationResponse

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """Protocol for LLM clients used in report generation."""

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate a response from the LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt for context

        Returns:
            Generated text response
        """
        ...


class AnthropicLLMClient:
    """LLM client using Anthropic's Claude API."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        """Initialize the Anthropic client.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model to use for generation
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazy initialization of the Anthropic client."""
        if self._client is None:
            try:
                import anthropic

                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package is required for LLM-based report generation. "
                    "Install with: pip install anthropic"
                )
        return self._client

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate a response using Claude.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt

        Returns:
            Generated text response
        """
        client = self._get_client()

        messages = [{"role": "user", "content": prompt}]

        response = client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=system_prompt
            or "You are an expert software engineer analyzing agent execution traces.",
            messages=messages,
        )

        return response.content[0].text


class ReportGenerator:
    """Generates markdown reports from analysis results.

    Creates enriched reports that leverage LLM understanding of the project's
    codebase to provide context-aware recommendations.

    The generator can operate in two modes:
    1. LLM-powered (--ci): Uses an AI model to generate observations, successes, and recommendations
    2. Deterministic (default): Uses rule-based analysis without LLM

    When use_llm=True (CI mode), the anthropic package must be installed.
    """

    def __init__(
        self,
        output_dir: Path = None,
        project_context: Optional[Dict[str, Any]] = None,
        llm_client: Optional[LLMClient] = None,
        use_llm: bool = False,
    ):
        """Initialize the report generator.

        Args:
            output_dir: Directory for generated reports
            project_context: Context about the project codebase for recommendations
            llm_client: Optional LLM client for AI-powered generation
            use_llm: Whether to use LLM for report generation (default False).
                     When True (--ci flag), requires anthropic package.
        """
        self.output_dir = output_dir or Path("./reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.project_context = project_context or {}
        self.use_llm = use_llm

        # Initialize LLM client if needed
        if use_llm and llm_client is None:
            # Verify anthropic package is available when CI mode is enabled
            try:
                import anthropic  # noqa: F401
            except ImportError:
                raise ImportError(
                    "anthropic package is required for LLM-powered reports (--ci flag). "
                    "Install with: pip install geniable[llm]"
                )

            # Verify API key is available
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY environment variable is required for LLM-powered reports. "
                    "Set the API key or use 'geni analyze-latest --ci' which will prompt for it."
                )

            try:
                self.llm_client = AnthropicLLMClient(api_key=api_key)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize LLM client: {e}")
        else:
            self.llm_client = llm_client

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use in a filename.

        Args:
            name: String to sanitize

        Returns:
            Sanitized string safe for filenames
        """
        # Replace spaces with hyphens
        sanitized = name.replace(" ", "-")
        # Remove any characters that aren't alphanumeric, hyphens, or underscores
        sanitized = re.sub(r"[^a-zA-Z0-9\-_]", "", sanitized)
        # Remove consecutive hyphens
        sanitized = re.sub(r"-+", "-", sanitized)
        # Trim to reasonable length
        return sanitized[:50].strip("-")

    def generate_thread_report(
        self,
        thread: Dict[str, Any],
        eval_result: Optional[EvaluationResponse],
        run_id: str,
    ) -> Path:
        """Generate an individual report for a single thread.

        Args:
            thread: Thread data
            eval_result: Evaluation results for the thread
            run_id: Unique run identifier

        Returns:
            Path to the generated report
        """
        thread_id = thread.get("thread_id", "unknown")
        thread_name = thread.get("name", "Unknown")

        # Create filename: Thread-{Name}-{ShortID}.md
        safe_name = self._sanitize_filename(thread_name)
        short_id = thread_id[:8] if len(thread_id) >= 8 else thread_id
        filename = f"Thread-{safe_name}-{short_id}.md"
        report_path = self.output_dir / filename

        content = self._build_single_thread_content(thread, eval_result, run_id)
        report_path.write_text(content)

        logger.info(f"Thread report generated: {report_path}")
        return report_path

    def update_report_with_tickets(
        self,
        report_path: Path,
        jira_tickets: Optional[List[Dict[str, str]]] = None,
        notion_tickets: Optional[List[Dict[str, str]]] = None,
    ) -> bool:
        """Update an existing report with ticket information.

        Inserts a "Related Tickets" section after the "Processing Summary" section.

        Args:
            report_path: Path to the existing report
            jira_tickets: List of Jira tickets with 'key' and 'url' fields
            notion_tickets: List of Notion pages with 'id' and 'url' fields

        Returns:
            True if report was updated successfully, False otherwise
        """
        if not report_path.exists():
            logger.warning(f"Report not found: {report_path}")
            return False

        if not jira_tickets and not notion_tickets:
            logger.debug("No tickets to add to report")
            return False

        try:
            content = report_path.read_text()

            # Build the Related Tickets section
            tickets_section_lines = [
                "",
                "## Related Tickets",
                "",
            ]

            if jira_tickets:
                for ticket in jira_tickets:
                    key = ticket.get("key", ticket.get("id", "Unknown"))
                    url = ticket.get("url", "")
                    if url:
                        tickets_section_lines.append(f"- **Jira**: [{key}]({url})")
                    else:
                        tickets_section_lines.append(f"- **Jira**: {key}")

            if notion_tickets:
                for ticket in notion_tickets:
                    page_id = ticket.get("id", "Unknown")
                    url = ticket.get("url", "")
                    short_id = page_id[:8] if len(page_id) > 8 else page_id
                    if url:
                        tickets_section_lines.append(f"- **Notion**: [{short_id}]({url})")
                    else:
                        tickets_section_lines.append(f"- **Notion**: {short_id}")

            tickets_section_lines.append("")
            tickets_section = "\n".join(tickets_section_lines)

            # Find the "Processing Summary" section and insert after it
            # Look for the next section header (## or ---) after Processing Summary
            processing_summary_marker = "## Processing Summary"

            if processing_summary_marker in content:
                # Find the end of Processing Summary section
                summary_start = content.find(processing_summary_marker)
                # Find the next section (either ## or ---)
                remaining = content[summary_start + len(processing_summary_marker) :]

                # Find next section header
                next_section_idx = -1
                for marker in ["## ", "---"]:
                    idx = remaining.find(marker)
                    if idx != -1:
                        if next_section_idx == -1 or idx < next_section_idx:
                            next_section_idx = idx

                if next_section_idx != -1:
                    insert_point = summary_start + len(processing_summary_marker) + next_section_idx
                    # Insert the tickets section before the next section
                    updated_content = (
                        content[:insert_point] + tickets_section + content[insert_point:]
                    )
                else:
                    # Append at the end if no next section found
                    updated_content = content + tickets_section
            else:
                # Fallback: append at the end
                updated_content = content + tickets_section

            report_path.write_text(updated_content)
            logger.info(f"Updated report with ticket information: {report_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to update report with tickets: {e}")
            return False

    def _build_single_thread_content(
        self,
        thread: Dict[str, Any],
        eval_result: Optional[EvaluationResponse],
        run_id: str,
    ) -> str:
        """Build enriched markdown content for a single thread report.

        Uses enhanced template with:
        - Detailed metadata
        - Conversation trace
        - Key observations
        - What worked well
        - Codebase-aware recommendations
        - Processing summary
        """
        thread_id = thread.get("thread_id", "unknown")
        thread_name = thread.get("name", "Unknown")
        title = thread_name or f"Thread {thread_id[:8]}"

        # Extract metadata
        start_time = thread.get("start_time", "N/A")
        end_time = thread.get("end_time", "N/A")
        duration_seconds = thread.get("duration_seconds", 0)
        status = thread.get("status", "unknown")
        total_tokens = thread.get("total_tokens", 0)
        prompt_tokens = thread.get("prompt_tokens", 0)
        completion_tokens = thread.get("completion_tokens", 0)
        technique = thread.get("technique", "Unknown")
        user_query = thread.get("user_query", "No query available")
        langsmith_url = thread.get("langsmith_url", "")

        # Build sections
        steps_section = self._build_conversation_trace(thread)
        observations_section = self._build_observations(thread, eval_result)
        successes_section = self._build_successes(thread, eval_result)
        recommendations_section = self._build_codebase_recommendations(thread, eval_result)
        issue_counts = self._count_issues_by_priority(eval_result)

        lines = [
            f"# Thread: {title}",
            "",
            "## Metadata",
            f"- **Thread ID**: `{thread_id}`",
            f"- **Name**: {thread_name}",
        ]

        if langsmith_url:
            lines.append(f"- **LangSmith URL**: [{thread_id[:8]}...]({langsmith_url})")

        lines.extend(
            [
                f"- **Timestamp**: {start_time}",
                f"- **End Time**: {end_time}",
                f"- **Duration**: {duration_seconds:.2f} seconds",
                f"- **Status**: {status}",
                f"- **Total Tokens**: {total_tokens:,}",
                f"- **Prompt Tokens**: {prompt_tokens:,}",
                f"- **Completion Tokens**: {completion_tokens:,}",
                f"- **Technique**: {technique}",
                "",
                "## User Query",
                "```",
                user_query,
                "```",
                "",
                "## Conversation Trace",
                "",
                steps_section,
                "",
                "## Key Observations",
                "",
                observations_section,
                "",
                "## What Worked Well",
                "",
                successes_section,
                "",
                "## Recommendations",
                "",
                recommendations_section,
                "",
                "## Processing Summary",
                "",
                f"- **Thread Processed**: {datetime.now().isoformat()}",
                f"- **Issues Identified**: {issue_counts['total']}",
                f"- **Critical Issues**: {issue_counts['critical']}",
                f"- **High Priority Issues**: {issue_counts['high']}",
                f"- **Medium Priority Issues**: {issue_counts['medium']}",
                f"- **Low Priority Issues**: {issue_counts['low']}",
                "",
            ]
        )

        # Add annotation if present
        if thread.get("annotation_text"):
            annotation_score = thread.get("annotation_score", "N/A")
            lines.extend(
                [
                    "---",
                    "",
                    "## Human Annotation",
                    "",
                    f"**Score**: {annotation_score}",
                    "",
                    f"> {thread['annotation_text']}",
                    "",
                ]
            )

        # Add evaluation details
        if eval_result and eval_result.results:
            lines.extend(
                [
                    "---",
                    "",
                    "## Detailed Evaluation Results",
                    "",
                    "| Evaluation | Status | Score | Details |",
                    "|------------|--------|-------|---------|",
                ]
            )

            for result in eval_result.results:
                status_icon = (
                    "✅" if result.status == "pass" else "⚠️" if result.status == "warning" else "❌"
                )
                message = (result.message or "")[:80]
                lines.append(
                    f"| {result.tool} | {status_icon} {result.status} | {result.score:.2f} | {message} |"
                )
            lines.append("")

        return "\n".join(lines)

    def _build_conversation_trace(self, thread: Dict[str, Any]) -> str:
        """Build the conversation trace section from thread steps.

        Args:
            thread: Thread data containing steps

        Returns:
            Formatted conversation trace as markdown
        """
        steps = thread.get("steps", [])
        if not steps:
            return "_No conversation trace available._"

        lines = []
        for i, step in enumerate(steps, 1):
            step_name = step.get("name", "Unknown Step")
            step_type = step.get("type", "step")
            duration_ms = step.get("duration_ms", 0)
            tokens = step.get("tokens", 0)
            input_text = step.get("input", "")
            output_text = step.get("output", "")
            error = step.get("error")

            # Format step header with timing
            lines.append(f"### Step {i}: {step_name}")
            lines.append(
                f"**Type**: {step_type} | **Duration**: {duration_ms}ms | **Tokens**: {tokens:,}"
            )
            lines.append("")

            # Input if available
            if input_text:
                input_preview = str(input_text)[:500]
                if len(str(input_text)) > 500:
                    input_preview += "..."
                lines.append("**Input:**")
                lines.append(f"```")
                lines.append(input_preview)
                lines.append("```")
                lines.append("")

            # Output if available
            if output_text:
                output_preview = str(output_text)[:500]
                if len(str(output_text)) > 500:
                    output_preview += "..."
                lines.append("**Output:**")
                lines.append(f"```")
                lines.append(output_preview)
                lines.append("```")
                lines.append("")

            # Error if present
            if error:
                lines.append(f"**⚠️ Error:** `{str(error)[:200]}`")
                lines.append("")

        return "\n".join(lines)

    def _build_observations(
        self, thread: Dict[str, Any], eval_result: Optional[EvaluationResponse]
    ) -> str:
        """Build key observations section based on thread analysis.

        Uses LLM when available for intelligent observation generation,
        falls back to deterministic analysis otherwise.

        Args:
            thread: Thread data
            eval_result: Evaluation results

        Returns:
            Formatted observations as markdown bullet points
        """
        if self.use_llm and self.llm_client:
            return self._generate_observations_with_llm(thread, eval_result)

        return self._generate_observations_deterministic(thread, eval_result)

    def _generate_observations_with_llm(
        self, thread: Dict[str, Any], eval_result: Optional[EvaluationResponse]
    ) -> str:
        """Generate observations using the LLM."""
        # Prepare thread summary for the LLM
        thread_summary = self._prepare_thread_summary(thread, eval_result)

        prompt = f"""Analyze this agent execution thread and provide key observations.

## Thread Data
{thread_summary}

## Project Context
{json.dumps(self.project_context, indent=2) if self.project_context else "No additional project context available."}

## Instructions
Provide 3-7 key observations about this thread execution. Focus on:
1. Performance characteristics (latency, efficiency)
2. Token usage patterns
3. Error patterns or anomalies
4. Step execution flow
5. Quality of the agent's reasoning

Format each observation as a bullet point with an emoji indicator:
- ✅ for positive observations
- ⚠️ for warnings or concerns
- ❌ for critical issues
- 📊 for neutral metrics
- 🔍 for insights requiring investigation

Output ONLY the bullet points, no preamble or summary."""

        try:
            response = self.llm_client.generate(
                prompt,
                system_prompt="You are an expert AI/ML engineer analyzing agent execution traces. Provide concise, actionable observations.",
            )
            return response.strip()
        except Exception as e:
            logger.warning(f"LLM observation generation failed: {e}. Using fallback.")
            return self._generate_observations_deterministic(thread, eval_result)

    def _generate_observations_deterministic(
        self, thread: Dict[str, Any], eval_result: Optional[EvaluationResponse]
    ) -> str:
        """Generate observations using deterministic rules (fallback)."""
        observations = []

        # Performance observations
        duration = thread.get("duration_seconds", 0)
        if duration > 30:
            observations.append(
                f"⚠️ **High Latency**: Thread execution took {duration:.1f}s, which exceeds the 30s threshold"
            )
        elif duration > 10:
            observations.append(f"⏱️ **Moderate Latency**: Thread execution took {duration:.1f}s")
        else:
            observations.append(f"✅ **Good Performance**: Thread completed in {duration:.1f}s")

        # Token observations
        total_tokens = thread.get("total_tokens", 0)
        if total_tokens > 50000:
            observations.append(
                f"⚠️ **High Token Usage**: {total_tokens:,} tokens consumed (exceeds 50K limit)"
            )
        elif total_tokens > 25000:
            observations.append(f"📊 **Moderate Token Usage**: {total_tokens:,} tokens consumed")

        # Error observations
        errors = thread.get("errors", [])
        if errors:
            observations.append(
                f"❌ **Errors Detected**: {len(errors)} error(s) occurred during execution"
            )
            for error in errors[:3]:
                observations.append(f"  - `{str(error)[:100]}`")

        # Evaluation observations
        if eval_result and eval_result.results:
            failed = [r for r in eval_result.results if r.status == "fail"]
            warnings = [r for r in eval_result.results if r.status == "warning"]

            if failed:
                observations.append(
                    f"❌ **Failed Evaluations**: {len(failed)} evaluation(s) failed"
                )
                for f in failed[:3]:
                    observations.append(
                        f"  - {f.tool}: {f.message[:80] if f.message else 'No details'}"
                    )

            if warnings:
                observations.append(
                    f"⚠️ **Warnings**: {len(warnings)} evaluation(s) produced warnings"
                )

        # Step analysis
        steps = thread.get("steps", [])
        if steps:
            slowest_steps = sorted(steps, key=lambda s: s.get("duration_ms", 0), reverse=True)[:3]
            if slowest_steps and slowest_steps[0].get("duration_ms", 0) > 5000:
                observations.append("🐢 **Slow Steps Identified**:")
                for step in slowest_steps:
                    if step.get("duration_ms", 0) > 1000:
                        observations.append(
                            f"  - {step.get('name', 'Unknown')}: {step.get('duration_ms', 0)}ms"
                        )

        if not observations:
            observations.append("_No significant observations._")

        return "\n".join(f"- {obs}" if not obs.startswith("  ") else obs for obs in observations)

    def _build_successes(
        self, thread: Dict[str, Any], eval_result: Optional[EvaluationResponse]
    ) -> str:
        """Build the 'What Worked Well' section.

        Uses LLM when available for intelligent success pattern identification,
        falls back to deterministic analysis otherwise.

        Args:
            thread: Thread data
            eval_result: Evaluation results

        Returns:
            Formatted successes as markdown bullet points
        """
        if self.use_llm and self.llm_client:
            return self._generate_successes_with_llm(thread, eval_result)

        return self._generate_successes_deterministic(thread, eval_result)

    def _generate_successes_with_llm(
        self, thread: Dict[str, Any], eval_result: Optional[EvaluationResponse]
    ) -> str:
        """Generate successes using the LLM."""
        thread_summary = self._prepare_thread_summary(thread, eval_result)

        prompt = f"""Analyze this agent execution thread and identify what worked well.

## Thread Data
{thread_summary}

## Project Context
{json.dumps(self.project_context, indent=2) if self.project_context else "No additional project context available."}

## Instructions
Identify 3-6 things that worked well in this thread execution. Focus on:
1. Successful outcomes and achievements
2. Efficient patterns in the execution
3. Good decision-making by the agent
4. Effective use of tools or resources
5. Quality aspects of the response

Be specific and reference actual data from the thread when possible.
Format each success as a bullet point starting with a positive emoji (✅, ⚡, 💡, 🎯, etc.)

Output ONLY the bullet points, no preamble or summary."""

        try:
            response = self.llm_client.generate(
                prompt,
                system_prompt="You are an expert AI/ML engineer analyzing agent execution traces. Focus on identifying positive patterns and successes.",
            )
            return response.strip()
        except Exception as e:
            logger.warning(f"LLM success generation failed: {e}. Using fallback.")
            return self._generate_successes_deterministic(thread, eval_result)

    def _generate_successes_deterministic(
        self, thread: Dict[str, Any], eval_result: Optional[EvaluationResponse]
    ) -> str:
        """Generate successes using deterministic rules (fallback)."""
        successes = []

        # Successful evaluations
        if eval_result and eval_result.results:
            passed = [r for r in eval_result.results if r.status == "pass"]
            for result in passed:
                score_pct = int(result.score * 100)
                successes.append(f"✅ **{result.tool}**: Passed with {score_pct}% score")

        # Good performance
        duration = thread.get("duration_seconds", 0)
        if duration < 5:
            successes.append(f"⚡ **Fast Execution**: Completed in just {duration:.1f}s")

        # Efficient token usage
        total_tokens = thread.get("total_tokens", 0)
        prompt_tokens = thread.get("prompt_tokens", 0)
        completion_tokens = thread.get("completion_tokens", 0)

        if total_tokens > 0 and total_tokens < 10000:
            successes.append(f"💰 **Efficient Token Usage**: Only {total_tokens:,} tokens used")

        if prompt_tokens > 0 and completion_tokens > 0:
            ratio = completion_tokens / prompt_tokens
            if ratio < 0.5:
                successes.append(f"📉 **Good Prompt-to-Completion Ratio**: {ratio:.2f}")

        # No errors
        errors = thread.get("errors", [])
        if not errors:
            successes.append("✅ **Error-Free Execution**: No errors detected during processing")

        # Successful steps
        steps = thread.get("steps", [])
        if steps:
            successful_steps = [s for s in steps if not s.get("error")]
            if len(successful_steps) == len(steps) and len(steps) > 0:
                successes.append(
                    f"✅ **All Steps Succeeded**: {len(steps)} steps completed without errors"
                )

            # Fast steps
            fast_steps = [s for s in steps if s.get("duration_ms", float("inf")) < 500]
            if fast_steps and len(fast_steps) >= len(steps) // 2:
                successes.append(
                    f"⚡ **Efficient Step Execution**: {len(fast_steps)}/{len(steps)} steps completed in <500ms"
                )

        if not successes:
            successes.append(
                "_Analysis in progress - successes will be identified as patterns emerge._"
            )

        return "\n".join(f"- {s}" for s in successes)

    def _build_codebase_recommendations(
        self, thread: Dict[str, Any], eval_result: Optional[EvaluationResponse]
    ) -> str:
        """Build codebase-aware recommendations.

        Uses LLM with project context to generate actionable recommendations
        tied to specific code locations and patterns in the codebase.

        Args:
            thread: Thread data
            eval_result: Evaluation results

        Returns:
            Formatted recommendations as markdown
        """
        if self.use_llm and self.llm_client:
            return self._generate_recommendations_with_llm(thread, eval_result)

        return self._generate_recommendations_deterministic(thread, eval_result)

    def _generate_recommendations_with_llm(
        self, thread: Dict[str, Any], eval_result: Optional[EvaluationResponse]
    ) -> str:
        """Generate codebase-aware recommendations using the LLM."""
        thread_summary = self._prepare_thread_summary(thread, eval_result)

        prompt = f"""Analyze this agent execution thread and provide actionable recommendations.

## Thread Data
{thread_summary}

## Project Context
{json.dumps(self.project_context, indent=2) if self.project_context else "No additional project context available."}

## Instructions
Provide 3-8 specific, actionable recommendations to improve this agent's performance and reliability.

For each recommendation:
1. Assign a priority level: 🔴 Critical, 🟠 High, 🟡 Medium, or 🟢 Low
2. Give it a clear title
3. Explain the issue and why it matters
4. List 2-4 specific actions to address it
5. If possible, reference specific code areas or components that need attention

Focus on:
- Performance bottlenecks and optimization opportunities
- Error handling and reliability improvements
- Token efficiency and cost reduction
- Code quality and maintainability
- User experience improvements

Use your understanding of the codebase patterns to make specific, actionable suggestions.
Reference actual step names, error messages, or metrics from the thread data.

Format as:
### [Priority Emoji] [Priority Level]: [Title]

[Description of the issue]

**Recommended Actions:**
1. [Specific action]
2. [Specific action]
...

**Affected Areas:** [If applicable, mention specific components or code areas]

---"""

        try:
            response = self.llm_client.generate(
                prompt,
                system_prompt="""You are a senior software engineer and AI/ML expert reviewing agent execution traces.
Your goal is to provide specific, actionable recommendations that will meaningfully improve the agent's performance,
reliability, and user experience. Base your recommendations on the actual data in the thread, not generic advice.
When you have project context, leverage your understanding of the codebase to make targeted suggestions.""",
            )
            return response.strip()
        except Exception as e:
            logger.warning(f"LLM recommendation generation failed: {e}. Using fallback.")
            return self._generate_recommendations_deterministic(thread, eval_result)

    def _generate_recommendations_deterministic(
        self, thread: Dict[str, Any], eval_result: Optional[EvaluationResponse]
    ) -> str:
        """Generate recommendations using deterministic rules (fallback)."""
        recommendations = []

        # Analyze evaluation failures for recommendations
        if eval_result and eval_result.results:
            for result in eval_result.results:
                if result.status == "fail":
                    rec = self._generate_recommendation_for_failure(result, thread)
                    if rec:
                        recommendations.append(rec)
                elif result.status == "warning":
                    rec = self._generate_recommendation_for_warning(result, thread)
                    if rec:
                        recommendations.append(rec)

        # Performance-based recommendations
        duration = thread.get("duration_seconds", 0)
        if duration > 30:
            recommendations.append(
                {
                    "priority": "🔴 Critical",
                    "title": "Reduce Thread Execution Time",
                    "description": f"Thread took {duration:.1f}s, significantly impacting user experience.",
                    "actions": [
                        "Profile slow steps to identify bottlenecks",
                        "Consider implementing caching for repeated operations",
                        "Review database queries for N+1 patterns",
                        "Evaluate if parallel execution is possible for independent steps",
                    ],
                    "affected_code": self._identify_slow_code_areas(thread),
                }
            )

        # Token-based recommendations
        total_tokens = thread.get("total_tokens", 0)
        if total_tokens > 50000:
            recommendations.append(
                {
                    "priority": "🟠 High",
                    "title": "Optimize Token Consumption",
                    "description": f"Thread consumed {total_tokens:,} tokens, exceeding the 50K limit.",
                    "actions": [
                        "Review prompt templates for unnecessary verbosity",
                        "Implement context window management",
                        "Consider summarization for long conversation histories",
                        "Use more concise system prompts",
                    ],
                    "affected_code": self._identify_token_heavy_areas(thread),
                }
            )

        # Error-based recommendations
        errors = thread.get("errors", [])
        if errors:
            error_types = self._categorize_errors(errors)
            for error_type, error_list in error_types.items():
                recommendations.append(
                    {
                        "priority": (
                            "🔴 Critical" if "exception" in error_type.lower() else "🟠 High"
                        ),
                        "title": f"Address {error_type} Errors",
                        "description": f"{len(error_list)} {error_type} error(s) detected.",
                        "actions": self._get_error_remediation_actions(error_type),
                        "affected_code": self._identify_error_source(errors),
                    }
                )

        # Step-specific recommendations
        steps = thread.get("steps", [])
        slow_steps = [s for s in steps if s.get("duration_ms", 0) > 5000]
        if slow_steps:
            step_names = [s.get("name", "Unknown") for s in slow_steps[:3]]
            recommendations.append(
                {
                    "priority": "🟡 Medium",
                    "title": "Optimize Slow Steps",
                    "description": f"Steps taking >5s: {', '.join(step_names)}",
                    "actions": [
                        (
                            f"Review implementation of '{step_names[0]}' step"
                            if step_names
                            else "Review slow steps"
                        ),
                        "Add performance monitoring/tracing",
                        "Consider async execution where applicable",
                        "Evaluate caching strategies for repeated computations",
                    ],
                    "affected_code": None,
                }
            )

        # Format recommendations
        if not recommendations:
            return "_No specific recommendations at this time. Thread execution appears optimal._"

        lines = []
        for rec in recommendations:
            if isinstance(rec, dict):
                lines.append(f"### {rec['priority']}: {rec['title']}")
                lines.append("")
                lines.append(f"{rec['description']}")
                lines.append("")
                lines.append("**Recommended Actions:**")
                for action in rec.get("actions", []):
                    lines.append(f"1. {action}")
                lines.append("")

                if rec.get("affected_code"):
                    lines.append("**Affected Code:**")
                    lines.append(f"```")
                    lines.append(rec["affected_code"])
                    lines.append("```")
                    lines.append("")
            else:
                lines.append(f"- {rec}")

        return "\n".join(lines)

    def _prepare_thread_summary(
        self, thread: Dict[str, Any], eval_result: Optional[EvaluationResponse]
    ) -> str:
        """Prepare a concise summary of thread data for LLM prompts.

        Args:
            thread: Thread data
            eval_result: Evaluation results

        Returns:
            Formatted string summary of the thread
        """
        summary_parts = []

        # Basic metadata
        summary_parts.append(f"**Thread ID**: {thread.get('thread_id', 'unknown')}")
        summary_parts.append(f"**Name**: {thread.get('name', 'Unknown')}")
        summary_parts.append(f"**Status**: {thread.get('status', 'unknown')}")
        summary_parts.append(f"**Duration**: {thread.get('duration_seconds', 0):.2f}s")
        summary_parts.append(f"**Total Tokens**: {thread.get('total_tokens', 0):,}")
        summary_parts.append(f"**Prompt Tokens**: {thread.get('prompt_tokens', 0):,}")
        summary_parts.append(f"**Completion Tokens**: {thread.get('completion_tokens', 0):,}")
        summary_parts.append("")

        # User query
        if thread.get("user_query"):
            query = thread["user_query"][:500]
            if len(thread["user_query"]) > 500:
                query += "..."
            summary_parts.append(f"**User Query**: {query}")
            summary_parts.append("")

        # Final response preview
        if thread.get("final_response"):
            response = thread["final_response"][:500]
            if len(thread["final_response"]) > 500:
                response += "..."
            summary_parts.append(f"**Final Response Preview**: {response}")
            summary_parts.append("")

        # Steps summary
        steps = thread.get("steps", [])
        if steps:
            summary_parts.append("**Execution Steps**:")
            for i, step in enumerate(steps[:10], 1):
                name = step.get("name", "Unknown")
                duration = step.get("duration_ms", 0)
                tokens = step.get("tokens", 0)
                error = step.get("error")
                error_str = f" [ERROR: {str(error)[:50]}]" if error else ""
                summary_parts.append(f"  {i}. {name} - {duration}ms, {tokens} tokens{error_str}")
            if len(steps) > 10:
                summary_parts.append(f"  ... and {len(steps) - 10} more steps")
            summary_parts.append("")

        # Errors
        errors = thread.get("errors", [])
        if errors:
            summary_parts.append("**Errors**:")
            for error in errors[:5]:
                summary_parts.append(f"  - {str(error)[:100]}")
            if len(errors) > 5:
                summary_parts.append(f"  ... and {len(errors) - 5} more errors")
            summary_parts.append("")

        # Evaluation results
        if eval_result and eval_result.results:
            summary_parts.append("**Evaluation Results**:")
            for result in eval_result.results:
                status_icon = (
                    "✅" if result.status == "pass" else "⚠️" if result.status == "warning" else "❌"
                )
                message = f" - {result.message[:80]}" if result.message else ""
                summary_parts.append(
                    f"  {status_icon} {result.tool}: {result.status} (score: {result.score:.2f}){message}"
                )
            summary_parts.append("")

        return "\n".join(summary_parts)

    def _generate_recommendation_for_failure(
        self, result: Any, thread: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generate a recommendation for a failed evaluation.

        Args:
            result: Failed evaluation result
            thread: Thread data

        Returns:
            Recommendation dictionary or None
        """
        tool = result.tool
        message = result.message or ""

        recommendations_map = {
            "latency_evaluation": {
                "title": "Improve Response Latency",
                "actions": [
                    "Identify and optimize slow database queries",
                    "Implement connection pooling",
                    "Add response caching for frequently requested data",
                    "Consider using streaming responses for large outputs",
                ],
            },
            "token_usage_evaluation": {
                "title": "Reduce Token Consumption",
                "actions": [
                    "Truncate or summarize long context windows",
                    "Use more efficient prompt engineering",
                    "Implement message pruning for conversation history",
                    "Consider using smaller models for simple tasks",
                ],
            },
            "error_detection": {
                "title": "Fix Detected Errors",
                "actions": [
                    "Review error logs for root cause",
                    "Add proper error handling and recovery",
                    "Implement retry logic with exponential backoff",
                    "Add input validation to prevent error conditions",
                ],
            },
            "content_quality_evaluation": {
                "title": "Improve Response Quality",
                "actions": [
                    "Enhance prompt templates with clearer instructions",
                    "Add few-shot examples for complex tasks",
                    "Implement response validation and filtering",
                    "Review and update knowledge base content",
                ],
            },
        }

        if tool in recommendations_map:
            rec = recommendations_map[tool]
            return {
                "priority": "🔴 Critical",
                "title": rec["title"],
                "description": message[:200] if message else f"Failed {tool} evaluation",
                "actions": rec["actions"],
                "affected_code": None,
            }

        return None

    def _generate_recommendation_for_warning(
        self, result: Any, thread: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generate a recommendation for a warning evaluation.

        Args:
            result: Warning evaluation result
            thread: Thread data

        Returns:
            Recommendation dictionary or None
        """
        return {
            "priority": "🟡 Medium",
            "title": f"Address {result.tool} Warning",
            "description": (
                result.message[:200] if result.message else f"Warning from {result.tool}"
            ),
            "actions": [
                "Review the warning details and assess impact",
                "Monitor for recurring patterns",
                "Consider implementing preventive measures",
            ],
            "affected_code": None,
        }

    def _count_issues_by_priority(
        self, eval_result: Optional[EvaluationResponse]
    ) -> Dict[str, int]:
        """Count issues by priority level based on evaluation results.

        Args:
            eval_result: Evaluation results

        Returns:
            Dictionary with issue counts by priority
        """
        counts = {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}

        if not eval_result or not eval_result.results:
            return counts

        for result in eval_result.results:
            if result.status == "fail":
                counts["total"] += 1
                # Determine priority based on score and tool
                if result.score < 0.3:
                    counts["critical"] += 1
                elif result.score < 0.5:
                    counts["high"] += 1
                else:
                    counts["medium"] += 1
            elif result.status == "warning":
                counts["total"] += 1
                counts["low"] += 1

        return counts

    def _identify_slow_code_areas(self, thread: Dict[str, Any]) -> Optional[str]:
        """Identify code areas that may be causing slow execution.

        Args:
            thread: Thread data

        Returns:
            String describing affected code areas or None
        """
        steps = thread.get("steps", [])
        slow_steps = sorted(
            [s for s in steps if s.get("duration_ms", 0) > 2000],
            key=lambda s: s.get("duration_ms", 0),
            reverse=True,
        )

        if not slow_steps:
            return None

        areas = []
        for step in slow_steps[:3]:
            name = step.get("name", "Unknown")
            duration = step.get("duration_ms", 0)
            areas.append(f"- {name}: {duration}ms")

        return "\n".join(areas)

    def _identify_token_heavy_areas(self, thread: Dict[str, Any]) -> Optional[str]:
        """Identify areas with high token usage.

        Args:
            thread: Thread data

        Returns:
            String describing token-heavy areas or None
        """
        steps = thread.get("steps", [])
        token_heavy = sorted(
            [s for s in steps if s.get("tokens", 0) > 5000],
            key=lambda s: s.get("tokens", 0),
            reverse=True,
        )

        if not token_heavy:
            return None

        areas = []
        for step in token_heavy[:3]:
            name = step.get("name", "Unknown")
            tokens = step.get("tokens", 0)
            areas.append(f"- {name}: {tokens:,} tokens")

        return "\n".join(areas)

    def _categorize_errors(self, errors: List[Any]) -> Dict[str, List[str]]:
        """Categorize errors by type.

        Args:
            errors: List of error strings/objects

        Returns:
            Dictionary mapping error types to error lists
        """
        categories: Dict[str, List[str]] = {}

        for error in errors:
            error_str = str(error)

            # Simple categorization based on keywords
            if "timeout" in error_str.lower():
                category = "Timeout"
            elif "connection" in error_str.lower() or "network" in error_str.lower():
                category = "Connection"
            elif "auth" in error_str.lower() or "permission" in error_str.lower():
                category = "Authentication"
            elif "validation" in error_str.lower() or "invalid" in error_str.lower():
                category = "Validation"
            elif "exception" in error_str.lower() or "error" in error_str.lower():
                category = "Exception"
            else:
                category = "Other"

            if category not in categories:
                categories[category] = []
            categories[category].append(error_str)

        return categories

    def _get_error_remediation_actions(self, error_type: str) -> List[str]:
        """Get remediation actions for a specific error type.

        Args:
            error_type: Type of error

        Returns:
            List of remediation action strings
        """
        actions_map = {
            "Timeout": [
                "Increase timeout thresholds for long-running operations",
                "Implement chunked processing for large requests",
                "Add circuit breaker patterns for external services",
            ],
            "Connection": [
                "Implement connection pooling",
                "Add retry logic with exponential backoff",
                "Review network configuration and firewall rules",
            ],
            "Authentication": [
                "Verify API keys and credentials are valid",
                "Check token expiration and refresh logic",
                "Review permission scopes and access policies",
            ],
            "Validation": [
                "Add input validation at API boundaries",
                "Implement schema validation for data models",
                "Add descriptive error messages for validation failures",
            ],
            "Exception": [
                "Add comprehensive error handling and logging",
                "Implement graceful degradation strategies",
                "Review stack traces for root cause identification",
            ],
        }

        return actions_map.get(
            error_type,
            [
                "Review error logs for detailed information",
                "Add monitoring and alerting for this error type",
                "Implement proper error handling",
            ],
        )

    def _identify_error_source(self, errors: List[Any]) -> Optional[str]:
        """Attempt to identify the source of errors.

        Args:
            errors: List of errors

        Returns:
            String describing error sources or None
        """
        if not errors:
            return None

        sources = []
        for error in errors[:3]:
            error_str = str(error)[:150]
            sources.append(f"- {error_str}")

        return "\n".join(sources)

    def generate_report(
        self,
        threads: List[Dict[str, Any]],
        evaluations: Dict[str, EvaluationResponse],
        run_id: str,
    ) -> Path:
        """Generate a complete analysis report (combined summary).

        Args:
            threads: List of analyzed threads
            evaluations: Mapping of thread_id to evaluation results
            run_id: Unique run identifier

        Returns:
            Path to the generated report
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"analysis_report_{timestamp}.md"
        report_path = self.output_dir / filename

        content = self._build_report_content(threads, evaluations, run_id)

        report_path.write_text(content)
        logger.info(f"Report generated: {report_path}")

        return report_path

    def _build_report_content(
        self,
        threads: List[Dict[str, Any]],
        evaluations: Dict[str, EvaluationResponse],
        run_id: str,
    ) -> str:
        """Build the report markdown content."""
        lines = [
            "# LangSmith Thread Analysis Report",
            "",
            f"**Run ID:** `{run_id}`",
            f"**Generated:** {datetime.now().isoformat()}",
            f"**Threads Analyzed:** {len(threads)}",
            "",
            "---",
            "",
        ]

        # Summary section
        lines.extend(self._build_summary(threads, evaluations))

        # Individual thread sections
        for thread in threads:
            thread_id = thread.get("thread_id", "unknown")
            eval_result = evaluations.get(thread_id)
            lines.extend(self._build_thread_section(thread, eval_result))

        return "\n".join(lines)

    def _build_summary(
        self,
        threads: List[Dict[str, Any]],
        evaluations: Dict[str, EvaluationResponse],
    ) -> List[str]:
        """Build the summary section."""
        lines = ["## Summary", ""]

        # Count issues
        total_issues = 0
        by_status = {"pass": 0, "warning": 0, "fail": 0}

        for thread_id, eval_resp in evaluations.items():
            for result in eval_resp.results:
                by_status[result.status] = by_status.get(result.status, 0) + 1
                if result.status in ("warning", "fail"):
                    total_issues += 1

        lines.extend(
            [
                f"- **Total Issues Found:** {total_issues}",
                f"- **Passed Evaluations:** {by_status.get('pass', 0)}",
                f"- **Warnings:** {by_status.get('warning', 0)}",
                f"- **Failures:** {by_status.get('fail', 0)}",
                "",
            ]
        )

        # Issues by category
        if total_issues > 0:
            lines.append("### Issues by Evaluation Type")
            lines.append("")
            lines.append("| Evaluation | Warnings | Failures |")
            lines.append("|------------|----------|----------|")

            by_tool = {}
            for eval_resp in evaluations.values():
                for result in eval_resp.results:
                    if result.status in ("warning", "fail"):
                        if result.tool not in by_tool:
                            by_tool[result.tool] = {"warning": 0, "fail": 0}
                        by_tool[result.tool][result.status] += 1

            for tool, counts in sorted(by_tool.items()):
                lines.append(f"| {tool} | {counts['warning']} | {counts['fail']} |")

            lines.append("")

        lines.append("---")
        lines.append("")

        return lines

    def _build_thread_section(
        self,
        thread: Dict[str, Any],
        eval_result: EvaluationResponse = None,
    ) -> List[str]:
        """Build a section for a single thread."""
        thread_id = thread.get("thread_id", "unknown")
        thread_name = thread.get("name", "Unknown")

        lines = [
            f"## Thread: {thread_name[:50]}",
            "",
            f"**Thread ID:** `{thread_id}`",
        ]

        if thread.get("langsmith_url"):
            lines.append(f"**LangSmith:** [{thread_id[:8]}...]({thread['langsmith_url']})")

        lines.extend(
            [
                f"**Duration:** {thread.get('duration_seconds', 0):.2f}s",
                f"**Tokens:** {thread.get('total_tokens', 0):,}",
                f"**Status:** {thread.get('status', 'unknown')}",
                "",
            ]
        )

        # User query
        if thread.get("user_query"):
            lines.extend(
                [
                    "### User Query",
                    "",
                    f"> {thread['user_query'][:500]}",
                    "",
                ]
            )

        # Annotation
        if thread.get("annotation_text"):
            lines.extend(
                [
                    "### Annotation",
                    "",
                    f"> {thread['annotation_text'][:500]}",
                    "",
                ]
            )

        # Evaluation results
        if eval_result and eval_result.results:
            lines.extend(
                [
                    "### Evaluation Results",
                    "",
                    "| Tool | Status | Score | Message |",
                    "|------|--------|-------|---------|",
                ]
            )

            for result in eval_result.results:
                status_icon = (
                    "✅" if result.status == "pass" else "⚠️" if result.status == "warning" else "❌"
                )
                message = (result.message or "")[:50]
                lines.append(
                    f"| {result.tool} | {status_icon} {result.status} | {result.score:.2f} | {message} |"
                )

            lines.append("")

        # Errors
        if thread.get("errors"):
            lines.extend(
                [
                    "### Errors",
                    "",
                ]
            )
            for error in thread["errors"][:5]:
                lines.append(f"- `{error[:100]}`")
            lines.append("")

        lines.extend(["---", ""])

        return lines

    def generate_issue_summary(
        self,
        issues: List[Dict[str, Any]],
        run_id: str,
    ) -> Path:
        """Generate a summary of created issues.

        Args:
            issues: List of issue dictionaries
            run_id: Run identifier

        Returns:
            Path to the summary file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"issues_summary_{timestamp}.md"
        report_path = self.output_dir / filename

        lines = [
            "# Issues Created",
            "",
            f"**Run ID:** `{run_id}`",
            f"**Generated:** {datetime.now().isoformat()}",
            f"**Total Issues:** {len(issues)}",
            "",
            "---",
            "",
            "| Issue ID | Title | Priority | Category | Provider ID |",
            "|----------|-------|----------|----------|-------------|",
        ]

        for issue in issues:
            lines.append(
                f"| {issue.get('issue_id', 'N/A')} | "
                f"{issue.get('title', '')[:40]} | "
                f"{issue.get('priority', 'N/A')} | "
                f"{issue.get('category', 'N/A')} | "
                f"{issue.get('provider_id', 'N/A')} |"
            )

        content = "\n".join(lines)
        report_path.write_text(content)

        return report_path
