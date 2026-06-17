import os
import re
import subprocess
import requests
from github import Github
from typing import Dict, List, Optional
from agent.config import Config

class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token or Config.GITHUB_TOKEN
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.github_api_url = "https://api.github.com"
        self.gh = Github(self.token) if self.token else None

    def get_failed_jobs(self, repo_name: str, run_id: int) -> List[Dict]:
        """Fetch the jobs for a workflow run and filter for failed ones."""
        if not self.token:
            print("[Warning] GITHUB_TOKEN is missing. Cannot fetch jobs from API.")
            return []
            
        url = f"{self.github_api_url}/repos/{repo_name}/actions/runs/{run_id}/jobs"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            jobs_data = response.json()
            
            failed_jobs = []
            for job in jobs_data.get("jobs", []):
                if job.get("conclusion") == "failure":
                    failed_jobs.append({
                        "id": job.get("id"),
                        "name": job.get("name"),
                        "status": job.get("status"),
                        "conclusion": job.get("conclusion"),
                        "steps": job.get("steps", [])
                    })
            return failed_jobs
        except Exception as e:
            print(f"[Error] Failed to fetch jobs for run {run_id}: {e}")
            return []

    def download_job_logs(self, repo_name: str, job_id: int) -> str:
        """Download plain text logs for a specific job."""
        if not self.token:
            print("[Warning] GITHUB_TOKEN is missing. Cannot download job logs.")
            return ""
            
        url = f"{self.github_api_url}/repos/{repo_name}/actions/jobs/{job_id}/logs"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"[Error] Failed to download logs for job {job_id}: {e}")
            return ""

    def create_git_branch(self, repo_path: str, branch_name: str) -> bool:
        """Create and checkout a new branch locally in the repository."""
        try:
            # First checkout main/master or whatever the current branch is to ensure we branch from a clean state,
            # or just branch off the current active commit.
            # Let's verify clean index
            subprocess.run(["git", "checkout", "-b", branch_name], cwd=repo_path, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            # If branch already exists, checkout to it
            try:
                subprocess.run(["git", "checkout", branch_name], cwd=repo_path, check=True, capture_output=True)
                return True
            except subprocess.CalledProcessError:
                print(f"[Error] Failed to create or checkout branch {branch_name}: {e.stderr.decode()}")
                return False

    def commit_and_push_changes(self, repo_path: str, branch_name: str, commit_message: str, files: List[str]) -> bool:
        """Commit modified files and push the branch to origin."""
        try:
            # Ensure git user identity is configured (e.g. inside CI runners)
            user_configured = True
            try:
                res = subprocess.run(["git", "config", "user.name"], cwd=repo_path, capture_output=True, text=True)
                if not res.stdout.strip():
                    user_configured = False
            except Exception:
                user_configured = False
                
            if not user_configured:
                subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=repo_path, check=True, capture_output=True)
                subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=repo_path, check=True, capture_output=True)

            for file in files:
                subprocess.run(["git", "add", file], cwd=repo_path, check=True, capture_output=True)
                
            subprocess.run(["git", "commit", "-m", commit_message], cwd=repo_path, check=True, capture_output=True)
            
            # Push branch
            # Use GITHUB_TOKEN in remote URL if pushing inside GitHub action
            # Otherwise use simple git push origin branch_name
            # Let's find origin url
            result = subprocess.run(["git", "remote", "get-url", "origin"], cwd=repo_path, capture_output=True, text=True)
            origin_url = result.stdout.strip()
            
            # If running in CI environment, configure git credentials if possible or push using token url
            if self.token and ("github.com" in origin_url) and not origin_url.startswith("git@"):
                # Insert token into https URL for authorization: https://<token>@github.com/owner/repo
                authenticated_url = re.sub(r"https://(github\.com/.*)", f"https://x-access-token:{self.token}@\\1", origin_url)
                subprocess.run(["git", "push", "-u", authenticated_url, branch_name, "--force"], cwd=repo_path, check=True, capture_output=True)
            else:
                subprocess.run(["git", "push", "-u", "origin", branch_name, "--force"], cwd=repo_path, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"[Error] Git commit/push failed: {e.stderr.decode() if e.stderr else str(e)}")
            return False

    def open_pull_request(self, repo_name: str, branch_name: str, base_branch: str, title: str, body: str) -> Optional[str]:
        """Open a pull request on GitHub."""
        if not self.gh:
            print("[Warning] GitHub client is not authenticated. Cannot open PR.")
            return None
            
        try:
            repo = self.gh.get_repo(repo_name)
            pr = repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base=base_branch
            )
            return pr.html_url
        except Exception as e:
            print(f"[Error] Failed to open pull request: {e}")
            return None
