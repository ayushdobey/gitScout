'use client';

import React, { useState, useMemo } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle2,
  Search,
  Filter,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Code2
} from 'lucide-react';

export interface FindingItem {
  id: string;
  tool: 'RUFF' | 'BANDIT';
  rule_id: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  category: string;
  description: string;
  file_path: string;
  line_number: number;
  snippet?: string;
  remediation_hint?: string;
}

const DEMO_FINDINGS: FindingItem[] = [
  {
    id: 'f1',
    tool: 'BANDIT',
    rule_id: 'B101',
    severity: 'MEDIUM',
    category: 'SECURITY',
    description: 'Use of assert detected. The assert statement is removed when compiled to optimized byte code.',
    file_path: 'src/flask/app.py',
    line_number: 142,
    snippet: 'assert endpoint is not None, "Endpoint must not be empty"',
    remediation_hint: 'Use explicit ValueError checks instead of assert in production code paths.'
  },
  {
    id: 'f2',
    tool: 'BANDIT',
    rule_id: 'B608',
    severity: 'HIGH',
    category: 'INJECTION',
    description: 'Potential SQL injection risk with formatted string execution.',
    file_path: 'src/flask/sessions.py',
    line_number: 89,
    snippet: 'cursor.execute(f"SELECT * FROM sessions WHERE id = {session_id}")',
    remediation_hint: 'Use parameterized queries: cursor.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))'
  },
  {
    id: 'f3',
    tool: 'RUFF',
    rule_id: 'F401',
    severity: 'LOW',
    category: 'STYLE',
    description: '`typing.Union` imported but unused in module preamble.',
    file_path: 'src/flask/helpers.py',
    line_number: 14,
    snippet: 'from typing import List, Dict, Union',
    remediation_hint: 'Remove unused typing import or refactor using Python 3.10+ pipe union syntax (X | Y).'
  },
  {
    id: 'f4',
    tool: 'RUFF',
    rule_id: 'E501',
    severity: 'LOW',
    category: 'STYLE',
    description: 'Line too long (128 > 120 characters).',
    file_path: 'src/flask/blueprints.py',
    line_number: 215,
    snippet: 'def register_blueprint(self, blueprint: Blueprint, url_prefix: Optional[str] = None, subdomain: Optional[str] = None):',
    remediation_hint: 'Break arguments onto separate lines to maintain clean readability.'
  },
  {
    id: 'f5',
    tool: 'RUFF',
    rule_id: 'C901',
    severity: 'MEDIUM',
    category: 'COMPLEXITY',
    description: 'Function `wsgi_app` has high cyclomatic complexity (score: 14).',
    file_path: 'src/flask/app.py',
    line_number: 2090,
    snippet: 'def wsgi_app(self, environ, start_response):',
    remediation_hint: 'Decompose dispatch branching into modular middleware pipelines.'
  }
];

