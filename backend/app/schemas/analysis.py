from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AnalysisRunRead(BaseModel):
    id: str
    repository_id: str
    commit_hash: str | None = None
    status: str
    error_message: str | None = None
    file_count: int
    symbol_count: int
    dependency_count: int
    finding_count: int
    duration_ms: int | None = None
    started_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AnalysisStatusRead(BaseModel):
    run_id: str
    repository_id: str
    status: str
    current_step: str
    progress_percentage: int
    error_message: str | None = None

