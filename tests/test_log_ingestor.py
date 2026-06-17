import pytest
from agent.log_ingestor import LogIngestor

def test_filter_logs_short():
    ingestor = LogIngestor()
    short_log = "Run pytest\ntest_calculator.py FAILED\nAssertionError"
    # For logs with <= 200 lines, it should return them fully
    assert ingestor.filter_logs(short_log) == short_log

def test_filter_logs_long_traceback():
    ingestor = LogIngestor()
    
    # Construct a log of 250 lines
    lines = [f"Info line {i}" for i in range(100)]
    lines.append("Traceback (most recent call last):")
    lines.append("  File \"calculator.py\", line 10, in add")
    lines.append("    assert calc.add(2, 3) == 5")
    lines.append("AssertionError")
    lines.extend([f"Info line {i}" for i in range(100, 240)])
    
    long_log = "\n".join(lines)
    filtered = ingestor.filter_logs(long_log)
    
    assert "Traceback (most recent call last):" in filtered
    assert "AssertionError" in filtered
    assert "Info line 0" not in filtered # Should be truncated
