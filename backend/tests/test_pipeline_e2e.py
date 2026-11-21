from app.core.security import get_password_hash
from app.models import AnalysisRun, CodeSymbol, FileDependency, FileRecord, Repository, User
from app.services.ingestion import ExtractedSourceFile, IngestionResult
from app.services.pipeline import run_repository_analysis_pipeline


def test_end_to_end_pipeline_analysis(db):
    """
    Test complete Phase 2 ingestion -> AST parsing -> symbol extraction -> dependency graph pipeline.
    Uses synthetic multi-module Python codebase to assert database state.
    """
    # 1. Setup user and repo
    user = User(
        email="pipeline_tester@gitscout.io",
        password_hash=get_password_hash("pass1234")
    )
    db.add(user)
    db.commit()

    repo = Repository(
        user_id=user.id,
        github_url="https://github.com/gitscout/test-repo",
        owner="gitscout",
        name="test-repo",
        default_branch="main"
    )
    db.add(repo)
    db.commit()

    run = AnalysisRun(
        repository_id=repo.id,
        status="PENDING"
    )
    db.add(run)
    db.commit()

    # 2. Synthetic Multi-Module Codebase
    file1_code = """\"\"\"Core models module.\"\"\"
class DataModel:
    \"\"\"Encapsulates domain entities.\"\"\"
    def __init__(self, name: str, value: int = 0):
        self.name = name
        self.value = value

    def to_dict(self) -> dict:
        return {"name": self.name, "value": self.value}
"""

    file2_code = """\"\"\"Utilities module.\"\"\"
def compute_hash(val: str) -> str:
    \"\"\"Computes hash string.\"\"\"
    return f"hash_{val}"
"""

    file3_code = """\"\"\"Main application entry point.\"\"\"
from .models import DataModel
from .utils import compute_hash

def process_item(name: str) -> DataModel:
    \"\"\"High-level orchestrator.\"\"\"
    h = compute_hash(name)
    return DataModel(name=h)

if __name__ == "__main__":
    item = process_item("sample")
"""

    synthetic_files = [
        ExtractedSourceFile(
            path="app/models.py",
            filename="models.py",
            extension=".py",
            language="Python",
            file_size=len(file1_code),
            content=file1_code,
            content_hash="sha256_mock_1"
        ),
        ExtractedSourceFile(
            path="app/utils.py",
            filename="utils.py",
            extension=".py",
            language="Python",
            file_size=len(file2_code),
            content=file2_code,
            content_hash="sha256_mock_2"
        ),
        ExtractedSourceFile(
            path="app/main.py",
            filename="main.py",
            extension=".py",
            language="Python",
            file_size=len(file3_code),
            content=file3_code,
            content_hash="sha256_mock_3"
        ),
        ExtractedSourceFile(
            path="README.md",
            filename="README.md",
            extension=".md",
            language="Markdown",
            file_size=50,
            content="# Sample Readme",
            content_hash="sha256_mock_md"
        )
    ]

    mock_ingestion = IngestionResult(
        owner="gitscout",
        name="test-repo",
        default_branch="main",
        stars=42,
        forks=5,
        primary_language="Python",
        files=synthetic_files,
        total_files=len(synthetic_files),
        total_bytes=sum(f.file_size for f in synthetic_files)
    )

    # 3. Execute Pipeline
    completed_run = run_repository_analysis_pipeline(
        analysis_run_id=run.id,
        custom_ingestion_result=mock_ingestion,
        db_session=db
    )

    # 4. Verify Database Records
    assert completed_run.status == "COMPLETED"
    assert completed_run.file_count == 4
    assert completed_run.symbol_count >= 5  # DataModel, __init__, to_dict, compute_hash, process_item
    assert completed_run.dependency_count == 2  # main -> models, main -> utils
    assert completed_run.duration_ms is not None

    # Refresh DB session to query persisted entities
    db.expire_all()

    # Verify Files in DB
    files = db.query(FileRecord).filter(FileRecord.analysis_id == run.id).all()
    assert len(files) == 4
    file_map = {f.path: f for f in files}
    assert "app/main.py" in file_map
    assert file_map["app/main.py"].is_entry_point is True
    assert file_map["app/models.py"].is_entry_point is False

    # Verify Symbols in DB
    symbols = db.query(CodeSymbol).join(FileRecord).filter(FileRecord.analysis_id == run.id).all()
    symbol_names = [s.name for s in symbols]
    assert "DataModel" in symbol_names
    assert "DataModel.__init__" in symbol_names
    assert "DataModel.to_dict" in symbol_names
    assert "compute_hash" in symbol_names
    assert "process_item" in symbol_names

    # Verify Docstrings
    data_model_sym = next(s for s in symbols if s.name == "DataModel")
    assert data_model_sym.docstring == "Encapsulates domain entities."

    # Verify Dependencies in DB
    deps = db.query(FileDependency).filter(
        FileDependency.source_file_id == file_map["app/main.py"].id
    ).all()
    assert len(deps) == 2
    target_ids = [d.target_file_id for d in deps]
    assert file_map["app/models.py"].id in target_ids
    assert file_map["app/utils.py"].id in target_ids

    # Verify Repository Status
    refreshed_repo = db.query(Repository).filter(Repository.id == repo.id).first()
    assert refreshed_repo.status == "READY"
    assert refreshed_repo.stars == 42
    assert refreshed_repo.forks == 5
