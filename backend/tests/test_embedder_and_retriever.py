import math

import pytest

from app.core.security import get_password_hash
from app.models import AnalysisRun, CodeChunk, FileRecord, Repository, User
from app.services.embedder import FastDeterministicEmbedder
from app.services.retriever import HybridRetriever


def test_embedder_properties():
    """Verify vector dimension, repeatability, and L2 unit normalization."""
    embedder = FastDeterministicEmbedder(dimension=384)
    vec1 = embedder.embed_text("def authenticate_user(token: str):")
    vec2 = embedder.embed_text("def authenticate_user(token: str):")
    vec3 = embedder.embed_text("def compute_matrix_multiplication(a, b):")

    assert len(vec1) == 384
    # Deterministic output
    assert vec1 == vec2
    # Distinct vector for different semantics
    assert vec1 != vec3

    # L2 Unit Norm
    norm = math.sqrt(sum(x * x for x in vec1))
    assert pytest.approx(norm, 0.001) == 1.0


def test_hybrid_retriever_rrf(db):
    """Verify Reciprocal Rank Fusion combines vector similarity and keyword hits."""
    # 1. Setup Repo and Analysis Run
    user = User(email="search_tester@gitscout.io", password_hash=get_password_hash("pass"))
    db.add(user)
    db.commit()

    repo = Repository(user_id=user.id, github_url="https://github.com/test/rag", owner="test", name="rag")
    db.add(repo)
    db.commit()

    run = AnalysisRun(repository_id=repo.id, status="COMPLETED")
    db.add(run)
    db.commit()

    # 2. Add File and Chunks
    file_auth = FileRecord(
        analysis_id=run.id,
        path="src/auth/jwt_handler.py",
        filename="jwt_handler.py",
        extension=".py",
        language="Python",
        file_size=500,
        line_count=30,
        content_hash="h1"
    )
    file_math = FileRecord(
        analysis_id=run.id,
        path="src/utils/math_helpers.py",
        filename="math_helpers.py",
        extension=".py",
        language="Python",
        file_size=500,
        line_count=30,
        content_hash="h2"
    )
    db.add_all([file_auth, file_math])
    db.commit()

    embedder = FastDeterministicEmbedder(dimension=384)

    chunk_auth = CodeChunk(
        file_id=file_auth.id,
        content="def verify_jwt_token(token: str) -> bool:\n    \"\"\"Validates signature and expiration.\"\"\"\n    return True",
        start_line=1,
        end_line=15,
        token_count=18,
        embedding=embedder.embed_text("def verify_jwt_token(token: str) -> bool: Validates signature and expiration.")
    )
    chunk_math = CodeChunk(
        file_id=file_math.id,
        content="def compute_fibonacci(n: int) -> int:\n    if n <= 1: return n\n    return compute_fibonacci(n-1) + compute_fibonacci(n-2)",
        start_line=1,
        end_line=15,
        token_count=22,
        embedding=embedder.embed_text("def compute_fibonacci(n: int) -> int:")
    )
    db.add_all([chunk_auth, chunk_math])
    db.commit()

    # 3. Execute Hybrid Search
    retriever = HybridRetriever(db)
    results = retriever.hybrid_search(analysis_id=run.id, query="Where is JWT token validation implemented?", top_k=2)

    assert len(results) >= 1
    top_hit = results[0]
    assert top_hit.file_path == "src/auth/jwt_handler.py"
    assert "verify_jwt_token" in top_hit.content
    assert top_hit.rrf_score > 0.0

