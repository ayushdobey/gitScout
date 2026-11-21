from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.evaluation import EvaluationFramework

router = APIRouter()


@router.get("/benchmark")
def run_evaluation_benchmark(db: Session = Depends(get_db)):
    """
    Execute empirical evaluation benchmark measuring AST parsing accuracy,
    dependency extraction precision, Tarjan cycle detection, hybrid retrieval Recall@5,
    and end-to-end pipeline latency.
    """
    framework = EvaluationFramework(db=db)
    report = framework.run_full_benchmark()
    return report.to_dict()

