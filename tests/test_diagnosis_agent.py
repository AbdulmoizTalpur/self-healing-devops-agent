import pytest
from agent.diagnosis_agent import DiagnosisAgent
from agent.schemas import Diagnosis

def test_safety_rules_low_risk():
    agent = DiagnosisAgent()
    diagnosis = Diagnosis(
        root_cause="Logical bug in add function",
        evidence_from_logs=["assert -1 == 5"],
        evidence_from_code=["return a - b"],
        proposed_fix="Change - to +",
        files_to_modify=["calculator.py"],
        risk_level="Low",
        should_attempt_fix=True
    )
    code_context = {"calculator.py": "def add(a, b): return a - b"}
    
    agent._apply_safety_rules(diagnosis, code_context)
    assert diagnosis.should_attempt_fix is True

def test_safety_rules_high_risk():
    agent = DiagnosisAgent()
    diagnosis = Diagnosis(
        root_cause="Broad architectural mismatch",
        evidence_from_logs=["Critical error"],
        evidence_from_code=[],
        proposed_fix="Rewrite auth logic",
        files_to_modify=["auth.py"],
        risk_level="High",
        should_attempt_fix=True
    )
    code_context = {"auth.py": "def login(): pass"}
    
    agent._apply_safety_rules(diagnosis, code_context)
    assert diagnosis.should_attempt_fix is False # Should be blocked due to High risk

def test_safety_rules_credentials():
    agent = DiagnosisAgent()
    diagnosis = Diagnosis(
        root_cause="Broken API endpoint config",
        evidence_from_logs=["Unauthenticated"],
        evidence_from_code=[],
        proposed_fix="Set api key",
        files_to_modify=["config.py"],
        risk_level="Low",
        should_attempt_fix=True
    )
    code_context = {"config.py": "API_SECRET_TOKEN = 'xyz'"}
    
    agent._apply_safety_rules(diagnosis, code_context)
    assert diagnosis.should_attempt_fix is False # Should be blocked due to sensitive secret keyword

def test_safety_rules_workflows():
    agent = DiagnosisAgent()
    diagnosis = Diagnosis(
        root_cause="Broken action checkout",
        evidence_from_logs=["Cannot checkout"],
        evidence_from_code=[],
        proposed_fix="Change action version",
        files_to_modify=[".github/workflows/ci.yml"],
        risk_level="Low",
        should_attempt_fix=True
    )
    code_context = {".github/workflows/ci.yml": "on: push"}
    
    agent._apply_safety_rules(diagnosis, code_context)
    assert diagnosis.should_attempt_fix is False # Should be blocked due to modifying workflows
