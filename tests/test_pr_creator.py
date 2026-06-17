import pytest
from agent.pr_creator import PRCreator
from agent.github_client import GitHubClient
from agent.schemas import PRWalkthrough

def test_build_markdown_body():
    client = GitHubClient(token="dummy")
    creator = PRCreator(client)
    
    walkthrough = PRWalkthrough(
        title="Fix calculation bug",
        failure_summary="test_add failed with AssertionError",
        root_cause="add was doing a - b",
        fix_summary="Changed - to + in calculator.py",
        changed_files=["calculator.py"],
        verification_commands=["pytest"],
        verification_result="Passed successfully.",
        risk_level="Low",
        reviewer_notes=["Verify logic correctness."]
    )
    
    body = creator.build_markdown_body(walkthrough)
    
    assert "test_add failed with AssertionError" in body
    assert "add was doing a - b" in body
    assert "Changed - to + in calculator.py" in body
    assert "- `calculator.py`" in body
    assert "pytest" in body
    assert "LOW" in body
    assert "- Verify logic correctness." in body
