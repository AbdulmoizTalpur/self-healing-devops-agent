import subprocess
import sys
from pathlib import Path
from typing import List, Optional
from agent.schemas import VerificationResult

class TestRunner:
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()

    def detect_test_commands(self) -> List[str]:
        """Infer verification commands based on project structure."""
        commands = []
        
        # Check for Python / pytest
        pyproject = self.repo_path / "pyproject.toml"
        requirements = self.repo_path / "requirements.txt"
        pytest_ini = self.repo_path / "pytest.ini"
        
        # If any typical python indicators exist, add pytest
        if (self.repo_path / "tests").exists() or pyproject.exists() or requirements.exists() or pytest_ini.exists():
            # Use sys.executable to run pytest using the same interpreter environment
            commands.append(f"{sys.executable} -m pytest")
            
        # If no commands detected, fallback to standard python pytest run
        if not commands:
            commands.append("pytest")
            
        return commands

    def run_tests(self) -> VerificationResult:
        """Run all detected test commands and verify results."""
        commands = self.detect_test_commands()
        
        passed = True
        failed_command = None
        output_summary_lines = []
        remaining_errors = []
        
        for cmd in commands:
            print(f"[Info] Running verification command: {cmd}")
            try:
                # Split the command string for subprocess execution
                # Note: On Windows, running with shell=True is more robust for commands with spaces or system executables
                result = subprocess.run(
                    cmd,
                    cwd=self.repo_path,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60 # 60 second safety timeout
                )
                
                stdout = result.stdout or ""
                stderr = result.stderr or ""
                combined_output = f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
                
                if result.returncode != 0:
                    passed = False
                    failed_command = cmd
                    
                    # Extract failing traceback or error lines
                    error_lines = []
                    for line in combined_output.splitlines():
                        if "FAIL" in line or "error" in line.lower() or "exception" in line.lower() or "traceback" in line.lower():
                            error_lines.append(line.strip())
                    
                    # Capture the last few lines or first few errors
                    remaining_errors.extend(error_lines[:10])
                    
                    output_summary_lines.append(f"Command '{cmd}' failed (exit code {result.returncode}):\n{stdout[-1000:]}")
                else:
                    output_summary_lines.append(f"Command '{cmd}' passed successfully.")
                    
            except subprocess.TimeoutExpired:
                passed = False
                failed_command = cmd
                output_summary_lines.append(f"Command '{cmd}' timed out after 60 seconds.")
                remaining_errors.append("Execution timed out.")
            except Exception as e:
                passed = False
                failed_command = cmd
                output_summary_lines.append(f"Failed to execute '{cmd}': {str(e)}")
                remaining_errors.append(str(e))
                
        summary = "\n\n".join(output_summary_lines)
        return VerificationResult(
            commands_run=commands,
            passed=passed,
            failed_command=failed_command,
            output_summary=summary,
            remaining_errors=remaining_errors
        )
