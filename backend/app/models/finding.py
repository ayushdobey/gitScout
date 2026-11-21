from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import generate_uuid


class AnalysisFinding(Base):
    """
    AnalysisFinding stores static analysis and security audit results (from Ruff and Bandit).
    Annotates file locations with severity, rule classification, and remediation guidance.
    """
    __tablename__ = "analysis_findings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    analysis_id = Column(String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id = Column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    tool = Column(String(50), nullable=False)  # RUFF, BANDIT
    rule_id = Column(String(100), nullable=False)  # e.g., B101, F401, S105
    severity = Column(String(50), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    category = Column(String(100), nullable=False)  # SECURITY, CODE_SMELL, STYLE, COMPLEXITY
    description = Column(Text, nullable=False)
    line_number = Column(Integer, default=1, nullable=False)
    snippet = Column(Text, nullable=True)
    remediation_hint = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_findings_analysis_sev", "analysis_id", "severity"),
        Index("idx_findings_tool_rule", "tool", "rule_id"),
    )

    # Relationships
    analysis = relationship("AnalysisRun", back_populates="findings")
    file = relationship("FileRecord", back_populates="findings")

    def __repr__(self):
        return f"<AnalysisFinding id={self.id} tool={self.tool} rule={self.rule_id} sev={self.severity}>"

