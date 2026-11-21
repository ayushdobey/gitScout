from typing import Dict

from pydantic import BaseModel, ConfigDict


class FindingRead(BaseModel):
    id: str
    analysis_id: str
    file_id: str
    file_path: str | None = None
    tool: str
    rule_id: str
    severity: str
    category: str
    description: str
    line_number: int
    snippet: str | None = None
    remediation_hint: str | None = None

    model_config = ConfigDict(from_attributes=True)


class FindingsSummary(BaseModel):
    total_findings: int
    by_severity: Dict[str, int]
    by_tool: Dict[str, int]
    by_category: Dict[str, int]

