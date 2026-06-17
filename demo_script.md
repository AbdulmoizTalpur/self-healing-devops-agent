# Recruiter Demo Script: Self-Healing CI/CD Agent

This script walks through demonstrating the Self-Healing DevOps agent.

## Option A: Mock Mode (Offline/Quick Demo)

Use this option to showcase the agent immediately without copying any API keys.

### 1. Show the Broken Application code
Open [calculator.py](file:///C:/Users/moizt/.gemini/antigravity-ide/scratch/self-healing-devops-agent/examples/broken-python-app/calculator.py).
Point out:
- The `add` function has a bug: it returns `a - b` instead of `a + b`.
- The `divide` function is missing check for `b == 0` (failing the test expectation of raising `ValueError`).

### 2. Show the failing test suite
Run the tests locally to prove they fail:
```bash
cd examples/broken-python-app
python -m pytest
```
You will see:
- `test_add` fails.
- `test_divide_by_zero` fails.

### 3. Run the Self-Healing Agent
Run the agent in mock mode from the root directory:
```bash
cd ../..
python agent/main.py --local-dir examples/broken-python-app --mock
```

Explain the streaming console output as it executes:
- **Stage 1**: Detects CI failure event.
- **Stage 2**: Ingests the raw logs (mock logs match the pytest traceback of the broken app).
- **Stage 3**: Scans for files and recent diffs.
- **Stage 4**: Diagnoses the logic error (`a - b` instead of `a + b`, division check) and confirms safety (Low risk, no credential threats).
- **Stage 5**: Automatically edits [calculator.py](file:///C:/Users/moizt/.gemini/antigravity-ide/scratch/self-healing-devops-agent/examples/broken-python-app/calculator.py).
- **Stage 6**: Runs `pytest` inside the broken-python-app directory to verify. Tests now pass!
- **Stage 7**: Formats the pull request title, failure details, and root cause, and prints the markdown PR body to console.

---

## Option B: Real Execution (Online Demo)

To show the actual power of Gemini, configure your `.env` variables and run:

```bash
python agent/main.py --local-dir examples/broken-python-app --log-file tests/sample_fail_log.txt
```
*(Create `tests/sample_fail_log.txt` with traceback copy-pastes to feed real logs to Gemini)*

This will call the real Gemini API to:
1. Parse the log file and discover the files and errors.
2. Formulate a custom diagnosis.
3. Automatically regenerate the file fix via Gemini.
4. Run `pytest` locally to confirm the fix works.
5. Create a real GitHub PR if configured.
