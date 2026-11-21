from typing import List

from pydantic import BaseModel, ConfigDict


class CodeSymbolRead(BaseModel):
    id: str
    file_id: str
    name: str
    symbol_type: str
    signature: str | None = None
    start_line: int
    end_line: int
    docstring: str | None = None
    cyclomatic_complexity: int

    model_config = ConfigDict(from_attributes=True)


class FileRecordRead(BaseModel):
    id: str
    analysis_id: str
    path: str
    filename: str
    extension: str
    language: str
    file_size: int
    line_count: int
    is_entry_point: bool

    model_config = ConfigDict(from_attributes=True)


class FileRecordDetail(FileRecordRead):
    symbols: List[CodeSymbolRead] = []


class FileTreeNode(BaseModel):
    name: str
    path: str
    type: str  # "file" | "directory"
    size: int | None = None
    language: str | None = None
    children: List["FileTreeNode"] | None = None


FileTreeNode.model_rebuild()

