from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.models.repository import Repository
from app.models.user import User
from app.schemas.chat import ChatAnswerResponse, ChatQuestionRequest
from app.services.assistant import CodebaseAssistantService

router = APIRouter()


@router.post("/repo/{repo_id}/chat", response_model=ChatAnswerResponse)
def ask_codebase(
    repo_id: str,
    request: ChatQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Query the codebase assistant with evidence grounding.
    Executes hybrid RAG retrieval, prompt assembly, LLM inference, and persists verified citations.
    """
    repo = db.query(Repository).filter(
        Repository.id == repo_id,
        Repository.user_id == current_user.id
    ).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    assistant = CodebaseAssistantService(db)
    try:
        response = assistant.answer_question(
            repository_id=repo_id,
            user_id=current_user.id,
            question=request.question,
            session_id=request.session_id
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assistant error: {str(e)}")
