'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { DependencyGraph } from '@/components/graph/DependencyGraph';
import { OverviewCharts } from '@/components/dashboard/OverviewCharts';
import { CodebaseAssistant } from '@/components/chat/CodebaseAssistant';
import { FindingsTable, FindingItem } from '@/components/findings/FindingsTable';
import { ArchitectureReportView } from '@/components/report/ArchitectureReportView';
import { GraphResponse } from '@/types/api';
import {
  Network,
  BarChart2,
  FolderTree,
  ShieldAlert,
  Bot,
  Code2,
  FileText,
  Sparkles,
  Loader2,
  CheckCircle2,
  AlertCircle,
  XCircle,
  RefreshCw,
  GitBranch,
} from 'lucide-react';

const rawApiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_BASE = rawApiBase.replace(/\/+$/, '').replace(/\/api\/v1$/, '');
const API = `${API_BASE}/api/v1`;

function authHeaders(token: string) {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };
}

// ─── Robust Auth Helper ──────────────────────────────────────────────────────
async function ensureAuth(): Promise<string> {
  const stored = typeof window !== 'undefined' ? sessionStorage.getItem('gs_token') : null;
  if (stored) {
    try {
      const verifyResp = await fetch(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${stored}` },
      });
      if (verifyResp.ok) {
        return stored;
      }
    } catch {
      // Backend may be restarting, proceed to re-auth
    }
    if (typeof window !== 'undefined') sessionStorage.removeItem('gs_token');
  }

  // Generate a valid RFC 5322 compliant email with a valid public TLD (.io)
  const randomSuffix = Math.floor(100000 + Math.random() * 900000);
  const email = `scout_${randomSuffix}@gitscout.io`;
  const password = 'GitScout2026!';

  // 1. Register
  const regResp = await fetch(`${API}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, full_name: 'GitScout User' }),
  });

  // 2. Login
  const loginResp = await fetch(`${API}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!loginResp.ok) {
    const errBody = await loginResp.json().catch(() => ({}));
    throw new Error(errBody.detail || 'Authentication failed: unable to establish backend session.');
  }

  const loginData = await loginResp.json();
  const token: string = loginData.access_token;
  if (typeof window !== 'undefined') sessionStorage.setItem('gs_token', token);
  return token;
}

// ─── Status badge ───────────────────────────────────────────────────────────
type AnalysisPhase =
  | 'idle'
  | 'authenticating'
  | 'submitting'
  | 'PENDING'
  | 'INGESTING'
  | 'PARSING'
  | 'GRAPHING'
  | 'EMBEDDING'
  | 'AUDITING'
  | 'COMPLETED'
  | 'FAILED';

const PHASE_LABELS: Record<string, string> = {
  idle: 'Ready',
  authenticating: 'Authenticating session…',
  submitting: 'Submitting repository to engine…',
  PENDING: 'Queued for background analysis…',
  INGESTING: 'Downloading & extracting repository tarball…',
  PARSING: 'Parsing Abstract Syntax Tree (AST) & imports…',
  GRAPHING: 'Constructing directed dependency graph (NetworkX)…',
  EMBEDDING: 'Computing vector embeddings & chunking…',
  AUDITING: 'Running security & code quality audit (Ruff & Bandit)…',
  COMPLETED: 'Analysis complete ✓',
  FAILED: 'Analysis failed',
};

const PHASE_PROGRESS: Record<string, number> = {
  idle: 0,
  authenticating: 5,
  submitting: 15,
  PENDING: 25,
  INGESTING: 40,
  PARSING: 60,
  GRAPHING: 75,
  EMBEDDING: 85,
  AUDITING: 92,
  COMPLETED: 100,
  FAILED: 100,
};

function StatusBadge({ phase }: { phase: AnalysisPhase }) {
  if (phase === 'idle') return null;
  const progress = PHASE_PROGRESS[phase] ?? 0;
  const isRunning = !['idle', 'COMPLETED', 'FAILED'].includes(phase);
  const isFailed = phase === 'FAILED';
  const isCompleted = phase === 'COMPLETED';

  return (
    <div className="w-full rounded-lg border border-neutral-800 bg-neutral-900/90 p-3 shadow-lg">
      <div className="flex items-center gap-2 text-xs">
        {isRunning && <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-400" />}
        {isCompleted && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />}
        {isFailed && <XCircle className="h-3.5 w-3.5 text-rose-400" />}
        <span className={isRunning ? 'text-cyan-300 font-medium' : isFailed ? 'text-rose-400 font-medium' : 'text-emerald-400 font-medium'}>
          {PHASE_LABELS[phase]}
        </span>
        <span className="ml-auto font-mono text-neutral-400">{progress}%</span>
      </div>
      <div className="mt-2 h-1.5 w-full rounded-full bg-neutral-800 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${
            isFailed ? 'bg-rose-500' : isCompleted ? 'bg-emerald-500' : 'bg-cyan-500'
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

// ─── Main Page Component ────────────────────────────────────────────────────
export default function Home() {
  const [repoUrl, setRepoUrl] = useState('');
  const [activeTab, setActiveTab] = useState<'graph' | 'overview' | 'explorer' | 'security' | 'report' | 'assistant'>('graph');
  const [phase, setPhase] = useState<AnalysisPhase>('idle');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [graphData, setGraphData] = useState<GraphResponse | null>(null);
  const [findings, setFindings] = useState<FindingItem[]>([]);
  const [reportMarkdown, setReportMarkdown] = useState<string>('');
  const [repoId, setRepoId] = useState<string | null>(null);
  const [repoMeta, setRepoMeta] = useState<{ owner: string; name: string; branch: string; stars?: number; forks?: number } | null>(null);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tokenRef = useRef<string | null>(null);

  // Pre-authenticate session on mount
  useEffect(() => {
    ensureAuth()
      .then((t) => {
        tokenRef.current = t;
      })
      .catch((e) => console.warn('Background auth initialization:', e));

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const loadAllRepoData = useCallback(async (rid: string, token: string) => {
    try {
      // 1. Fetch Graph
      const graphResp = await fetch(`${API}/repo/${rid}/graph`, {
        headers: authHeaders(token),
      });
      if (graphResp.ok) {
        const gData: GraphResponse = await graphResp.json();
        setGraphData(gData);
      }

      // 2. Fetch Findings
      const findingsResp = await fetch(`${API}/repo/${rid}/findings`, {
        headers: authHeaders(token),
      });
      if (findingsResp.ok) {
        const fData = await findingsResp.json();
        if (Array.isArray(fData)) {
          setFindings(fData);
        }
      }

      // 3. Fetch Architecture Report Markdown
      const reportResp = await fetch(`${API}/repo/${rid}/report?format=markdown`, {
        headers: authHeaders(token),
      });
      if (reportResp.ok) {
        const mdText = await reportResp.text();
        setReportMarkdown(mdText);
      }
    } catch (err) {
      console.error('Failed to load repository workspace data:', err);
    }
  }, []);

  const pollAnalysisStatus = useCallback(
    (runId: string, rid: string, token: string) => {
      if (pollingRef.current) clearInterval(pollingRef.current);

      pollingRef.current = setInterval(async () => {
        try {
          const resp = await fetch(`${API}/analysis/${runId}/status`, {
            headers: authHeaders(token),
          });
          if (!resp.ok) return;

          const data = await resp.json();
          const st = data.status as AnalysisPhase;
          setPhase(st);

          if (st === 'COMPLETED') {
            if (pollingRef.current) clearInterval(pollingRef.current);
            pollingRef.current = null;
            await loadAllRepoData(rid, token);
          } else if (st === 'FAILED') {
            if (pollingRef.current) clearInterval(pollingRef.current);
            pollingRef.current = null;
            setErrorMsg(data.error_message || 'The analysis pipeline failed to complete.');
          }
        } catch {
          // Transient network blip — keep polling
        }
      }, 1500);
    },
    [loadAllRepoData]
  );

  const triggerReanalysis = async () => {
    if (!repoId) return;
    try {
      const token = tokenRef.current || (await ensureAuth());
      tokenRef.current = token;
      setPhase('PENDING');
      setErrorMsg(null);

      const reResp = await fetch(`${API}/repositories/${repoId}/analyze`, {
        method: 'POST',
        headers: authHeaders(token),
      });
      if (!reResp.ok) throw new Error('Failed to trigger re-analysis.');

      const runsResp = await fetch(`${API}/analysis/repo/${repoId}/runs`, {
        headers: authHeaders(token),
      });
      if (runsResp.ok) {
        const runs = await runsResp.json();
        if (runs.length > 0) {
          pollAnalysisStatus(runs[0].id, repoId, token);
        }
      }
    } catch (err: unknown) {
      setPhase('FAILED');
      setErrorMsg(err instanceof Error ? err.message : 'Failed to re-analyze repository.');
    }
  };

  const handleAnalyze = async (e?: React.FormEvent, overrideUrl?: string) => {
    if (e) e.preventDefault();
    const targetUrl = (overrideUrl || repoUrl).trim();
    if (!targetUrl) return;

    if (overrideUrl) setRepoUrl(overrideUrl);
    setPhase('authenticating');
    setErrorMsg(null);
    setGraphData(null);
    setFindings([]);
    setReportMarkdown('');
    setRepoId(null);
    setRepoMeta(null);
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }

    try {
      // 1. Authenticate with backend
      const token = await ensureAuth();
      tokenRef.current = token;

      // 2. Submit repository URL
      setPhase('submitting');
      const repoResp = await fetch(`${API}/repositories/`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({ github_url: targetUrl }),
      });

      if (!repoResp.ok) {
        const errBody = await repoResp.json().catch(() => ({}));
        throw new Error(errBody.detail || `Repository registration failed (${repoResp.status}).`);
      }

      const repo = await repoResp.json();
      setRepoId(repo.id);
      setRepoMeta({
        owner: repo.owner,
        name: repo.name,
        branch: repo.default_branch,
        stars: repo.stars,
        forks: repo.forks,
      });

      // 3. Inspect existing runs
      const runsResp = await fetch(`${API}/analysis/repo/${repo.id}/runs`, {
        headers: authHeaders(token),
      });

      if (runsResp.ok) {
        const runs = await runsResp.json();
        if (runs.length > 0) {
          const latestRun = runs[0];

          if (latestRun.status === 'COMPLETED') {
            setPhase('COMPLETED');
            await loadAllRepoData(repo.id, token);
            return;
          }

          if (latestRun.status === 'FAILED') {
            // Trigger fresh run
            setPhase('PENDING');
            const reResp = await fetch(`${API}/repositories/${repo.id}/analyze`, {
              method: 'POST',
              headers: authHeaders(token),
            });
            if (reResp.ok) {
              const freshRuns = await (await fetch(`${API}/analysis/repo/${repo.id}/runs`, { headers: authHeaders(token) })).json();
              if (freshRuns.length > 0) {
                pollAnalysisStatus(freshRuns[0].id, repo.id, token);
              }
            } else {
              setPhase('FAILED');
              setErrorMsg(latestRun.error_message || 'Previous analysis failed.');
            }
            return;
          }

          // In-progress run
          setPhase(latestRun.status as AnalysisPhase);
          pollAnalysisStatus(latestRun.id, repo.id, token);
          return;
        }
      }

      // If no runs exist, trigger initial analysis
      const reResp = await fetch(`${API}/repositories/${repo.id}/analyze`, {
        method: 'POST',
        headers: authHeaders(token),
      });
      if (reResp.ok) {
        const freshRuns = await (await fetch(`${API}/analysis/repo/${repo.id}/runs`, { headers: authHeaders(token) })).json();
        if (freshRuns.length > 0) {
          pollAnalysisStatus(freshRuns[0].id, repo.id, token);
        }
      }
    } catch (err: unknown) {
      setPhase('FAILED');
      setErrorMsg(err instanceof Error ? err.message : 'An unexpected error occurred.');
    }
  };

  const hasResults = graphData !== null;
  const displayName = repoMeta ? `${repoMeta.owner}/${repoMeta.name}` : 'GitScout';
  const displayBranch = repoMeta?.branch || 'main';

  const tabs = [
    { key: 'graph' as const, label: 'Dependency Graph', icon: Network, color: 'cyan' },
    { key: 'overview' as const, label: 'Architecture Analytics', icon: BarChart2, color: 'cyan' },
    { key: 'explorer' as const, label: 'Code Explorer', icon: FolderTree, color: 'cyan' },
    { key: 'security' as const, label: 'Quality & Security', icon: ShieldAlert, color: 'rose' },
    { key: 'report' as const, label: 'Architecture Report', icon: FileText, color: 'cyan' },
    { key: 'assistant' as const, label: 'AI Assistant', icon: Bot, color: 'indigo' },
  ];

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col font-sans selection:bg-cyan-500/20 selection:text-cyan-300">
      {/* Top Application Navbar */}
      <header className="sticky top-0 z-30 border-b border-neutral-800/80 bg-neutral-950/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-indigo-600 text-neutral-950 font-black shadow-lg shadow-cyan-500/20">
              GS
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold tracking-tight text-neutral-100">GitScout</span>
                <span className="rounded border border-neutral-800 bg-neutral-900 px-1.5 py-0.5 text-[10px] font-mono text-cyan-400">
                  v0.1.0
                </span>
              </div>
              <p className="text-[11px] text-neutral-400">AI-Powered Repository Intelligence</p>
            </div>
          </div>

          {/* Repository Ingestion Bar */}
          <form onSubmit={handleAnalyze} className="flex items-center gap-2 max-w-lg w-full">
            <div className="relative flex-1">
              <Code2 className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-neutral-500" />
              <input
                type="text"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/owner/repository"
                className="w-full rounded-lg border border-neutral-800 bg-neutral-900/90 py-1.5 pl-9 pr-3 text-xs text-neutral-200 placeholder-neutral-500 transition-colors focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
              />
            </div>
            <button
              type="submit"
              disabled={phase !== 'idle' && phase !== 'COMPLETED' && phase !== 'FAILED'}
              className="flex items-center gap-1.5 rounded-lg bg-cyan-500 px-3.5 py-1.5 text-xs font-semibold text-neutral-950 shadow-sm transition-all hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {phase !== 'idle' && phase !== 'COMPLETED' && phase !== 'FAILED' ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Analyzing…</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>Analyze</span>
                </>
              )}
            </button>
          </form>

          {/* Re-analyze & Status Indicator */}
          <div className="flex items-center gap-3 text-xs">
            {hasResults && (
              <button
                type="button"
                onClick={triggerReanalysis}
                disabled={phase !== 'COMPLETED'}
                className="hidden sm:flex items-center gap-1 rounded-md border border-neutral-800 bg-neutral-900 px-2.5 py-1 text-xs text-neutral-300 hover:border-neutral-700 hover:text-white transition-colors"
                title="Re-run analysis on this repository"
              >
                <RefreshCw className="h-3 w-3" />
                <span>Re-analyze</span>
              </button>
            )}
            <span className="hidden sm:flex items-center gap-1.5 text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Engine Active</span>
            </span>
          </div>
        </div>
      </header>

      {/* Main Workspace Body */}
      <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col px-4 py-6 sm:px-6">
        {/* Status bar (during analysis or on failure) */}
        {phase !== 'idle' && (
          <div className="mb-4">
            <StatusBadge phase={phase} />
            {errorMsg && (
              <div className="mt-2 flex items-center justify-between rounded-lg border border-rose-800/50 bg-rose-950/30 p-3 text-xs text-rose-300">
                <div className="flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
                  <span>{errorMsg}</span>
                </div>
                <button
                  type="button"
                  onClick={() => handleAnalyze()}
                  className="rounded bg-rose-500/20 px-2 py-1 text-xs font-medium text-rose-200 hover:bg-rose-500/30 transition-colors"
                >
                  Retry
                </button>
              </div>
            )}
          </div>
        )}

        {/* Landing state – no analysis yet */}
        {!hasResults && phase === 'idle' && (
          <div className="flex flex-1 flex-col items-center justify-center text-center py-20">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-500/20 to-indigo-600/20 border border-cyan-500/30 mb-6 shadow-xl shadow-cyan-500/5">
              <Network className="h-8 w-8 text-cyan-400" />
            </div>
            <h2 className="text-xl font-bold text-neutral-100 mb-2">Analyze Any GitHub Repository</h2>
            <p className="max-w-md text-sm text-neutral-400 mb-6">
              Enter any public Python or TypeScript/JavaScript GitHub URL above to deterministically extract its file dependency graph, code symbols, security findings, and architecture documentation.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-2 text-xs text-neutral-400">
              <span className="text-neutral-500">Quick explore:</span>
              {[
                'https://github.com/ayushdobey/driveinstyle',
                'https://github.com/psf/requests',
                'https://github.com/joerick/pyinstrument',
                'https://github.com/pallets/flask',
              ].map((url) => {
                const label = url.replace('https://github.com/', '');
                return (
                  <button
                    key={url}
                    type="button"
                    onClick={() => handleAnalyze(undefined, url)}
                    className="rounded-md border border-neutral-800 bg-neutral-900/90 px-3 py-1.5 hover:border-cyan-500 hover:text-cyan-300 transition-colors font-mono"
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Results workspace */}
        {hasResults && (
          <>
            {/* Repo Header & Tab Navigation */}
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-neutral-800 pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-xl font-bold tracking-tight text-neutral-100">{displayName}</h1>
                  <span className="flex items-center gap-1 rounded border border-neutral-800 bg-neutral-900 px-2 py-0.5 text-xs font-mono text-neutral-300">
                    <GitBranch className="h-3 w-3 text-neutral-400" />
                    <span>{displayBranch}</span>
                  </span>
                  <span className="rounded border border-emerald-800/50 bg-emerald-950/30 px-2 py-0.5 text-xs text-emerald-400">
                    {graphData!.metrics.total_nodes} files · {graphData!.metrics.total_edges} dependencies
                  </span>
                </div>
                <p className="mt-1 text-xs text-neutral-400">
                  Interactive workspace. Switch tabs to inspect graph topology, code symbols, security findings, or ask codebase questions.
                </p>
              </div>

              {/* Navigation Tabs */}
              <div className="flex items-center gap-1 rounded-lg border border-neutral-800 bg-neutral-900/80 p-1">
                {tabs.map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.key;
                  return (
                    <button
                      key={tab.key}
                      onClick={() => setActiveTab(tab.key)}
                      className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                        isActive
                          ? 'bg-neutral-800 text-cyan-400 shadow-sm'
                          : 'text-neutral-400 hover:text-neutral-200'
                      }`}
                    >
                      <Icon className="h-3.5 w-3.5" />
                      <span className="hidden lg:inline">{tab.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Tab Contents */}
            <div className="mt-6 flex-1">
              {activeTab === 'graph' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between text-xs text-neutral-400">
                    <p>Interactive file-to-file directed dependency graph. Pan, zoom, click any module to inspect references.</p>
                    <span className="font-mono text-neutral-500">NetworkX Directed Adjacency Engine</span>
                  </div>
                  <DependencyGraph graphData={graphData!} />
                </div>
              )}

              {activeTab === 'overview' && <OverviewCharts metrics={graphData!.metrics} />}

              {activeTab === 'explorer' && (
                <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-6 text-neutral-300">
                  <h3 className="text-sm font-semibold text-neutral-100 flex items-center gap-2">
                    <FolderTree className="h-4 w-4 text-cyan-400" />
                    <span>AST File & Symbol Explorer ({graphData!.nodes.length} files)</span>
                  </h3>
                  <p className="mt-1 text-xs text-neutral-400 mb-4">
                    Extracted classes, functions, and import references from deterministic source analysis.
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-[600px] overflow-y-auto pr-2">
                    {graphData!.nodes.map((node) => (
                      <div key={node.id} className="rounded-lg border border-neutral-800 bg-neutral-950 p-4">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-xs font-semibold text-cyan-400">{node.label}</span>
                          <span className="text-[10px] text-neutral-500 font-mono">{node.language || 'Source'}</span>
                        </div>
                        <p className="text-[11px] text-neutral-400 mt-1 font-mono truncate">{node.path}</p>
                        <div className="mt-3 flex items-center gap-3 text-xs text-neutral-400">
                          <span>In: <strong className="text-neutral-200">{node.in_degree}</strong></span>
                          <span>Out: <strong className="text-neutral-200">{node.out_degree}</strong></span>
                          <span>PageRank: <strong className="text-neutral-200">{node.pagerank.toFixed(4)}</strong></span>
                          {node.is_entry_point && (
                            <span className="ml-auto rounded bg-cyan-500/20 px-1.5 py-0.5 text-[10px] text-cyan-300 font-semibold">
                              ENTRY POINT
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {activeTab === 'security' && (
                <div className="space-y-4">
                  <FindingsTable findings={findings.length > 0 ? findings : undefined} />
                </div>
              )}

              {activeTab === 'report' && (
                <div className="space-y-4">
                  <ArchitectureReportView
                    repoName={displayName}
                    markdownContent={reportMarkdown || undefined}
                  />
                </div>
              )}

              {activeTab === 'assistant' && repoId && (
                <div className="space-y-4">
                  <CodebaseAssistant repoId={repoId} repoName={displayName} />
                </div>
              )}
            </div>
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-neutral-900 bg-neutral-950 px-6 py-4 text-center text-xs text-neutral-600">
        GitScout • Production-Quality GitHub Repository Intelligence Platform • ADBMS Academic Project
      </footer>
    </div>
  );
}
