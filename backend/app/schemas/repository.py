import re
from datetime import datetime
from typing import Dict

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RepositoryCreate(BaseModel):
    github_url: str = Field(..., json_schema_extra={"example": "https://github.com/pallets/flask"})
    branch: str | None = Field(None, description="Specific branch, defaults to repository default branch")

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        clean_url = v.strip().rstrip("/")
        pattern = r"^https?://(www\.)?github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)$"
        match = re.match(pattern, clean_url)
        if not match:
            raise ValueError("Must be a valid GitHub repository URL (e.g., https://github.com/owner/repo)")
        return clean_url


class RepositoryRead(BaseModel):
    id: str
    user_id: str
    github_url: str
    owner: str
    name: str
    default_branch: str
    stars: int
    forks: int
    primary_language: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RepositoryStats(BaseModel):
    repository_id: str
    file_count: int
    symbol_count: int
    dependency_count: int
    finding_count: int
    circular_dependency_count: int
    languages: Dict[str, int]
    top_connected_modules: list[dict]
