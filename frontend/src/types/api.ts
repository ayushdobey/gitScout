export interface GraphNodeData {
  id: string;
  label: string;
  path: string;
  language: string;
  is_entry_point: boolean;
  in_degree: number;
  out_degree: number;
  pagerank: number;
  x?: number;
  y?: number;
  is_selected?: boolean;
  is_in_path?: boolean;
}

export interface GraphEdgeData {
  id: string;
  source: string;
  target: string;
  dependency_type: string;
  imported_symbol?: string | null;
  is_circular: boolean;
  is_in_path?: boolean;
}

export interface HubModule {
  file_id: string;
  path: string;
  filename: string;
  in_degree: number;
  out_degree: number;
  pagerank: number;
}

export interface GraphMetrics {
  total_nodes: number;
  total_edges: number;
  density: number;
  is_dag: boolean;
  circular_dependencies: string[][];
  hub_modules: HubModule[];
  isolated_modules: string[];
}

export interface GraphResponse {
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  metrics: GraphMetrics;
}

export interface RepositoryData {
  id: string;
  github_url: string;
  owner: string;
  name: string;
  default_branch: string;
  stars: number;
  forks: number;
  primary_language?: string;
  status: string;
}

export interface CodeSymbol {
  id: string;
  name: string;
  symbol_type: string;
  signature?: string;
  start_line: number;
  end_line: number;
  docstring?: string;
  cyclomatic_complexity: number;
}

export interface FileRecord {
  id: string;
  path: string;
  filename: string;
  extension: string;
  language: string;
  file_size: number;
  line_count: number;
  is_entry_point: boolean;
  symbols?: CodeSymbol[];
}

