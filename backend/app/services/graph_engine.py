from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple

import networkx as nx


@dataclass
class GraphAnalysisResult:
    total_nodes: int
    total_edges: int
    density: float
    is_dag: bool
    circular_dependencies: List[List[str]]  # Lists of file paths forming cycles
    circular_edge_tuples: Set[Tuple[str, str]]  # Set of (source_id, target_id)
    hub_modules: List[Dict[str, Any]]  # Top connected modules by degree & PageRank
    isolated_modules: List[str]  # File paths with 0 connections
    node_metrics: Dict[str, Dict[str, Any]]  # file_id -> {in_degree, out_degree, pagerank, x, y}


class DependencyGraphEngine:
    """
    Graph theory analysis engine utilizing NetworkX.
    Constructs directed graph G=(V, E), evaluates circular dependencies via Tarjan's SCC,
    computes PageRank and centrality metrics, and generates layout coordinates for React Flow.
    """
    def __init__(self):
        self.graph = nx.DiGraph()
        self.file_metadata: Dict[str, Dict[str, Any]] = {}

    def add_node(
        self,
        file_id: str,
        path: str,
        filename: str,
        language: str,
        is_entry_point: bool = False,
        line_count: int = 0
    ):
        """Add a file node with metadata attributes."""
        self.graph.add_node(file_id)
        self.file_metadata[file_id] = {
            "id": file_id,
            "path": path,
            "filename": filename,
            "language": language,
            "is_entry_point": is_entry_point,
            "line_count": line_count
        }

    def add_dependency(
        self,
        source_id: str,
        target_id: str,
        dependency_type: str = "DIRECT_IMPORT",
        imported_symbol: str | None = None,
        line_number: int = 1
    ):
        """Add a directed import edge (source -> target)."""
        if source_id != target_id:  # Exclude self-loops from graph edge insertion
            self.graph.add_edge(
                source_id,
                target_id,
                dependency_type=dependency_type,
                imported_symbol=imported_symbol,
                line_number=line_number
            )

    def analyze(self) -> GraphAnalysisResult:
        """
        Execute comprehensive graph theory analytics:
        - Strongly Connected Components (SCC) for cycle detection
        - PageRank for architectural chokepoint detection
        - In-degree (fan-in / reuse) and out-degree (fan-out / coupling)
        - Spring layout coordinates (scaled for React Flow canvas)
        """
        num_nodes = self.graph.number_of_nodes()
        num_edges = self.graph.number_of_edges()

        if num_nodes == 0:
            return GraphAnalysisResult(
                total_nodes=0,
                total_edges=0,
                density=0.0,
                is_dag=True,
                circular_dependencies=[],
                circular_edge_tuples=set(),
                hub_modules=[],
                isolated_modules=[],
                node_metrics={}
            )

        density = round(nx.density(self.graph), 4)
        is_dag = nx.is_directed_acyclic_graph(self.graph)

        # 1. Circular Dependency Detection via Tarjan's SCC
        circular_cycles: List[List[str]] = []
        circular_edges: Set[Tuple[str, str]] = set()

        if not is_dag:
            sccs = list(nx.strongly_connected_components(self.graph))
            for scc in sccs:
                if len(scc) > 1:
                    # Collect file paths participating in the circular cycle
                    cycle_paths = [self.file_metadata[nid]["path"] for nid in scc if nid in self.file_metadata]
                    circular_cycles.append(cycle_paths)

                    # Mark all edges between nodes in this SCC as circular
                    subgraph = self.graph.subgraph(scc)
                    for u, v in subgraph.edges():
                        circular_edges.add((u, v))

        # 2. Centrality & Metrics
        in_degrees = dict(self.graph.in_degree())
        out_degrees = dict(self.graph.out_degree())

        try:
            pageranks = nx.pagerank(self.graph, alpha=0.85, max_iter=100)
        except Exception:
            # Fallback uniform score if power iteration fails to converge
            pageranks = {node: round(1.0 / num_nodes, 4) for node in self.graph.nodes()}

        # 3. Automatic 2D Layout Coordinates for React Flow
        # Use multipartite/topological layers if DAG, or spring layout
        positions: Dict[str, Tuple[float, float]] = {}
        try:
            # Spring layout simulation gives visually pleasant force-directed node distributions
            raw_pos = nx.spring_layout(self.graph, k=2.0 / (num_nodes ** 0.5 if num_nodes > 0 else 1.0), seed=42)
            # Scale coordinates for React Flow (spread across 1600 x 900 canvas)
            for nid, (x, y) in raw_pos.items():
                positions[nid] = (round((x + 1.0) * 800, 1), round((y + 1.0) * 450, 1))
        except Exception:
            # Grid fallback
            cols = max(1, int(num_nodes ** 0.5))
            for idx, nid in enumerate(self.graph.nodes()):
                r, c = divmod(idx, cols)
                positions[nid] = (c * 280.0, r * 160.0)

        # 4. Compile Per-Node Metrics
        node_metrics: Dict[str, Dict[str, Any]] = {}
        isolated_paths: List[str] = []

        for nid in self.graph.nodes():
            meta = self.file_metadata.get(nid, {})
            in_d = in_degrees.get(nid, 0)
            out_d = out_degrees.get(nid, 0)
            pr = round(pageranks.get(nid, 0.0), 4)
            pos = positions.get(nid, (0.0, 0.0))

            if in_d == 0 and out_d == 0 and "path" in meta:
                isolated_paths.append(meta["path"])

            node_metrics[nid] = {
                "in_degree": in_d,
                "out_degree": out_d,
                "pagerank": pr,
                "x": pos[0],
                "y": pos[1]
            }

        # 5. Identify Top Hub Modules (High PageRank / In-Degree)
        sorted_hubs = sorted(
            [
                {
                    "file_id": nid,
                    "path": self.file_metadata[nid]["path"],
                    "filename": self.file_metadata[nid]["filename"],
                    "in_degree": in_degrees.get(nid, 0),
                    "out_degree": out_degrees.get(nid, 0),
                    "pagerank": round(pageranks.get(nid, 0.0), 4)
                }
                for nid in self.graph.nodes()
                if in_degrees.get(nid, 0) > 0 or out_degrees.get(nid, 0) > 0
            ],
            key=lambda item: (item["in_degree"], item["pagerank"]),
            reverse=True
        )[:8]

        return GraphAnalysisResult(
            total_nodes=num_nodes,
            total_edges=num_edges,
            density=density,
            is_dag=is_dag,
            circular_dependencies=circular_cycles,
            circular_edge_tuples=circular_edges,
            hub_modules=sorted_hubs,
            isolated_modules=isolated_paths,
            node_metrics=node_metrics
        )

    def find_shortest_path(self, source_id: str, target_id: str) -> List[str] | None:
        """
        Find shortest dependency path from source_id to target_id.
        Returns list of file paths along the directed path, or None if unreachable.
        """
        if not self.graph.has_node(source_id) or not self.graph.has_node(target_id):
            return None
        try:
            node_path = nx.shortest_path(self.graph, source=source_id, target=target_id)
            return [self.file_metadata[nid]["path"] for nid in node_path if nid in self.file_metadata]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def get_direct_and_reverse_dependencies(self, file_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Returns:
        - dependencies: files imported by this file (outbound edges)
        - dependents: files that import this file (inbound edges)
        """
        if not self.graph.has_node(file_id):
            return {"dependencies": [], "dependents": []}

        outbound = []
        for target_id in self.graph.successors(file_id):
            edge_data = self.graph.get_edge_data(file_id, target_id, {})
            outbound.append({
                "file_id": target_id,
                "path": self.file_metadata.get(target_id, {}).get("path", target_id),
                "filename": self.file_metadata.get(target_id, {}).get("filename", target_id),
                "imported_symbol": edge_data.get("imported_symbol"),
                "dependency_type": edge_data.get("dependency_type")
            })

        inbound = []
        for source_id in self.graph.predecessors(file_id):
            edge_data = self.graph.get_edge_data(source_id, file_id, {})
            inbound.append({
                "file_id": source_id,
                "path": self.file_metadata.get(source_id, {}).get("path", source_id),
                "filename": self.file_metadata.get(source_id, {}).get("filename", source_id),
                "imported_symbol": edge_data.get("imported_symbol"),
                "dependency_type": edge_data.get("dependency_type")
            })

        return {"dependencies": outbound, "dependents": inbound}
