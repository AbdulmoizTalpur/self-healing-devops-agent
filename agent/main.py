import argparse
import os
import sys
from pathlib import Path
from agent.config import Config
from agent.github_client import GitHubClient
from agent.log_ingestor import LogIngestor
from agent.repo_inspector import RepoInspector
from agent.diagnosis_agent import DiagnosisAgent
from agent.code_editor import CodeEditor
from agent.test_runner import TestRunner
from agent.pr_creator import PRCreator
from agent.streaming import ProgressStreamer

TOTAL_STAGES = 7

def main():
    parser = argparse.ArgumentParser(description="Self-Healing CI/CD DevOps Agent")
    parser.add_argument("--repo", type=str, default="example/broken-python-app", help="GitHub repository name (owner/repo)")
    parser.add_argument("--run-id", type=int, default=12345, help="GitHub Action workflow run ID")
    parser.add_argument("--job-id", type=int, help="GitHub Action job ID")
    parser.add_argument("--branch", type=str, default="main", help="Target base branch")
    parser.add_argument("--local-dir", type=str, default=".", help="Path to local repository workspace")
    parser.add_argument("--log-file", type=str, help="Path to a local log file (bypasses GitHub Action log download)")
    parser.add_argument("--mock", action="store_true", help="Simulate external API calls (Gemini/GitHub) for demo purposes")
    
    args = parser.parse_args()

    # Determine local directory path
    repo_path = Path(args.local_dir).resolve()
    if not repo_path.exists():
        print(f"[Error] Local repository directory does not exist: {repo_path}")
        sys.exit(1)

    # Initialize streaming
    streamer = ProgressStreamer()
    streamer.log("Starting Self-Healing CI/CD DevOps Agent...", level="INFO")

    # If mock mode is specified, we force configure empty credentials if they aren't present
    if args.mock:
        streamer.log("Running in MOCK mode. External APIs (Gemini/GitHub REST) will be simulated.", level="WARNING")
        # Ensure we don't crash on missing config validations
        os.environ["GITHUB_TOKEN"] = os.getenv("GITHUB_TOKEN", "mock_github_token")
        os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY", "mock_gemini_key")
        # Reload configs
        Config.GITHUB_TOKEN = "mock_github_token"
        Config.GEMINI_API_KEY = "mock_gemini_key"
    else:
        # Validate configurations
        validation_errors = Config.validate()
        if validation_errors:
            for error in validation_errors:
                streamer.log(error, level="ERROR")
            streamer.log("Please set credentials in .env or run with --mock.", level="WARNING")
            sys.exit(1)

    # Initialize components
    gh_client = GitHubClient()
    log_ingestor = LogIngestor()
    repo_inspector = RepoInspector(str(repo_path))
    diagnosis_agent = DiagnosisAgent()
    code_editor = CodeEditor(str(repo_path))
    test_runner = TestRunner(str(repo_path))
    pr_creator = PRCreator(gh_client)

    # ==========================================
    # STAGE 1: CI Failure Detection
    # ==========================================
    streamer.stream_stage(1, TOTAL_STAGES, f"CI failure detected in repository: {args.repo} on branch: {args.branch}")

    # ==========================================
    # STAGE 2: Log Ingestion
    # ==========================================
    streamer.stream_stage(2, TOTAL_STAGES, "Ingesting failed CI/CD error logs...")
    raw_logs = ""
    
    if args.log_file:
        log_path = Path(args.log_file).resolve()
        if log_path.exists():
            streamer.log(f"Reading logs from local file: {log_path}", level="INFO")
            raw_logs = log_path.read_text(encoding="utf-8", errors="replace")
        else:
            streamer.log(f"Local log file not found: {log_path}", level="ERROR")
            sys.exit(1)
    elif args.mock:
        streamer.log("Generating mock failing pytest logs...", level="INFO")
        raw_logs = """
================================== FAILURES ===================================
_________________________________ test_divide _________________________________

    def test_divide():
        calc = Calculator()
>       assert calc.divide(6, 3) == 2
E       assert 3 == 2
E        +  where 3 = divide(6, 3)

test_calculator.py:12: AssertionError
_____________________________ test_divide_by_zero _____________________________

    def test_divide_by_zero():
        calc = Calculator()
>       with pytest.raises(ValueError):
E       Failed: DID NOT RAISE <class 'ValueError'>

test_calculator.py:18: Failed
=========================== short test summary info ===========================
FAILED test_calculator.py::test_divide - assert 3 == 2
FAILED test_calculator.py::test_divide_by_zero - Failed: DID NOT RAISE <class 'ValueError'>
============================== 2 failed in 0.05s ==============================
"""
    else:
        # Fetch from GitHub
        if not args.job_id:
            streamer.log("Fetching failed jobs from GitHub...", level="INFO")
            failed_jobs = gh_client.get_failed_jobs(args.repo, args.run_id)
            if not failed_jobs:
                streamer.log("No failed jobs found for this workflow run.", level="SUCCESS")
                sys.exit(0)
            # Take the first failed job for processing
            target_job = failed_jobs[0]
            args.job_id = target_job["id"]
            streamer.log(f"Selected failed job: {target_job['name']} (ID: {args.job_id})", level="INFO")
            
        streamer.log(f"Downloading logs for job ID {args.job_id}...", level="INFO")
        raw_logs = gh_client.download_job_logs(args.repo, args.job_id)
        if not raw_logs:
            streamer.log("Could not download logs from GitHub Actions.", level="ERROR")
            sys.exit(1)

    # Parse and extract Failure Report
    failure_report = log_ingestor.analyze_logs(raw_logs, "CI Pipeline", args.repo)
    streamer.log(f"Failure type classified: {failure_report.suspected_failure_type} (Confidence: {failure_report.confidence})", level="SUCCESS")
    streamer.log(f"Error summary: {failure_report.error_summary}", level="INFO")
    streamer.log(f"Suspected files: {failure_report.suspected_files}", level="INFO")

    # ==========================================
    # STAGE 3: Repository Inspection
    # ==========================================
    streamer.stream_stage(3, TOTAL_STAGES, "Inspecting suspected source and test files...")
    code_context = repo_inspector.gather_context(failure_report.suspected_files)
    git_diff = repo_inspector.get_recent_diff()
    
    streamer.log(f"Gathered code context for {len(code_context)} files.", level="INFO")

    # ==========================================
    # STAGE 4: Diagnosis & Safety Decision
    # ==========================================
    streamer.stream_stage(4, TOTAL_STAGES, "Diagnosing root cause and verifying safety rule constraints...")
    diagnosis = diagnosis_agent.diagnose_failure(failure_report, code_context, git_diff)
    
    streamer.log(f"Diagnosis Root Cause: {diagnosis.root_cause}", level="INFO")
    streamer.log(f"Proposed Fix: {diagnosis.proposed_fix}", level="INFO")
    
    if not diagnosis.should_attempt_fix:
        streamer.log("Self-healing aborted due to safety constraints or high risk.", level="SAFETY")
        streamer.log(f"Reason: {diagnosis.proposed_fix}", level="INFO")
        sys.exit(0)

    # Check confidence threshold from config
    if failure_report.confidence < Config.CONFIDENCE_THRESHOLD:
        streamer.log(f"Self-healing aborted: Ingestion confidence {failure_report.confidence} below threshold {Config.CONFIDENCE_THRESHOLD}.", level="SAFETY")
        sys.exit(0)

    # ==========================================
    # STAGE 5: Applying Code Fix
    # ==========================================
    streamer.stream_stage(5, TOTAL_STAGES, "Applying targeted code fix to codebase...")
    
    # Create git branch
    fix_branch = f"self-healing/fix-ci-{args.run_id}"
    if not args.mock:
        streamer.log(f"Creating new git branch: {fix_branch}", level="INFO")
        branch_created = gh_client.create_git_branch(str(repo_path), fix_branch)
        if not branch_created:
            streamer.log("Failed to create branch. Aborting fix.", level="ERROR")
            sys.exit(1)
    else:
        streamer.log(f"[Mock] Created git branch: {fix_branch}", level="INFO")

    # Edit code
    modified_files = code_editor.apply_fix(diagnosis, code_context)
    if not modified_files:
        streamer.log("Failed to apply code modifications. Code rolled back.", level="ERROR")
        sys.exit(1)
        
    streamer.log(f"Successfully modified files: {modified_files}", level="SUCCESS")

    # ==========================================
    # STAGE 6: Local Verification
    # ==========================================
    streamer.stream_stage(6, TOTAL_STAGES, "Running test verification checks locally...")
    
    verification_result = test_runner.run_tests()
    if verification_result.passed:
        streamer.log("All local verification tests passed!", level="SUCCESS")
    else:
        streamer.log("Local verification failed. Rolling back changes...", level="ERROR")
        streamer.log(f"Test failure summary:\n{verification_result.output_summary}", level="INFO")
        # Rollback changes if tests fail
        code_editor.rollback()
        # Reset git state back to base branch if branch was created
        if not args.mock:
            subprocess.run(["git", "checkout", args.branch], cwd=str(repo_path), capture_output=True)
            subprocess.run(["git", "branch", "-D", fix_branch], cwd=str(repo_path), capture_output=True)
        sys.exit(1)

    # ==========================================
    # STAGE 7: Pull Request Creation
    # ==========================================
    streamer.stream_stage(7, TOTAL_STAGES, "Opening pull request with diagnosis explanation...")
    
    # Commit and push
    commit_msg = f"fix: Auto-healing CI failure in {failure_report.workflow_name}"
    if not args.mock:
        streamer.log("Committing and pushing changes to GitHub remote...", level="INFO")
        push_success = gh_client.commit_and_push_changes(str(repo_path), fix_branch, commit_msg, modified_files)
        if not push_success:
            streamer.log("Failed to push changes to remote repository.", level="ERROR")
            sys.exit(1)
    else:
        streamer.log(f"[Mock] Committed and pushed files: {modified_files}", level="INFO")

    # Draft walkthrough and open PR
    pr_walkthrough = pr_creator.generate_pr_walkthrough(failure_report, diagnosis, verification_result, modified_files)
    
    if not args.mock:
        streamer.log("Opening PR on GitHub...", level="INFO")
        pr_url = pr_creator.create_pr(args.repo, fix_branch, args.branch, pr_walkthrough)
        if pr_url:
            streamer.log(f"Pull request created successfully! URL: {pr_url}", level="SUCCESS")
        else:
            streamer.log("Failed to open pull request.", level="ERROR")
    else:
        streamer.log("[Mock] Opening PR details...", level="INFO")
        body = pr_creator.build_markdown_body(pr_walkthrough)
        streamer.log(f"Mock Pull Request Title: {pr_walkthrough.title}", level="SUCCESS")
        streamer.log(f"Mock Pull Request Body:\n{body}", level="INFO")

    streamer.log("Self-Healing CI/CD DevOps Agent execution finished successfully!", level="SUCCESS")

if __name__ == "__main__":
    main()
