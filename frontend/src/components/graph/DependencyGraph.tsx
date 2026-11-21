'use client';

import React, { useState, useMemo, useCallback } from 'react';
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { FileNode } from './FileNode';
import { GraphResponse, GraphNodeData } from '@/types/api';
import {
  Search,
  Filter,
  RefreshCw,
  GitCommit,
  AlertTriangle,
  ArrowRight,
  Route,
  Layers,
  Sparkles,
  Info,
  CheckCircle2,
  X
} from 'lucide-react';

interface DependencyGraphProps {
  graphData: GraphResponse;
  onRefresh?: () => void;
}

const nodeTypes = {
  fileNode: FileNode,
};

export function DependencyGraph({ graphData, onRefresh }: DependencyGraphProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [hideIsolated, setHideIsolated] = useState(false);
  const [onlyCycles, setOnlyCycles] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Path Exploration state
  const [pathSource, setPathSource] = useState<string>('');
  const [pathTarget, setPathTarget] = useState<string>('');
  const [activePath, setActivePath] = useState<string[]>([]);

  // Collect circular file paths
  const circularPathSet = useMemo(() => {
    const set = new Set<string>();
    graphData.metrics.circular_dependencies.forEach((cycle) => {
      cycle.forEach((p) => set.add(p));
    });
    return set;
  }, [graphData.metrics.circular_dependencies]);

  // Convert API nodes to React Flow nodes
  const initialNodes: Node[] = useMemo(() => {
    return graphData.nodes
      .filter((n) => {
        if (hideIsolated && n.in_degree === 0 && n.out_degree === 0) return false;
        if (onlyCycles && !circularPathSet.has(n.path)) return false;
        if (searchQuery && !n.path.toLowerCase().includes(searchQuery.toLowerCase())) return false;
        return true;
      })
      .map((n) => ({
        id: n.id,
        type: 'fileNode',
        position: { x: n.x ?? 100, y: n.y ?? 100 },
        data: {
          ...n,
          is_in_path: activePath.includes(n.path),
        },
      }));
  }, [graphData.nodes, hideIsolated, onlyCycles, searchQuery, circularPathSet, activePath]);

  // Convert API edges to React Flow edges
  const initialEdges: Edge[] = useMemo(() => {
    const visibleNodeIds = new Set(initialNodes.map((n) => n.id));
    return graphData.edges
      .filter((e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target))
      .map((e) => {
        const isCircular = e.is_circular;
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          animated: isCircular || activePath.length > 0,
          style: {
            stroke: isCircular ? '#f43f5e' : '#38bdf8',
            strokeWidth: isCircular ? 2.5 : 1.5,
            strokeDasharray: isCircular ? '5 5' : undefined,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 14,
            height: 14,
            color: isCircular ? '#f43f5e' : '#38bdf8',
          },
          label: e.imported_symbol ? `import ${e.imported_symbol}` : undefined,
          labelStyle: { fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' },
          labelBgStyle: { fill: '#0f172a', fillOpacity: 0.8 },
        };
      });
  }, [graphData.edges, initialNodes, activePath]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync state when filters change
  React.useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  // Node selection handler
  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id);
  }, []);

  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    return graphData.nodes.find((n) => n.id === selectedNodeId) || null;
  }, [selectedNodeId, graphData.nodes]);

  // Direct dependencies (what selected node imports)
  const directDependencies = useMemo(() => {
    if (!selectedNodeId) return [];
    const targetIds = graphData.edges.filter((e) => e.source === selectedNodeId).map((e) => e.target);
    return graphData.nodes.filter((n) => targetIds.includes(n.id));
  }, [selectedNodeId, graphData.edges, graphData.nodes]);

  // Reverse dependents (what files import selected node)
  const reverseDependents = useMemo(() => {
    if (!selectedNodeId) return [];
    const sourceIds = graphData.edges.filter((e) => e.target === selectedNodeId).map((e) => e.source);
    return graphData.nodes.filter((n) => sourceIds.includes(n.id));
  }, [selectedNodeId, graphData.edges, graphData.nodes]);

  // Path exploration simulation
  const handleTracePath = () => {
    if (!pathSource || !pathTarget) return;
    // Simple BFS to find directed path on client
    const adj = new Map<string, string[]>();
    graphData.edges.forEach((e) => {
      if (!adj.has(e.source)) adj.set(e.source, []);
      adj.get(e.source)!.push(e.target);
    });

    const queue: string[][] = [[pathSource]];
    const visited = new Set<string>([pathSource]);
    let foundPath: string[] = [];

    while (queue.length > 0) {
      const currentPath = queue.shift()!;
      const last = currentPath[currentPath.length - 1];
      if (last === pathTarget) {
        foundPath = currentPath;
        break;
      }
      const neighbors = adj.get(last) || [];
      for (const next of neighbors) {
        if (!visited.has(next)) {
          visited.add(next);
          queue.push([...currentPath, next]);
        }
      }
    }

    if (foundPath.length > 0) {
      const pathPaths = foundPath.map((id) => graphData.nodes.find((n) => n.id === id)?.path || id);
      setActivePath(pathPaths);
    } else {
      setActivePath([]);
      alert('No direct dependency path found between selected modules.');
    }
  };

  const clearPath = () => {
    setActivePath([]);
    setPathSource('');
    setPathTarget('');
  };

  return (
    <div className="relative flex h-[760px] w-full flex-col overflow-hidden rounded-xl border border-neutral-800 bg-neutral-950 text-neutral-100 shadow-2xl">
      {/* Top Toolbar */}
      <div className="z-10 flex flex-wrap items-center justify-between gap-3 border-b border-neutral-800/80 bg-neutral-900/90 px-4 py-3 backdrop-blur-md">
        {/* Search */}
        <div className="flex items-center gap-2">
          <div className="relative w-64">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-neutral-400" />
            <input
              type="text"
              placeholder="Search file path..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-md border border-neutral-800 bg-neutral-950/80 py-1.5 pl-8 pr-3 text-xs text-neutral-200 placeholder-neutral-500 transition-colors focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
            />
          </div>

          {/* Filter Toggles */}
          <button
            onClick={() => setHideIsolated(!hideIsolated)}
            className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs transition-colors ${
              hideIsolated
                ? 'border-cyan-500/50 bg-cyan-950/30 text-cyan-300'
                : 'border-neutral-800 bg-neutral-900 text-neutral-400 hover:text-neutral-200'
            }`}
          >
            <Filter className="h-3 w-3" />
            <span>Hide Isolated ({graphData.metrics.isolated_modules.length})</span>
          </button>

          <button
            onClick={() => setOnlyCycles(!onlyCycles)}
            className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs transition-colors ${
              onlyCycles
                ? 'border-rose-500/50 bg-rose-950/30 text-rose-300'
                : 'border-neutral-800 bg-neutral-900 text-neutral-400 hover:text-neutral-200'
            }`}
          >
            <AlertTriangle className="h-3 w-3 text-rose-400" />
            <span>Cycles ({graphData.metrics.circular_dependencies.length})</span>
          </button>
        </div>

        {/* Path Explorer Bar */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1 text-xs">
            <Route className="h-3.5 w-3.5 text-amber-400" />
            <select
              value={pathSource}
              onChange={(e) => setPathSource(e.target.value)}
              className="bg-transparent text-xs text-neutral-300 focus:outline-none max-w-[120px] truncate"
            >
              <option value="" className="bg-neutral-900">Source Module</option>
              {graphData.nodes.map((n) => (
                <option key={n.id} value={n.id} className="bg-neutral-900">
                  {n.label}
                </option>
              ))}
            </select>

            <ArrowRight className="h-3 w-3 text-neutral-500" />

            <select
              value={pathTarget}
              onChange={(e) => setPathTarget(e.target.value)}
              className="bg-transparent text-xs text-neutral-300 focus:outline-none max-w-[120px] truncate"
            >
              <option value="" className="bg-neutral-900">Target Module</option>
              {graphData.nodes.map((n) => (
                <option key={n.id} value={n.id} className="bg-neutral-900">
                  {n.label}
                </option>
              ))}
            </select>

            <button
              onClick={handleTracePath}
              disabled={!pathSource || !pathTarget}
              className="rounded bg-amber-500/20 px-2 py-0.5 text-[11px] font-medium text-amber-300 hover:bg-amber-500/30 disabled:opacity-40"
            >
              Trace
            </button>

            {activePath.length > 0 && (
              <button onClick={clearPath} className="text-neutral-400 hover:text-neutral-200">
                <X className="h-3 w-3" />
              </button>
            )}
          </div>
        </div>

        {/* Metrics Summary Badges */}
        <div className="flex items-center gap-2 font-mono text-[11px] text-neutral-400">
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-cyan-400" />
            <span>{graphData.metrics.total_nodes} Files</span>
          </span>
          <span className="text-neutral-700">•</span>
          <span>{graphData.metrics.total_edges} Edges</span>
          <span className="text-neutral-700">•</span>
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
            graphData.metrics.is_dag
              ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/40'
              : 'bg-rose-950/60 text-rose-400 border border-rose-800/40'
          }`}>
            {graphData.metrics.is_dag ? 'DAG (Clean)' : 'Cyclic'}
          </span>
        </div>
      </div>

      {/* Main Canvas & Detail Sidebar */}
      <div className="relative flex flex-1 overflow-hidden">
        {/* React Flow Canvas */}
        <div className="h-full flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            nodeTypes={nodeTypes}
            fitView
            colorMode="dark"
            minZoom={0.2}
            maxZoom={2.0}
            defaultEdgeOptions={{
              type: 'smoothstep',
            }}
          >
            <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="#334155" />
            <Controls className="!border-neutral-800 !bg-neutral-900/90 !text-neutral-300" />
            <MiniMap
              className="!border !border-neutral-800 !bg-neutral-950/90"
              nodeColor={(n) => {
                const nodeData = n.data as unknown as GraphNodeData;
                if (nodeData.is_entry_point) return '#10b981';
                if (nodeData.in_degree > 0 && nodeData.out_degree > 0) return '#f43f5e';
                return '#38bdf8';
              }}
              maskColor="rgba(15, 23, 42, 0.75)"
            />
          </ReactFlow>
        </div>

        {/* Selected Node Inspector Sidebar */}
        {selectedNode && (
          <div className="z-10 w-80 shrink-0 border-l border-neutral-800 bg-neutral-900/95 p-4 backdrop-blur-md overflow-y-auto">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <div className="flex items-center gap-2">
                <Info className="h-4 w-4 text-cyan-400" />
                <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-300">
                  Module Inspector
                </h3>
              </div>
              <button onClick={() => setSelectedNodeId(null)} className="text-neutral-500 hover:text-neutral-300">
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* File Details */}
            <div className="mt-3 space-y-2">
              <div>
                <span className="text-[10px] text-neutral-500 uppercase tracking-wider">File Path</span>
                <p className="font-mono text-xs text-neutral-200 break-all">{selectedNode.path}</p>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-2">
                <div className="rounded border border-neutral-800 bg-neutral-950/60 p-2">
                  <span className="text-[10px] text-neutral-500">In-Degree (Fan-In)</span>
                  <p className="font-mono text-sm font-semibold text-cyan-400">
                    {selectedNode.in_degree}
                  </p>
                </div>
                <div className="rounded border border-neutral-800 bg-neutral-950/60 p-2">
                  <span className="text-[10px] text-neutral-500">Out-Degree (Fan-Out)</span>
                  <p className="font-mono text-sm font-semibold text-violet-400">
                    {selectedNode.out_degree}
                  </p>
                </div>
              </div>

              <div className="rounded border border-neutral-800 bg-neutral-950/60 p-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-neutral-500">PageRank Score</span>
                  <span className="font-mono text-xs font-medium text-neutral-200">
                    {selectedNode.pagerank.toFixed(4)}
                  </span>
                </div>
              </div>
            </div>

            {/* Direct Dependencies */}
            <div className="mt-5">
              <h4 className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
                Direct Dependencies ({directDependencies.length})
              </h4>
              <p className="text-[10px] text-neutral-500">Files imported by this module</p>
              <div className="mt-2 space-y-1.5 max-h-40 overflow-y-auto">
                {directDependencies.length === 0 ? (
                  <p className="text-xs text-neutral-500 italic">No internal dependencies</p>
                ) : (
                  directDependencies.map((d) => (
                    <div
                      key={d.id}
                      onClick={() => setSelectedNodeId(d.id)}
                      className="cursor-pointer rounded border border-neutral-800/80 bg-neutral-950/50 p-2 hover:border-neutral-700"
                    >
                      <p className="font-mono text-xs text-cyan-300 truncate">{d.label}</p>
                      <p className="font-mono text-[10px] text-neutral-500 truncate">{d.path}</p>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Reverse Dependents */}
            <div className="mt-5">
              <h4 className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
                Reverse Dependents ({reverseDependents.length})
              </h4>
              <p className="text-[10px] text-neutral-500">Modules importing this file</p>
              <div className="mt-2 space-y-1.5 max-h-40 overflow-y-auto">
                {reverseDependents.length === 0 ? (
                  <p className="text-xs text-neutral-500 italic">No internal dependents</p>
                ) : (
                  reverseDependents.map((d) => (
                    <div
                      key={d.id}
                      onClick={() => setSelectedNodeId(d.id)}
                      className="cursor-pointer rounded border border-neutral-800/80 bg-neutral-950/50 p-2 hover:border-neutral-700"
                    >
                      <p className="font-mono text-xs text-violet-300 truncate">{d.label}</p>
                      <p className="font-mono text-[10px] text-neutral-500 truncate">{d.path}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

