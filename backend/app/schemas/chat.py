from typing import List

from pydantic import BaseModel


class ChatQuestionRequest(BaseModel):
    session_id: str | None = None
    question: str


class CitationRead(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    snippet: str | None = None
    relevance_score: float | None = None


class ChatAnswerResponse(BaseModel):
    session_id: str
    message_id: str
    question: str
    answer: str
    citations: List[CitationRead] = []
    latency_ms: int | None = None

