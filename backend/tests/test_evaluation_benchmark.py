from app.services.evaluation import EvaluationFramework


def test_evaluation_framework_metrics(db):
    """
    Assert empirical evaluation benchmarks satisfy academic and production thresholds:
    - AST Parsing Accuracy >= 95%
    - Dependency Extraction Precision == 100%
    - Cycle Detection Accuracy == 100%
    - Hybrid Retrieval Recall@5 == 100%
    - MRR >= 0.5
    """
    framework = EvaluationFramework(db=db)
    report = framework.run_full_benchmark()

    # 1. Parsing Assertions
    assert report.parsing.overall_parsing_accuracy >= 0.95
    assert report.parsing.class_recall == 1.0
    assert report.parsing.function_recall == 1.0
    assert report.parsing.extracted_classes_matched == 3
    assert report.parsing.extracted_functions_matched == 14

    # 2. Dependency Graph Assertions
    assert report.dependencies.precision == 1.0
    assert report.dependencies.recall == 1.0
    assert report.dependencies.f1_score == 1.0
    assert report.dependencies.cycle_detection_accuracy == 1.0
    assert report.dependencies.detected_cycles == 1

    # 3. Hybrid Retrieval Assertions
    assert report.retrieval.recall_at_5 == 1.0
    assert report.retrieval.recall_at_3 == 1.0
    assert report.retrieval.mean_reciprocal_rank >= 0.5

    # 4. Latency Assertions
    assert report.latencies.ast_parsing_ms > 0
    assert report.latencies.resolver_ms >= 0
    assert report.latencies.graph_analysis_ms > 0
    assert report.latencies.hybrid_retrieval_avg_ms > 0
    assert report.latencies.end_to_end_pipeline_ms > 0


def test_evaluation_api_endpoint(client):
    """Verify REST API endpoint returns evaluation benchmark report."""
    response = client.get("/api/v1/evaluation/benchmark")
    assert response.status_code == 200
    data = response.json()

    assert data["system_status"] == "OPTIMAL"
    assert data["parsing"]["overall_parsing_accuracy"] >= 0.95
    assert data["dependencies"]["precision"] == 1.0
    assert data["retrieval"]["recall_at_5"] == 1.0
    assert "latencies" in data

