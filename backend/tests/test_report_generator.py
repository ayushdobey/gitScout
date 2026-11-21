from app.core.security import get_password_hash
from app.models import AnalysisFinding, AnalysisRun, CodeSymbol, FileDependency, FileRecord, Repository, User
from app.services.report_generator import ArchitectureReportGenerator


def test_architecture_report_synthesis(db):
    """Verify Markdown report generation synthesizing metrics, topology, and static findings."""
    # 1. Setup DB state
    user = User(email="report_user@gitscout.io", password_hash=get_password_hash("pass"))
    db.add(user)
    db.commit()

    repo = Repository(
        user_id=user.id,
        github_url="https://github.com/my-org/core-service",
        owner="my-org",
        name="core-service",
        default_branch="main",
        stars=120,
        forks=25,
        primary_language="Python"
    )
    db.add(repo)
    db.commit()

    run = AnalysisRun(
        repository_id=repo.id,
        status="COMPLETED",
        duration_ms=450
    )
    db.add(run)
    db.commit()

    # 2. Add File, Symbol, Dependency, and Finding
    f1 = FileRecord(
        analysis_id=run.id,
        path="src/main.py",
        filename="main.py",
        extension=".py",
        language="Python",
        file_size=500,
        line_count=40,
        content_hash="h1",
        is_entry_point=True
    )
    f2 = FileRecord(
        analysis_id=run.id,
        path="src/service.py",
        filename="service.py",
        extension=".py",
        language="Python",
        file_size=400,
        line_count=30,
        content_hash="h2",
        is_entry_point=False
    )
    db.add_all([f1, f2])
    db.commit()

    sym = CodeSymbol(
        file_id=f1.id,
        name="bootstrap_app",
        symbol_type="FUNCTION",
        signature="def bootstrap_app() -> None:",
        start_line=10,
        end_line=25,
        docstring="Bootstraps microservice core."
    )
    dep = FileDependency(
        source_file_id=f1.id,
        target_file_id=f2.id,
        dependency_type="FROM_IMPORT",
        line_number=2
    )
    finding = AnalysisFinding(
        analysis_id=run.id,
        file_id=f1.id,
        tool="BANDIT",
        rule_id="B101",
        severity="MEDIUM",
        category="SECURITY",
        description="Assert statement detected",
        line_number=15
    )
    db.add_all([sym, dep, finding])
    db.commit()

    # 3. Generate Report
    generator = ArchitectureReportGenerator(db)
    report = generator.generate_report(repo.id)

    # 4. Verify Report Structure
    assert report["repository"] == "my-org/core-service"
    md = report["markdown"]

    # Verify Markdown sections
    assert "# GitScout Architecture Report: `my-org/core-service`" in md
    assert "## 1. Repository Overview & Statistics" in md
    assert "## 2. Technology Stack & Language Distribution" in md
    assert "## 3. Structural Entry Points & Orchestrators" in md
    assert "## 4. Key Architectural Modules & Centrality (PageRank)" in md
    assert "## 5. Dependency Graph Topology & Cycle Analysis" in md
    assert "## 6. Static Code Quality & Security Audit" in md
    assert "## 7. Architectural Observations & Recommendations" in md

    assert "`src/main.py`" in md
    assert "BANDIT" in md

    # Verify JSON summary
    assert report["summary"]["total_files"] == 2
    assert report["summary"]["total_symbols"] == 1
    assert report["summary"]["total_dependencies"] == 1
    assert report["summary"]["total_findings"] == 1

