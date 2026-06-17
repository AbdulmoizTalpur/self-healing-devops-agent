from pydantic import BaseModel, Field
from typing import List, Optional

class FailureReport(BaseModel):
    workflow_name: str = Field(..., description="Name of the failing workflow")
    failed_job: str = Field(..., description="Name of the failing job")
    failed_step: str = Field(..., description="Name of the failing step")
    error_summary: str = Field(..., description="Short description of the error / crash reason")
    stack_trace: Optional[str] = Field(None, description="Extracted error log or stack trace snippet")
    suspected_files: List[str] = Field(default_factory=list, description="List of source/test files suspected to be causing the issue")
    suspected_failure_type: str = Field(..., description="E.g. Unit test failure, Syntax error, Import error, Config issue, etc.")
    confidence: float = Field(..., description="Confidence score from 0.0 to 1.0 about the ingestion classification")

class Diagnosis(BaseModel):
    root_cause: str = Field(..., description="Deep explanation of why the failure occurred")
    evidence_from_logs: List[str] = Field(default_factory=list, description="Snippets from logs supporting the diagnosis")
    evidence_from_code: List[str] = Field(default_factory=list, description="Snippets from code files supporting the diagnosis")
    proposed_fix: str = Field(..., description="Description of the changes needed to fix the bug")
    files_to_modify: List[str] = Field(..., description="List of specific files that need code edits")
    risk_level: str = Field("Low", description="Risk level rating: Low, Medium, High")
    should_attempt_fix: bool = Field(..., description="Set to True only if safe to fix automatically based on safety rules")

class FixDecision(BaseModel):
    should_fix: bool = Field(..., description="Whether the agent should attempt to modify code")
    confidence: float = Field(..., description="Confidence score in the diagnosis and fix safety")
    reason: str = Field(..., description="Rationale for either attempting or refusing to fix")
    requires_human_review: bool = Field(..., description="True if code should only be updated manually by a human")

class VerificationResult(BaseModel):
    commands_run: List[str] = Field(..., description="List of commands executed for verification")
    passed: bool = Field(..., description="True if all verification commands succeeded without failure")
    failed_command: Optional[str] = Field(None, description="Command that failed, if any")
    output_summary: str = Field(..., description="Brief summary of test/lint runner execution output")
    remaining_errors: List[str] = Field(default_factory=list, description="Errors/tracebacks that are still present")

class PRWalkthrough(BaseModel):
    title: str = Field(..., description="Title for the Pull Request")
    failure_summary: str = Field(..., description="Summary of the failed CI/CD run")
    root_cause: str = Field(..., description="Explanation of the diagnosed bug")
    fix_summary: str = Field(..., description="Details of the implemented fix")
    changed_files: List[str] = Field(..., description="List of modified files")
    verification_commands: List[str] = Field(..., description="List of commands run to verify the fix")
    verification_result: str = Field(..., description="Pass/Fail status and brief summaries")
    risk_level: str = Field(..., description="Risk assessment (Low/Medium/High) of the change")
    reviewer_notes: List[str] = Field(default_factory=list, description="Notes, comments or warning details for the human reviewer")
