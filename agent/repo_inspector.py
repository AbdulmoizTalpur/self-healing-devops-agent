import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

class RepoInspector:
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()

    def find_file(self, file_name_pattern: str) -> List[Path]:
        """Find files in the repository matching a specific pattern (e.g. 'calculator.py' or '*.json')."""
        matches = []
        for root, _, files in os.walk(self.repo_path):
            # Exclude standard directories
            if any(dir_name in root for dir_name in [".git", "node_modules", "venv", "__pycache__", ".pytest_cache"]):
                continue
            for file in files:
                if file_name_pattern in file or file_name_pattern == file:
                    matches.append(Path(root) / file)
        return matches

    def read_file_content(self, relative_or_absolute_path: str) -> Optional[str]:
        """Read the full content of a file, returning None if not found or error."""
        file_path = Path(relative_or_absolute_path)
        if not file_path.is_absolute():
            file_path = self.repo_path / file_path
            
        file_path = file_path.resolve()
        
        # Ensure file is inside the repository path to avoid directory traversal
        if not str(file_path).startswith(str(self.repo_path)):
            print(f"[Warning] Security block: Refusing to read file outside workspace: {file_path}")
            return None

        if not file_path.exists() or not file_path.is_file():
            # Try searching for the file name if relative path didn't resolve directly
            search_results = self.find_file(file_path.name)
            if search_results:
                file_path = search_results[0]
            else:
                return None

        try:
            return file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"[Error] Failed to read {file_path}: {e}")
            return None


    def get_recent_diff(self) -> str:
        """Fetch the git diff of the last commit (HEAD~1..HEAD) or current changes."""
        try:
            # Check if there is a commit history first
            res = subprocess.run(["git", "rev-parse", "HEAD~1"], cwd=self.repo_path, capture_output=True)
            if res.returncode == 0:
                result = subprocess.run(["git", "diff", "HEAD~1", "HEAD"], cwd=self.repo_path, check=True, capture_output=True, text=True)
                return result.stdout
            else:
                # If only 1 commit exists or repository is brand new/no history, return untracked diff or first commit diff
                result = subprocess.run(["git", "diff", "HEAD"], cwd=self.repo_path, capture_output=True, text=True)
                return result.stdout
        except Exception as e:
            print(f"[Warning] Failed to fetch git diff: {e}")
            return ""

    def gather_context(self, suspected_files: List[str]) -> Dict[str, str]:
        """Gather code contents for suspected files."""
        context = {}
        for filename in suspected_files:
            # Clean path from potential line numbers or formats like 'test_calculator.py:12'
            clean_name = filename.split(":")[0].strip()
            content = self.read_file_content(clean_name)
            if content:
                context[clean_name] = content
        return context
