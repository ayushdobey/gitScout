'use client';

import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import { GraphMetrics, HubModule } from '@/types/api';
import { GitFork, Star, FileCode, CheckCircle2, AlertTriangle, Network } from 'lucide-react';

interface OverviewChartsProps {
  metrics: GraphMetrics;
  stars?: number;
  forks?: number;
}

const COLORS = ['#38bdf8', '#818cf8', '#34d399', '#fbbf24', '#f43f5e'];

export function OverviewCharts({ metrics, stars = 48200, forks = 14500 }: OverviewChartsProps) {
  const hubData = (metrics.hub_modules || []).slice(0, 6).map((h) => ({
    name: h.filename,
    in_degree: h.in_degree,
    out_degree: h.out_degree,
    pagerank: Math.round(h.pagerank * 1000) / 10,
  }));

  const connectivityData = [
    { name: 'Connected Files', value: metrics.total_nodes - metrics.isolated_modules.length },
    { name: 'Isolated Files', value: metrics.isolated_modules.length },
  ];

  return (
    <div className="space-y-6">
      {/* Top Metric Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-4 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-neutral-400">
            <span className="text-xs font-medium">Analyzed Files</span>
            <FileCode className="h-4 w-4 text-cyan-400" />
          </div>
          <p className="mt-2 text-2xl font-bold tracking-tight text-neutral-100">
            {metrics.total_nodes}
          </p>
          <span className="text-[11px] text-neutral-500">Deterministic AST parsed</span>
        </div>

        <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-4 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-neutral-400">
            <span className="text-xs font-medium">Dependency Edges</span>
            <Network className="h-4 w-4 text-violet-400" />
          </div>
          <p className="mt-2 text-2xl font-bold tracking-tight text-neutral-100">
            {metrics.total_edges}
          </p>
          <span className="text-[11px] text-neutral-500">File-to-file import relationships</span>
        </div>

        <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-4 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-neutral-400">
            <span className="text-xs font-medium">Graph Density</span>
            <span className="text-xs font-mono text-emerald-400">D</span>
          </div>
          <p className="mt-2 text-2xl font-bold tracking-tight text-neutral-100">
            {metrics.density}
          </p>
          <span className="text-[11px] text-neutral-500">Adjacency coupling ratio</span>
        </div>

        <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-4 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-neutral-400">
            <span className="text-xs font-medium">Circular Loops</span>
            {metrics.circular_dependencies.length > 0 ? (
              <AlertTriangle className="h-4 w-4 text-rose-400" />
            ) : (
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            )}
          </div>
          <p className={`mt-2 text-2xl font-bold tracking-tight ${metrics.circular_dependencies.length > 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
            {metrics.circular_dependencies.length}
          </p>
          <span className="text-[11px] text-neutral-500">
            {metrics.is_dag ? 'Pure DAG (No circular cycles)' : 'Architectural cycles detected'}
          </span>
        </div>
      </div>

      {/* Visual Charts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Hub Modules Degree Bar Chart */}
        <div className="lg:col-span-2 rounded-xl border border-neutral-800 bg-neutral-900/70 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-neutral-200">
            Top Architectural Hub Modules (Fan-In vs Fan-Out)
          </h3>
          <p className="text-xs text-neutral-400 mb-4">
            Modules with the highest incoming references (utility reuse) and outgoing couplings.
          </p>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={hubData}>
                <XAxis dataKey="name" stroke="#64748b" fontSize={11} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="in_degree" name="In-Degree (Fan-In)" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                <Bar dataKey="out_degree" name="Out-Degree (Fan-Out)" fill="#818cf8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Connectivity Breakdown */}
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/70 p-5 shadow-sm flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-semibold text-neutral-200">
              Module Connectivity
            </h3>
            <p className="text-xs text-neutral-400 mb-2">
              Ratio of connected core modules to isolated utility scripts.
            </p>
          </div>

          <div className="h-52 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={connectivityData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={75}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {connectivityData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="flex justify-center gap-4 text-xs text-neutral-400">
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-cyan-400" />
              <span>Connected</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-indigo-400" />
              <span>Isolated</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

