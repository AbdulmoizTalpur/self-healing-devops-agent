from typing import Dict, List, Optional
from google import genai
from google.genai import types
from agent.config import Config
from agent.schemas import FailureReport, Diagnosis

class DiagnosisAgent:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.GEMINI_API_KEY
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    def diagnose_failure(
        self, 
        report: FailureReport, 
        code_context: Dict[str, str], 
        git_diff: str
    ) -> Diagnosis:
        """Query Gemini to diagnose the root cause and propose a safe, minimal code fix."""
        
        # Format the code files context
        formatted_context = ""
        for filepath, content in code_context.items():
            formatted_context += f"\nFile: {filepath}\n```python\n{content}\n```\n"

        if not self.client or "mock" in (self.api_key or "").lower():
            print("[Warning] GEMINI_API_KEY is missing or mock. Using mock diagnosis.")
            # Mock diagnosis behavior for local testing
            suspected_files = report.suspected_files or ["calculator.py"]
            proposed_fix = "Fix the mathematical calculations to return the correct value."
            return Diagnosis(
                root_cause="A logical error in the source code or an incorrect assertion in the test code.",
                evidence_from_logs=[report.error_summary],
                evidence_from_code=["def add(a, b): return a - b  # should be +"],
                proposed_fix=proposed_fix,
                files_to_modify=suspected_files,
                risk_level="Low",
                should_attempt_fix=True
            )

        prompt = f"""
        You are an elite software engineer and autonomous debugger.
        We have a failing CI/CD run.
        
        Failure Report:
        {report.model_dump_json(indent=2)}
        
        Recent Git Diff in the commit that failed:
        ---
        {git_diff or 'No recent commit diff available.'}
        ---
        
        Suspected Files and their Code Content:
        ---
        {formatted_context}
        ---

        Perform a deep analysis of the traceback/logs and the current code context:
        1. Identify the EXACT root cause (logic error, off-by-one, type error, broken import, wrong test expectation).
        2. Gather specific evidence strings from the logs and from the code.
        3. Propose a targeted, minimal code fix. Avoid broad refactorings. Keep changes as localized as possible.
        4. List the exact files that need modification.
        5. Assess the risk level (Low, Medium, High).
        6. Determine if the fix is safe to attempt automatically. 
           Set `should_attempt_fix` to false if the failure touches security, auth, payments, database credentials, 
           or requires major architectural rewrites.
        """

        try:
            response = self.client.models.generate_content(
                model=Config.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Diagnosis,
                    temperature=0.1
                )
            )
            diagnosis = Diagnosis.model_validate_json(response.text)
            
            # Post-process with additional safety rules
            self._apply_safety_rules(diagnosis, code_context)
            return diagnosis
            
        except Exception as e:
            print(f"[Error] Gemini diagnosis failed: {e}")
            return Diagnosis(
                root_cause=f"Gemini analysis failed. Error: {str(e)}",
                evidence_from_logs=[],
                evidence_from_code=[],
                proposed_fix="Manual intervention required.",
                files_to_modify=[],
                risk_level="High",
                should_attempt_fix=False
            )

    def _apply_safety_rules(self, diagnosis: Diagnosis, code_context: Dict[str, str]):
        """Enforce strict guardrails. Modifies the diagnosis in-place if rules are violated."""
        # Rule 1: Stop if risk is High
        if diagnosis.risk_level.lower() == "high":
            diagnosis.should_attempt_fix = False
            print("[Safety Control] Aborted auto-fix: Risk level is High.")

        # Rule 2: Check for sensitive keywords in files being edited
        sensitive_keywords = ["secret", "password", "token", "credential", "auth_token", "private_key", "stripe", "payment", "creditcard"]
        for filepath, content in code_context.items():
            if filepath in diagnosis.files_to_modify:
                content_lower = content.lower()
                for keyword in sensitive_keywords:
                    if keyword in content_lower:
                        # If the proposed fix or files contain auth/payment elements, trigger caution
                        if any(k in filepath.lower() for k in ["auth", "security", "payment", "key", "config", "settings", "credential"]):
                            diagnosis.should_attempt_fix = False
                            print(f"[Safety Control] Aborted auto-fix: Suspected sensitive/credential file: {filepath}")
                            return

        # Rule 3: Stop if proposed fix touches infrastructure configurations (e.g. CI workflow files)
        for file in diagnosis.files_to_modify:
            if ".github/workflows" in file or "dockerfile" in file.lower() or "docker-compose" in file.lower():
                diagnosis.should_attempt_fix = False
                print(f"[Safety Control] Aborted auto-fix: Refusing to modify infrastructure config: {file}")
                return

        # Rule 4: Verify we don't try to edit empty files lists
        if not diagnosis.files_to_modify:
            diagnosis.should_attempt_fix = False
            print("[Safety Control] Aborted auto-fix: No files specified for modification.")
