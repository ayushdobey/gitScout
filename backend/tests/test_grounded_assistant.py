from app.core.security import get_password_hash
from app.models import AnalysisRun, ChatMessage, CodeChunk, FileRecord, MessageCitation, Repository, User
from app.services.assistant import CodebaseAssistantService, extract_citations_from_text
from app.services.embedder import FastDeterministicEmbedder
from app.services.llm import MockLLMProvider


def test_extract_citations_regex():
    """Verify regex citation parser extracts file paths and line ranges."""
    sample_text = (
        "Authentication is handled in [src/auth/jwt.py#L12-L35]. "
        "Additionally, configuration is defined in [config.py#L42-L60]."
    )
    citations = extract_citations_from_text(sample_text)
    assert len(citations) == 2
    assert citations[0] == ("src/auth/jwt.py", 12, 35)
    assert citations[1] == ("config.py", 42, 60)


def test_assistant_grounded_qa_flow(db):
    """Verify full assistant Q&A workflow including citation persistence and chat history."""
    # 1. Setup repository and chunk
    user = User(email="assistant_tester@gitscout.io", password_hash=get_password_hash("pass"))
    db.add(user)
    db.commit()

    repo = Repository(user_id=user.id, github_url="https://github.com/org/service", owner="org", name="service")
    db.add(repo)
    db.commit()

    run = AnalysisRun(repository_id=repo.id, status="COMPLETED", file_count=1)
    db.add(run)
    db.commit()

    file_rec = FileRecord(
        analysis_id=run.id,
        path="src/database/session.py",
        filename="session.py",
        extension=".py",
        language="Python",
        file_size=300,
        line_count=20,
        content_hash="h123"
    )
    db.add(file_rec)
    db.commit()

    embedder = FastDeterministicEmbedder(dimension=384)
    chunk = CodeChunk(
        file_id=file_rec.id,
        content="def get_db_session():\n    \"\"\"Yields managed database connection.\"\"\"\n    db = SessionLocal()\n    try:\n        yield db\n    finally:\n        db.close()",
        start_line=5,
        end_line=15,
        token_count=25,
        embedding=embedder.embed_text("def get_db_session database connection pool session")
    )
    db.add(chunk)
    db.commit()

    # 2. Invoke Assistant Service with Mock LLM
    assistant = CodebaseAssistantService(db=db, llm_provider=MockLLMProvider())
    response = assistant.answer_question(
        repository_id=repo.id,
        user_id=user.id,
        question="How does database connection session cleanup work?"
    )

    # 3. Verify Response Payload
    assert response["answer"] is not None
    assert "src/database/session.py" in response["answer"]
    assert len(response["citations"]) >= 1
    top_citation = response["citations"][0]
    assert top_citation["file_path"] == "src/database/session.py"
    assert top_citation["start_line"] == 5
    assert top_citation["end_line"] == 15

    # 4. Verify Database Persistence
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == response["session_id"]).all()
    assert len(messages) == 2  # 1 User, 1 Assistant
    user_msg = next(m for m in messages if m.role == "USER")
    assistant_msg = next(m for m in messages if m.role == "ASSISTANT")

    assert user_msg.content == "How does database connection session cleanup work?"
    assert assistant_msg.latency_ms is not None

    citations = db.query(MessageCitation).filter(MessageCitation.message_id == assistant_msg.id).all()
    assert len(citations) >= 1
    assert citations[0].file_path == "src/database/session.py"

