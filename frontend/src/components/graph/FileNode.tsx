'use client';

import React, { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { FileCode, AlertTriangle, Play, Share2 } from 'lucide-react';
import { GraphNodeData } from '@/types/api';

export const FileNode = memo(({ data, selected }: NodeProps) => {
  const nodeData = data as unknown as GraphNodeData;
  const isEntryPoint = nodeData.is_entry_point;
  const isInPath = nodeData.is_in_path;
  const isCircular = nodeData.in_degree > 0 && nodeData.out_degree > 0;

  return (
    <div
      className={`relative min-w-[240px] max-w-[280px] rounded-lg border bg-neutral-900/95 p-3.5 shadow-xl backdrop-blur-md transition-all duration-200 ${
        selected
          ? 'border-cyan-400 ring-2 ring-cyan-400/30'
          : isInPath
          ? 'border-amber-400 ring-2 ring-amber-400/40'
          : isEntryPoint
          ? 'border-emerald-500/80 bg-neutral-900/95 shadow-emerald-500/10'
          : 'border-neutral-800 hover:border-neutral-700'
      }`}
    >
      {/* Target Handle (Incoming Imports) */}
      <Handle
        type="target"
        position={Position.Top}
        className="!h-2.5 !w-2.5 !border-neutral-900 !bg-cyan-400"
      />

      {/* Header with filename and entry badge */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 overflow-hidden">
          <div
            className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md border ${
              isEntryPoint
                ? 'border-emerald-500/30 bg-emerald-950/40 text-emerald-400'
                : 'border-neutral-700/50 bg-neutral-800/60 text-neutral-300'
            }`}
          >
            {isEntryPoint ? <Play className="h-3.5 w-3.5 fill-current" /> : <FileCode className="h-3.5 w-3.5" />}
          </div>
          <div className="truncate">
            <h4 className="truncate text-xs font-semibold text-neutral-100" title={nodeData.label}>
              {nodeData.label}
            </h4>
            <p className="truncate font-mono text-[10px] text-neutral-400" title={nodeData.path}>
              {nodeData.path}
            </p>
          </div>
        </div>

        {isEntryPoint && (
          <span className="shrink-0 rounded border border-emerald-500/30 bg-emerald-950/50 px-1.5 py-0.5 text-[9px] font-medium text-emerald-300">
            Entry
          </span>
        )}
      </div>

      {/* Metrics Row */}
      <div className="mt-2.5 flex items-center justify-between border-t border-neutral-800/80 pt-2 text-[10px] text-neutral-400">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1 font-mono" title="In-degree (Fan-in / Modules importing this)">
            <span className="text-cyan-400 font-medium">↓ {nodeData.in_degree}</span>
          </span>
          <span className="flex items-center gap-1 font-mono" title="Out-degree (Fan-out / Modules imported by this)">
            <span className="text-violet-400 font-medium">↑ {nodeData.out_degree}</span>
          </span>
        </div>

        <div className="flex items-center gap-1.5 font-mono text-[9px] text-neutral-500" title="PageRank Architectural Centrality">
          <span>PR:</span>
          <span className="text-neutral-300 font-medium">{nodeData.pagerank?.toFixed(3) || '0.000'}</span>
        </div>
      </div>

      {/* Source Handle (Outgoing Imports) */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-2.5 !w-2.5 !border-neutral-900 !bg-violet-400"
      />
    </div>
  );
});

FileNode.displayName = 'FileNode';

