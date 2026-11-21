import json
import logging
import os
import subprocess  # nosec B404
import sys
import tempfile
from dataclasses import dataclass
from typing import Dict, List

logger = logging.getLogger(__name__)


@dataclass
class StaticFindingData:
    tool: str  # RUFF, BANDIT
    rule_id: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    category: str  # SECURITY, CODE_SMELL, STYLE, COMPLEXITY
    description: str
    file_path: str
    line_number: int
    snippet: str | None = None
    remediation_hint: str | None = None


class StaticAnalysisService:
    """
    Executes static code quality linting (Ruff) and security vulnerability auditing (Bandit).
    Maps raw CLI/JSON outputs to standardized severity classifications and remediation advice.
    """
    def __init__(self):
        pass

    def run_ruff(self, target_dir: str) -> List[StaticFindingData]:
        """
        Execute Ruff linter in JSON output mode and parse findings.
        """
        findings: List[StaticFindingData] = []
        try:
            # Use current python executable's scripts directory or venv
            cmd = [sys.executable, "-m", "ruff", "check", target_dir, "--output-format=json"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)  # nosec B603
            
            # Ruff returns code 1 if findings exist, which is expected
            if result.stdout:
                raw_data = json.loads(result.stdout)
                for item in raw_data:
                    filename = item.get("filename", "")
                    rel_path = os.path.relpath(filename, target_dir).replace("\\", "/")
                    rule_code = item.get("code", "RUFF")
                    message = item.get("message", "Code quality issue")
                    location = item.get("location", {})
                    line_num = location.get("row", 1)

                    # Determine severity and category based on Ruff prefix
                    severity = "LOW"
                    category = "CODE_SMELL"
                    if rule_code.startswith("S"):
                        severity = "MEDIUM"
                        category = "SECURITY"
                    elif rule_code.startswith("E") or rule_code.startswith("F"):
                        severity = "MEDIUM"
                        category = "STYLE"
                    elif rule_code.startswith("C"):
                        severity = "LOW"
                        category = "COMPLEXITY"

                    findings.append(
                        StaticFindingData(
                            tool="RUFF",
                            rule_id=rule_code,
                            severity=severity,
                            category=category,
                            description=message,
                            file_path=rel_path,
                            line_number=line_num,
                            snippet=item.get("fix", {}).get("message") if item.get("fix") else None,
                            remediation_hint=f"Review rule {rule_code} in Ruff documentation for recommended refactoring."
                        )
                    )
        except Exception as exc:
            logger.warning("Ruff static analysis execution failed or timed out: %s", exc)

        return findings

    def run_bandit(self, target_dir: str) -> List[StaticFindingData]:
        """
        Execute Bandit AST security scanner in JSON mode and parse vulnerabilities.
        """
        findings: List[StaticFindingData] = []
        try:
            cmd = [sys.executable, "-m", "bandit", "-r", target_dir, "-f", "json"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)  # nosec B603
            
            output = result.stdout or result.stderr
            if output:
                try:
                    data = json.loads(output)
                    raw_results = data.get("results", [])
                    for res in raw_results:
                        filename = res.get("filename", "")
                        rel_path = os.path.relpath(filename, target_dir).replace("\\", "/")
                        rule_id = res.get("test_id", "BANDIT")
                        text_msg = res.get("issue_text", "Potential security vulnerability")
                        line_num = res.get("line_number", 1)
                        raw_sev = res.get("issue_severity", "MEDIUM").upper()

                        # Map severity
                        severity = "MEDIUM"
                        if raw_sev == "HIGH":
                            severity = "HIGH"
                        elif raw_sev == "LOW":
                            severity = "LOW"

                        # High severity + High confidence -> CRITICAL
                        if raw_sev == "HIGH" and res.get("issue_confidence") == "HIGH":
                            severity = "CRITICAL"

                        findings.append(
                            StaticFindingData(
                                tool="BANDIT",
                                rule_id=rule_id,
                                severity=severity,
                                category="SECURITY",
                                description=text_msg,
                                file_path=rel_path,
                                line_number=line_num,
                                snippet=res.get("code", "").strip() if res.get("code") else None,
                                remediation_hint=res.get("more_info", "Verify input sanitization and avoid dangerous dynamic evaluation.")
                            )
                        )
                except json.JSONDecodeError as jde:
                    logger.warning("Bandit JSON decoding error: %s", jde)
        except Exception as exc:
            logger.warning("Bandit static analysis execution failed: %s", exc)

        return findings

    def analyze_source_files(self, files: Dict[str, str]) -> List[StaticFindingData]:
        """
        Analyze a dictionary of {relative_path: source_code} by creating a temporary sandbox directory,
        running both Ruff and Bandit, and returning normalized findings.
        """
        findings: List[StaticFindingData] = []
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write files to sandbox
            for rel_path, code in files.items():
                if not rel_path.endswith(".py"):
                    continue
                full_path = os.path.join(temp_dir, rel_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(code)

            # Run Ruff
            findings.extend(self.run_ruff(temp_dir))
            # Run Bandit
            findings.extend(self.run_bandit(temp_dir))

        return findings
