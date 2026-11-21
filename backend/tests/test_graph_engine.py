from app.services.graph_engine import DependencyGraphEngine


def test_acyclic_graph_analysis():
    """Verify metrics and topological analysis on a Directed Acyclic Graph (DAG)."""
    engine = DependencyGraphEngine()
    
    # Nodes: main -> service -> repository -> database_driver
    engine.add_node("n1", "src/main.py", "main.py", "Python", is_entry_point=True)
    engine.add_node("n2", "src/service.py", "service.py", "Python")
    engine.add_node("n3", "src/repository.py", "repository.py", "Python")
    engine.add_node("n4", "src/db.py", "db.py", "Python")
    engine.add_node("n5", "src/isolated.py", "isolated.py", "Python")

    engine.add_dependency("n1", "n2", "DIRECT_IMPORT")
    engine.add_dependency("n2", "n3", "FROM_IMPORT")
    engine.add_dependency("n3", "n4", "DIRECT_IMPORT")

    result = engine.analyze()

    assert result.total_nodes == 5
    assert result.total_edges == 3
    assert result.is_dag is True
    assert len(result.circular_dependencies) == 0
    assert len(result.circular_edge_tuples) == 0
    assert "src/isolated.py" in result.isolated_modules

    # Degree checks
    metrics = result.node_metrics
    assert metrics["n1"]["out_degree"] == 1
    assert metrics["n1"]["in_degree"] == 0

    assert metrics["n4"]["out_degree"] == 0
    assert metrics["n4"]["in_degree"] == 1

    # Shortest path: n1 -> n4 should return [main.py, service.py, repository.py, db.py]
    path = engine.find_shortest_path("n1", "n4")
    assert path == ["src/main.py", "src/service.py", "src/repository.py", "src/db.py"]

    # Shortest path to isolated should be None
    assert engine.find_shortest_path("n1", "n5") is None


def test_circular_dependency_detection():
    """Verify Tarjan's SCC algorithm flags circular import cycles."""
    engine = DependencyGraphEngine()

    # Cyclic loop: A -> B -> C -> A
    engine.add_node("a", "app/auth.py", "auth.py", "Python")
    engine.add_node("b", "app/user.py", "user.py", "Python")
    engine.add_node("c", "app/session.py", "session.py", "Python")
    # Independent module
    engine.add_node("d", "app/config.py", "config.py", "Python")

    engine.add_dependency("a", "b", "FROM_IMPORT")
    engine.add_dependency("b", "c", "FROM_IMPORT")
    engine.add_dependency("c", "a", "FROM_IMPORT")
    engine.add_dependency("a", "d", "DIRECT_IMPORT")

    result = engine.analyze()

    assert result.is_dag is False
    assert len(result.circular_dependencies) == 1
    cycle = result.circular_dependencies[0]
    assert set(cycle) == {"app/auth.py", "app/user.py", "app/session.py"}

    # Verify circular edge tuples
    assert ("a", "b") in result.circular_edge_tuples
    assert ("b", "c") in result.circular_edge_tuples
    assert ("c", "a") in result.circular_edge_tuples
    assert ("a", "d") not in result.circular_edge_tuples


def test_direct_and_reverse_dependencies():
    """Verify incoming and outgoing dependency query lookups."""
    engine = DependencyGraphEngine()

    engine.add_node("core", "app/core.py", "core.py", "Python")
    engine.add_node("mod1", "app/mod1.py", "mod1.py", "Python")
    engine.add_node("mod2", "app/mod2.py", "mod2.py", "Python")

    # mod1 -> core, mod2 -> core
    engine.add_dependency("mod1", "core", "FROM_IMPORT", imported_symbol="BaseEngine")
    engine.add_dependency("mod2", "core", "DIRECT_IMPORT")

    deps_core = engine.get_direct_and_reverse_dependencies("core")
    # core has 0 outbound dependencies and 2 inbound dependents (mod1, mod2)
    assert len(deps_core["dependencies"]) == 0
    assert len(deps_core["dependents"]) == 2
    dependent_paths = [d["path"] for d in deps_core["dependents"]]
    assert "app/mod1.py" in dependent_paths
    assert "app/mod2.py" in dependent_paths

    deps_mod1 = engine.get_direct_and_reverse_dependencies("mod1")
    assert len(deps_mod1["dependencies"]) == 1
    assert deps_mod1["dependencies"][0]["path"] == "app/core.py"

