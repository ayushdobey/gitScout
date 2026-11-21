from app.services.static_analysis import StaticAnalysisService

SAMPLE_INSECURE_CODE = """import os
import sys  # Unused import (Ruff F401)

def dangerous_function(user_input: str):
    # Potential security findings for Bandit (assert, hardcoded password)
    password = "super_secret_admin_password_123"  # Bandit B105
    assert user_input is not None  # Bandit B101
    return password
"""


def test_static_analysis_runner():
    """Verify Ruff and Bandit execution on synthetic Python code."""
    service = StaticAnalysisService()
    files = {"app/insecure_module.py": SAMPLE_INSECURE_CODE}

    findings = service.analyze_source_files(files)

    # We expect at least 1 finding from Ruff (unused import sys) or Bandit (assert / hardcoded password)
    assert len(findings) >= 1

    tools = {f.tool for f in findings}
    assert "RUFF" in tools or "BANDIT" in tools

    for finding in findings:
        assert finding.file_path == "app/insecure_module.py"
        assert finding.line_number > 0
        assert finding.severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert finding.remediation_hint is not None

