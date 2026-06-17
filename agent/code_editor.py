import shutil
from pathlib import Path
from typing import Dict, List, Optional
from agent.config import Config
from agent.schemas import Diagnosis
from agent.llm_client import LLMClient

class CodeEditor:
    def __init__(self, repo_path: str, llm_client: Optional[LLMClient] = None):
        self.repo_path = Path(repo_path).resolve()
        self.client = llm_client or LLMClient()
        self.backups: Dict[Path, str] = {}

    def backup_files(self, files_to_modify: List[str]):
        """Store original contents of all files that are going to be edited."""
        self.backups.clear()
        for filename in files_to_modify:
            file_path = self.repo_path / filename
            if file_path.exists() and file_path.is_file():
                try:
                    self.backups[file_path] = file_path.read_text(encoding="utf-8")
                except Exception as e:
                    print(f"[Warning] Failed to backup file {filename}: {e}")

    def rollback(self):
        """Restore all backed-up files to their original state."""
        if not self.backups:
            print("[Info] No backups available to rollback.")
            return

        print("[Info] Rolling back changes to original files...")
        for file_path, content in self.backups.items():
            try:
                file_path.write_text(content, encoding="utf-8")
                print(f"  Restored: {file_path.name}")
            except Exception as e:
                print(f"[Error] Failed to restore backup for {file_path}: {e}")
        self.backups.clear()

    def apply_fix(self, diagnosis: Diagnosis, code_context: Dict[str, str]) -> List[str]:
        """Apply the generated fixes using Gemini to modify the files."""
        modified_files = []
        
        # Backup first
        self.backup_files(diagnosis.files_to_modify)

        for filename in diagnosis.files_to_modify:
            file_path = self.repo_path / filename
            original_content = code_context.get(filename)
            
            if not original_content:
                # If file wasn't loaded in context, try loading it now
                if file_path.exists():
                    original_content = file_path.read_text(encoding="utf-8")
                else:
                    original_content = ""

            if self.client.is_mock:
                print(f"[Warning] Running in mock mode. Simulating mock fix on {filename}.")
                # Apply a dummy fix if mock mode is on
                # Let's perform a simple logical fix for our demo app if present
                fixed_content = original_content
                if "calculator.py" in filename:
                    fixed_content = original_content.replace("return a - b", "return a + b", 1)
                    fixed_content = fixed_content.replace("return a / b  # Bug: doesn't handle division by zero correctly", "if b == 0:\n            raise ValueError('Cannot divide by zero')\n        return a / b")
                elif "test_calculator.py" in filename:
                    # Keep test unmodified or fix broken assert
                    pass
                
                try:
                    file_path.write_text(fixed_content, encoding="utf-8")
                    modified_files.append(filename)
                except Exception as e:
                    print(f"[Error] Failed to write fix to {filename}: {e}")
                continue

            prompt = f"""
            You are a precise and safe code generator.
            Your task is to modify a source file to fix a bug based on a provided diagnosis.
            
            File to edit: {filename}
            Original Content:
            ---
            {original_content}
            ---

            Diagnosis of the Failure:
            ---
            {diagnosis.root_cause}
            ---

            Proposed Fix Description:
            ---
            {diagnosis.proposed_fix}
            ---

            Please return the COMPLETE, updated content for the file.
            Do NOT include any markdown code blocks (e.g. ```python) or comments outside the code.
            Return ONLY the raw file content ready to be saved.
            Preserve all unrelated code, comments, formatting, and imports. Do not add placeholders or shorten code!
            """

            try:
                raw_response = self.client.generate_content(
                    prompt=prompt,
                    temperature=0.1
                )
                fixed_content = raw_response.strip()
                
                # Strip leading/trailing python markdown formatting if the model output them anyway
                if fixed_content.startswith("```"):
                    lines = fixed_content.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    fixed_content = "\n".join(lines).strip()
                
                # Write to disk
                file_path.write_text(fixed_content, encoding="utf-8")
                modified_files.append(filename)
                
            except Exception as e:
                print(f"[Error] Failed to generate fix for {filename}: {e}")
                self.rollback()
                return []

        return modified_files
