from typing import List, Optional
from agent.config import Config
from agent.github_client import GitHubClient
from agent.schemas import FailureReport, Diagnosis, VerificationResult, PRWalkthrough
from agent.llm_client import LLMClient

class PRCreator:
    def __init__(self, github_client: GitHubClient, llm_client: Optional[LLMClient] = None):
        self.gh_client = github_client
        self.client = llm_client or LLMClient()

    def generate_pr_walkthrough(
        self, 
        report: FailureReport, 
        diagnosis: Diagnosis, 
        verification: VerificationResult,
        files_changed: List[str]
    ) -> PRWalkthrough:
        """Call Gemini to draft a structured PR walkthrough."""
        if self.client.is_mock:
            print("[Warning] Running in mock mode. Generating default PR details.")
            return PRWalkthrough(
                title=f"[Self-Healing Agent] Fix CI failure in {report.workflow_name}/{report.failed_job}",
                failure_summary=report.error_summary,
                root_cause=diagnosis.root_cause,
                fix_summary=diagnosis.proposed_fix,
                changed_files=files_changed,
                verification_commands=verification.commands_run,
                verification_result="Passed successfully." if verification.passed else "Failed.",
                risk_level=diagnosis.risk_level,
                reviewer_notes=["Automatically generated PR. Please verify safety before merging."]
            )

        prompt = f"""
        You are a professional software engineer drafting a pull request.
        A self-healing agent has successfully fixed a CI/CD build failure, verified it locally, and is ready to submit a PR.
        
        Failure Report:
        {report.model_dump_json(indent=2)}
        
        Diagnosis:
        {diagnosis.model_dump_json(indent=2)}
        
        Verification Result:
        {verification.model_dump_json(indent=2)}
        
        Modified Files:
        {files_changed}
        
        Generate a clear, professional PR Walkthrough with:
        1. A compelling PR title.
        2. A clear explanation of what failed in CI.
        3. A root cause analysis.
        4. Details of the fix.
        5. Verification commands and results.
        6. A risk level assessment.
        7. Key notes or warnings for the human reviewer.
        """

        try:
            walkthrough = self.client.generate_structured(
                prompt=prompt,
                response_schema=PRWalkthrough,
                temperature=0.2
            )
            return walkthrough
        except Exception as e:
            print(f"[Error] Failed to generate structured PR walkthrough: {e}")
            # Fallback
            return PRWalkthrough(
                title=f"[Self-Healing Agent] Fix CI failure in {report.workflow_name}",
                failure_summary=report.error_summary,
                root_cause=diagnosis.root_cause,
                fix_summary=diagnosis.proposed_fix,
                changed_files=files_changed,
                verification_commands=verification.commands_run,
                verification_result="Passed" if verification.passed else "Failed",
                risk_level=diagnosis.risk_level,
                reviewer_notes=["Fallback PR template used due to LLM error."]
            )

    def build_markdown_body(self, walkthrough: PRWalkthrough) -> str:
        """Convert structured walkthrough into a clean markdown body for GitHub PRs."""
        reviewer_notes_list = "\n".join(f"- {note}" for note in walkthrough.reviewer_notes)
        changed_files_list = "\n".join(f"- `{f}`" for f in walkthrough.changed_files)
        verification_cmds = ", ".join(f"`{c}`" for c in walkthrough.verification_commands)
        
        body = f"""## What failed
{walkthrough.failure_summary}

## Root cause
{walkthrough.root_cause}

## Fix implemented
{walkthrough.fix_summary}

### Files changed
{changed_files_list}

## Verification
- **Verification commands**: {verification_cmds}
- **Results**: {walkthrough.verification_result}

## Risk level
**{walkthrough.risk_level.upper()}**

## Notes for reviewer
{reviewer_notes_list or 'None'}

---
*Created automatically by the Self-Healing CI/CD DevOps Agent.*
"""
        return body

    def create_pr(
        self, 
        repo_name: str, 
        branch_name: str, 
        base_branch: str, 
        walkthrough: PRWalkthrough
    ) -> Optional[str]:
        """Format and open a pull request on GitHub."""
        body = self.build_markdown_body(walkthrough)
        return self.gh_client.open_pull_request(
            repo_name=repo_name,
            branch_name=branch_name,
            base_branch=base_branch,
            title=walkthrough.title,
            body=body
        )
