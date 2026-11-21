'use client';

import React, { useState } from 'react';
import { FileText, Copy, Download, Check, Sparkles, Network, ShieldCheck, Layers } from 'lucide-react';

interface ArchitectureReportViewProps {
  repoName?: string;
  markdownContent?: string;
}

const DEFAULT_REPORT_MD = `# GitScout Architecture Report: pallets/flask

> Generated automatically by the **GitScout Repository Intelligence Platform**.  
> Snapshot Analysis ID: \`snap_flask_prod_01\` | Duration: \`385ms\`

---

## 1. Repository Overview & Statistics

| Metric | Value |
| :--- | :--- |
| **Repository URL** | https://github.com/pallets/flask |
| **Default Branch** | \`main\` |
| **GitHub Stars** | 48,200 |
| **GitHub Forks** | 14,500 |
| **Total Source Files** | 10 core modules |
| **Total Extracted Symbols** | 38 classes & functions |
| **Dependency Edges** | 14 internal import relationships |
| **Static Audit Findings** | 5 findings (0 Critical, 1 High, 2 Medium, 2 Low) |

---

## 2. Technology Stack & Language Distribution

- **Python**: 10 files (100.0%)
- **Primary Framework**: WSGI Micro-Framework Architecture
- **Key Dependencies**: Werkzeug, Jinja2, Click, ItsDangerous, Blinker

---

## 3. Structural Entry Points & Orchestrators

Entry points detected through AST heuristics:
- \`[ENTRY POINT]\` \`src/flask/app.py\` (Defines central \`Flask\` WSGI application class)

---

## 4. Key Architectural Modules & Centrality (PageRank)

Top hub modules ranked by architectural connectivity (in-degree fan-in and PageRank centrality):

| File Path | In-Degree (Fan-In) | Out-Degree (Fan-Out) | PageRank Score |
| :--- | :--- | :--- | :--- |
| \`src/flask/app.py\` | 5 | 6 | 0.2450 |
| \`src/flask/globals.py\` | 6 | 1 | 0.1890 |
| \`src/flask/config.py\` | 4 | 1 | 0.1650 |
| \`src/flask/helpers.py\` | 5 | 2 | 0.1510 |
| \`src/flask/ctx.py\` | 3 | 4 | 0.1420 |

---

## 5. Dependency Graph Topology & Cycle Analysis

- **Graph Density**: \`0.1556\`
- **Directed Acyclic Graph (DAG)**: No (Contains Cycles)
- **Isolated Modules**: 0 files with no internal imports.

### ⚠️ Detected Circular Dependency Loops:
1. \`src/flask/app.py\` $\\rightarrow$ \`src/flask/templating.py\` $\\rightarrow$ \`src/flask/app.py\`

---

## 6. Static Code Quality & Security Audit (Ruff & Bandit)

- **Critical Vulnerabilities**: \`0\`
- **High Severity Findings**: \`1\`
- **Medium Severity Findings**: \`2\`
- **Low Severity / Style Issues**: \`2\`

### Top Audit Findings:
- **[BANDIT] B608 (HIGH)** in \`src/flask/sessions.py:89\`: Potential SQL injection risk with formatted string execution.
- **[BANDIT] B101 (MEDIUM)** in \`src/flask/app.py:142\`: Use of assert detected.
- **[RUFF] C901 (MEDIUM)** in \`src/flask/app.py:2090\`: Function \`wsgi_app\` has high cyclomatic complexity (score: 14).

---

## 7. Architectural Observations & Recommendations

- **Refactor Circular Loops**: Circular module dependencies between \`app.py\` and \`templating.py\` increase tight coupling and can cause subtle runtime import errors during module initialization.
- **Modular Decoupling**: The repository exhibits clean modular separation with low overall graph density (\`D = 0.1556\`).
`;

export function ArchitectureReportView({
  repoName = "pallets/flask",
  markdownContent = DEFAULT_REPORT_MD
}: ArchitectureReportViewProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(markdownContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([markdownContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${repoName.replace('/', '_')}_architecture_report.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      {/* Top Action Bar */}
      <div className="flex items-center justify-between rounded-xl border border-neutral-800 bg-neutral-900/80 px-5 py-3 backdrop-blur-md">
        <div className="flex items-center gap-2.5">
          <FileText className="h-4 w-4 text-cyan-400" />
          <span className="text-xs font-semibold text-neutral-200">
            Synthesized Architecture Report: {repoName}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs font-medium text-neutral-200 hover:bg-neutral-700 transition-colors"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
            <span>{copied ? 'Copied!' : 'Copy Markdown'}</span>
          </button>

          <button
            onClick={handleDownload}
            className="flex items-center gap-1.5 rounded-lg bg-cyan-500 px-3 py-1.5 text-xs font-semibold text-neutral-950 hover:bg-cyan-400 transition-colors"
          >
            <Download className="h-3.5 w-3.5" />
            <span>Download .md</span>
          </button>
        </div>
      </div>

      {/* Rendered Document Container */}
      <div className="rounded-xl border border-neutral-800 bg-neutral-950 p-8 shadow-2xl overflow-x-auto text-neutral-200 leading-relaxed font-sans text-xs">
        <pre className="whitespace-pre-wrap font-sans font-normal leading-relaxed text-neutral-200">
          {markdownContent}
        </pre>
      </div>
    </div>
  );
}