export function FindingsTable({ findings = DEMO_FINDINGS }: { findings?: FindingItem[] }) {
  const [selectedSeverity, setSelectedSeverity] = useState<string>('ALL');
  const [selectedTool, setSelectedTool] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const counts = useMemo(() => {
    const c = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, RUFF: 0, BANDIT: 0 };
    findings.forEach((f) => {
      if (f.severity in c) (c as any)[f.severity]++;
      if (f.tool in c) (c as any)[f.tool]++;
    });
    return c;
  }, [findings]);

  const filteredFindings = useMemo(() => {
    return findings.filter((f) => {
      if (selectedSeverity !== 'ALL' && f.severity !== selectedSeverity) return false;
      if (selectedTool !== 'ALL' && f.tool !== selectedTool) return false;
      if (
        searchQuery &&
        !f.description.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !f.file_path.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !f.rule_id.toLowerCase().includes(searchQuery.toLowerCase())
      ) {
        return false;
      }
      return true;
    });
  }, [findings, selectedSeverity, selectedTool, searchQuery]);

  return (
    <div className="space-y-6">
      {/* Metric Cards Row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-xl border border-rose-900/30 bg-rose-950/20 p-4">
          <div className="flex items-center justify-between text-rose-400">
            <span className="text-xs font-semibold">Critical Vulnerabilities</span>
            <ShieldAlert className="h-4 w-4" />
          </div>
          <p className="mt-2 text-2xl font-bold tracking-tight text-rose-300">{counts.CRITICAL}</p>
          <span className="text-[11px] text-rose-400/80">Immediate remediation needed</span>
        </div>

        <div className="rounded-xl border border-orange-900/30 bg-orange-950/20 p-4">
          <div className="flex items-center justify-between text-orange-400">
            <span className="text-xs font-semibold">High Severity</span>
            <AlertTriangle className="h-4 w-4" />
          </div>
          <p className="mt-2 text-2xl font-bold tracking-tight text-orange-300">{counts.HIGH}</p>
          <span className="text-[11px] text-orange-400/80">Injection / security exposure</span>
        </div>

        <div className="rounded-xl border border-amber-900/30 bg-amber-950/20 p-4">
          <div className="flex items-center justify-between text-amber-400">
            <span className="text-xs font-semibold">Medium Severity</span>
            <AlertCircle className="h-4 w-4" />
          </div>
          <p className="mt-2 text-2xl font-bold tracking-tight text-amber-300">{counts.MEDIUM}</p>
          <span className="text-[11px] text-amber-400/80">Complexity & assert logic</span>
        </div>

        <div className="rounded-xl border border-sky-900/30 bg-sky-950/20 p-4">
          <div className="flex items-center justify-between text-sky-400">
            <span className="text-xs font-semibold">Low / Style Smells</span>
            <Info className="h-4 w-4" />
          </div>
          <p className="mt-2 text-2xl font-bold tracking-tight text-sky-300">{counts.LOW}</p>
          <span className="text-[11px] text-sky-400/80">Ruff unused imports & lint</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-neutral-800 bg-neutral-900/80 p-3">
        <div className="flex items-center gap-2 flex-1 max-w-md">
          <div className="relative w-full">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-neutral-400" />
            <input
              type="text"
              placeholder="Search rule code, description, or file..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-md border border-neutral-800 bg-neutral-950 py-1.5 pl-9 pr-3 text-xs text-neutral-200 placeholder-neutral-500 focus:border-cyan-500 focus:outline-none"
            />
          </div>
        </div>

        {/* Severity Filters */}
        <div className="flex items-center gap-1.5 text-xs">
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((sev) => (
            <button
              key={sev}
              onClick={() => setSelectedSeverity(sev)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                selectedSeverity === sev
                  ? 'bg-neutral-800 text-cyan-400 border border-neutral-700'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              {sev}
            </button>
          ))}
        </div>

        {/* Tool Filter */}
        <div className="flex items-center gap-1.5 text-xs">
          {['ALL', 'RUFF', 'BANDIT'].map((tool) => (
            <button
              key={tool}
              onClick={() => setSelectedTool(tool)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                selectedTool === tool
                  ? 'bg-neutral-800 text-indigo-400 border border-neutral-700'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              {tool}
            </button>
          ))}
        </div>
      </div>

      {/* Findings List Table */}
      <div className="overflow-hidden rounded-xl border border-neutral-800 bg-neutral-950 shadow-xl">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-neutral-800 bg-neutral-900/90 text-neutral-400 font-mono text-[11px] uppercase tracking-wider">
            <tr>
              <th className="py-3 pl-4 pr-2">Severity</th>
              <th className="py-3 px-3">Tool</th>
              <th className="py-3 px-3">Rule</th>
              <th className="py-3 px-3">File Location</th>
              <th className="py-3 px-3">Description</th>
              <th className="py-3 pr-4 text-right">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-800/80 text-neutral-300">
            {filteredFindings.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-neutral-500 italic">
                  No static findings match the selected filters.
                </td>
              </tr>
            ) : (
              filteredFindings.map((f) => {
                const isExpanded = expandedId === f.id;
                return (
                  <React.Fragment key={f.id}>
                    <tr
                      onClick={() => setExpandedId(isExpanded ? null : f.id)}
                      className="cursor-pointer hover:bg-neutral-900/50 transition-colors"
                    >
                      <td className="py-3 pl-4 pr-2">
                        <span
                          className={`inline-block rounded px-2 py-0.5 font-mono text-[10px] font-semibold border ${
                            f.severity === 'CRITICAL'
                              ? 'bg-rose-950/80 text-rose-300 border-rose-800'
                              : f.severity === 'HIGH'
                              ? 'bg-orange-950/80 text-orange-300 border-orange-800'
                              : f.severity === 'MEDIUM'
                              ? 'bg-amber-950/80 text-amber-300 border-amber-800'
                              : 'bg-sky-950/80 text-sky-300 border-sky-800'
                          }`}
                        >
                          {f.severity}
                        </span>
                      </td>

                      <td className="py-3 px-3">
                        <span className="font-mono text-[11px] font-medium text-neutral-300">
                          {f.tool}
                        </span>
                      </td>

                      <td className="py-3 px-3">
                        <span className="font-mono text-cyan-400">{f.rule_id}</span>
                      </td>

                      <td className="py-3 px-3 font-mono text-neutral-400">
                        <span>{f.file_path}:{f.line_number}</span>
                      </td>

                      <td className="py-3 px-3 text-neutral-200 max-w-md truncate">
                        {f.description}
                      </td>

                      <td className="py-3 pr-4 text-right text-neutral-500">
                        {isExpanded ? <ChevronDown className="h-4 w-4 inline" /> : <ChevronRight className="h-4 w-4 inline" />}
                      </td>
                    </tr>

                    {isExpanded && (
                      <tr className="bg-neutral-900/40">
                        <td colSpan={6} className="p-4 pl-8 border-t border-neutral-800/60">
                          <div className="space-y-3">
                            {f.snippet && (
                              <div>
                                <span className="text-[10px] uppercase font-semibold text-neutral-400 tracking-wider">
                                  Affected Code Snippet (Line {f.line_number}):
                                </span>
                                <pre className="mt-1 rounded-lg border border-neutral-800 bg-neutral-950 p-3 font-mono text-xs text-rose-300 overflow-x-auto">
                                  {f.snippet}
                                </pre>
                              </div>
                            )}

                            {f.remediation_hint && (
                              <div className="rounded-lg border border-cyan-900/30 bg-cyan-950/20 p-3 text-xs text-cyan-300">
                                <strong className="font-semibold text-cyan-200">Remediation Guidance: </strong>
                                {f.remediation_hint}
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

