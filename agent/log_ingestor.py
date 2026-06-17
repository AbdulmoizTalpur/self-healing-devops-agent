import os
import re
from typing import Optional
from agent.config import Config
from agent.schemas import FailureReport
from agent.llm_client import LLMClient

class LogIngestor:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.client = llm_client or LLMClient()

    def filter_logs(self, raw_logs: str) -> str:
        """
        Pre-filter logs to isolate failure information (e.g. pytest traceback).
        Keeps sections containing tracebacks, assertion errors, and test failures.
        If logs are very short, returns them fully.
        """
        lines = raw_logs.splitlines()
        if len(lines) <= 200:
            return raw_logs

        # Search for interesting lines
        interesting_indices = []
        patterns = [
            re.compile(r"FAIL(S|ED)?\b", re.IGNORECASE),
            re.compile(r"Traceback \(most recent call last\):"),
            re.compile(r"__+ traceback __+"),
            re.compile(r"assertionerror", re.IGNORECASE),
            re.compile(r"===+ FAILURES ===+"),
            re.compile(r"===+ ERRORS ===+"),
            re.compile(r"ModuleNotFoundError:"),
            re.compile(r"ImportError:"),
            re.compile(r"SyntaxError:"),
            re.compile(r"TypeError:")
        ]

        for i, line in enumerate(lines):
            if any(pat.search(line) for pat in patterns):
                interesting_indices.append(i)

        if not interesting_indices:
            # If no direct patterns matched, grab the last 200 lines
            return "\n".join(lines[-200:])

        # Extract segments around the interesting lines (e.g., 20 lines before and 50 lines after)
        segments = []
        visited = set()
        for idx in interesting_indices:
            start = max(0, idx - 20)
            end = min(len(lines), idx + 80)
            
            # Form contiguous blocks
            block = []
            for line_idx in range(start, end):
                if line_idx not in visited:
                    block.append(lines[line_idx])
                    visited.add(line_idx)
            if block:
                segments.append("\n".join(block))

        return "\n\n... [Truncated Log Section] ...\n\n".join(segments)

    def analyze_logs(self, raw_logs: str, workflow_name: str, failed_job: str) -> FailureReport:
        """Call the LLM to parse logs and return a structured FailureReport."""
        filtered_log = self.filter_logs(raw_logs)
        
        # If running in mock mode, return a default mock FailureReport for testing
        if self.client.is_mock:
            print("[Warning] Running in mock mode. Using mock log analysis.")
            # Let's see if we can extract suspected files using regex
            suspected = []
            for line in raw_logs.splitlines():
                match = re.search(r"(\S+\.py):(\d+)", line)
                if match:
                    filename = match.group(1)
                    # Handle paths
                    basename = os.path.basename(filename)
                    if filename not in suspected:
                        suspected.append(filename)
                    # Heuristic: if it is a test file, also suspect the source file
                    if basename.startswith("test_"):
                        src_name = basename.replace("test_", "")
                        # Add relative to the same directory or general search
                        dirname = os.path.dirname(filename)
                        src_path = os.path.join(dirname, src_name) if dirname else src_name
                        if src_path not in suspected:
                            src_path = src_path.replace("\\", "/")
                            suspected.append(src_path)
            return FailureReport(
                workflow_name=workflow_name,
                failed_job=failed_job,
                failed_step="Run pytest" if "pytest" in raw_logs.lower() else "Unknown Step",
                error_summary="Detected local build / test execution failure.",
                stack_trace=filtered_log[:1500],
                suspected_files=suspected if suspected else ["test_calculator.py", "calculator.py"],
                suspected_failure_type="Unit test failure",
                confidence=0.8
            )

        prompt = f"""
        You are an expert DevOps engineer and log parsing agent.
        Analyze the following CI/CD job execution logs for a workflow named "{workflow_name}" and job "{failed_job}".
        
        Logs:
        ---
        {filtered_log}
        ---

        Extract the following:
        1. The failed step name (e.g., "Run tests" or "Lint with Ruff").
        2. A precise, clear error summary.
        3. The stack trace / failing traceback snippet.
        4. Suspected files mentioned in the failure trace (both test files and implementation source files).
        5. The failure type (e.g., "Unit test failure", "Syntax error", "Import error", "Config issue", "Type error", etc.).
        6. A confidence score (0.0 to 1.0) indicating how clear the failure reason is from the logs.
        """

        try:
            report = self.client.generate_structured(
                prompt=prompt,
                response_schema=FailureReport,
                temperature=0.1
            )
            return report
        except Exception as e:
            print(f"[Error] Log analysis failed: {e}. Falling back to default report.")
            # Fallback
            return FailureReport(
                workflow_name=workflow_name,
                failed_job=failed_job,
                failed_step="Unknown",
                error_summary=f"Failed during analysis. Error: {str(e)}",
                stack_trace=filtered_log[:1000],
                suspected_files=[],
                suspected_failure_type="Unknown error",
                confidence=0.5
            )
