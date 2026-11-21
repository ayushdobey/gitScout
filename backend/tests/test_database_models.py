import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security import get_password_hash
from app.models import (
    AnalysisRun,
    CodeChunk,
    CodeSymbol,
    FileDependency,
    FileRecord,
    Repository,
    User,
)


def test_user_creation_and_unique_constraint(db):
    """Test user entity creation and unique email constraint enforcement."""
    user = User(
        email="developer@example.com",
        password_hash=get_password_hash("securepass123"),
        full_name="Alice Dev"
    )
    db.add(user)
    db.commit()

    assert user.id is not None
    assert user.email == "developer@example.com"
    assert user.is_active is True

    # Attempt inserting duplicate email
    duplicate_user = User(
        email="developer@example.com",
        password_hash=get_password_hash("differentpass")
    )
    db.add(duplicate_user)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_repository_lifecycle_and_cascades(db):
    """
    Test 3NF relational hierarchy and cascading deletion rules:
    User -> Repository -> AnalysisRun -> FileRecord -> CodeSymbol / Dependency.
    """
    # 1. Create User
    user = User(
        email="bob@example.com",
        password_hash=get_password_hash("bobpassword")
    )
    db.add(user)
    db.commit()

    # 2. Create Repository
    repo = Repository(
        user_id=user.id,
        github_url="https://github.com/example/sample-repo",
        owner="example",
        name="sample-repo",
        default_branch="main"
    )
    db.add(repo)
    db.commit()

    # 3. Create AnalysisRun
    run = AnalysisRun(
        repository_id=repo.id,
        commit_hash="abc1234",
        status="COMPLETED",
        file_count=2,
        symbol_count=4
    )
    db.add(run)
    db.commit()

    # 4. Create Source Files
    file_a = FileRecord(
        analysis_id=run.id,
        path="src/main.py",
        filename="main.py",
        extension=".py",
        language="Python",
        file_size=1024,
        line_count=45,
        content_hash="hash_a1b2c3d4",
        is_entry_point=True
    )
    file_b = FileRecord(
        analysis_id=run.id,
        path="src/utils.py",
        filename="utils.py",
        extension=".py",
        language="Python",
        file_size=512,
        line_count=20,
        content_hash="hash_e5f6g7h8",
        is_entry_point=False
    )
    db.add_all([file_a, file_b])
    db.commit()

    # 5. Create Code Symbols
    symbol = CodeSymbol(
        file_id=file_a.id,
        name="process_data",
        symbol_type="FUNCTION",
        signature="def process_data(input_stream: Stream) -> Result:",
        start_line=10,
        end_line=25,
        docstring="Transforms raw stream into structured analytics."
    )
    db.add(symbol)
    db.commit()

    # 6. Create Directed Dependency Edge (file_a -> file_b)
    dep = FileDependency(
        source_file_id=file_a.id,
        target_file_id=file_b.id,
        dependency_type="FROM_IMPORT",
        imported_symbol="format_date",
        line_number=2
    )
    db.add(dep)
    db.commit()

    # 7. Create Code Chunk with Embedding
    chunk = CodeChunk(
        file_id=file_a.id,
        symbol_id=symbol.id,
        content="def process_data(input_stream):\n    return format_date()",
        start_line=10,
        end_line=25,
        token_count=18,
        embedding=[0.12, -0.45, 0.78]
    )
    db.add(chunk)
    db.commit()

    # 8. Verify Entities Exist in DB
    assert db.query(CodeSymbol).filter(CodeSymbol.id == symbol.id).count() == 1
    assert db.query(FileDependency).filter(FileDependency.id == dep.id).count() == 1
    assert db.query(CodeChunk).filter(CodeChunk.id == chunk.id).count() == 1

    # 9. Test Atomic Cascading Delete: Deleting repo cascades down to files, symbols, chunks, and dependencies
    db.delete(repo)
    db.commit()

    assert db.query(Repository).filter(Repository.id == repo.id).count() == 0
    assert db.query(AnalysisRun).filter(AnalysisRun.id == run.id).count() == 0
    assert db.query(FileRecord).filter(FileRecord.id == file_a.id).count() == 0
    assert db.query(CodeSymbol).filter(CodeSymbol.id == symbol.id).count() == 0
    assert db.query(FileDependency).filter(FileDependency.id == dep.id).count() == 0
    assert db.query(CodeChunk).filter(CodeChunk.id == chunk.id).count() == 0


def test_unique_repository_per_user_constraint(db):
    """Enforce that a user cannot register duplicate copies of the same repository URL."""
    user = User(
        email="carol@example.com",
        password_hash=get_password_hash("carolpass")
    )
    db.add(user)
    db.commit()

    repo1 = Repository(
        user_id=user.id,
        github_url="https://github.com/django/django",
        owner="django",
        name="django"
    )
    db.add(repo1)
    db.commit()

    repo2 = Repository(
        user_id=user.id,
        github_url="https://github.com/django/django",
        owner="django",
        name="django"
    )
    db.add(repo2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

