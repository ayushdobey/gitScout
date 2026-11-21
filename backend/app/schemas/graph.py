from typing import Any, Dict, List

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    label: str
    path: str
    language: str
    is_entry_point: bool = False
    in_degree: int = 0
    out_degree: int = 0
    pagerank: float = 0.0
    x: float = 0.0
    y: float = 0.0
    group: str | None = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    dependency_type: str = "DIRECT_IMPORT"
    imported_symbol: str | None = None
    is_circular: bool = False


class GraphMetrics(BaseModel):
    total_nodes: int
    total_edges: int
    density: float
    is_dag: bool
    circular_dependencies: List[List[str]] = []
    hub_modules: List[Dict[str, Any]] = []
    isolated_modules: List[str] = []


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    metrics: GraphMetrics


class GraphPathResponse(BaseModel):
    source_id: str
    target_id: str
    source_path: str
    target_path: str
    path: List[str] = []
    is_reachable: bool = False


class NodeDependenciesResponse(BaseModel):
    file_id: str
    path: str
    dependencies: List[Dict[str, Any]] = []  # Modules imported by this file
    dependents: List[Dict[str, Any]] = []    # Modules that import this file
