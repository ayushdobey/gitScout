"""
JavaScript & TypeScript Dependency and Symbol Extractor.
Extracts ES module imports, CommonJS requires, paths aliases (@/),
and top-level exported functions and classes.
"""

import os
import re
from dataclasses import dataclass
from typing import List, Set


@dataclass
class JSExtractedImport:
    target_raw: str
    target_path: str | None
    import_type: str  # ES_IMPORT, REQUIRE
    line_number: int


@dataclass
class JSExtractedSymbol:
    name: str
    symbol_type: str  # FUNCTION, CLASS, CONST
    line_number: int


class JavaScriptResolver:
    """
    Extracts module dependencies and top-level symbols from JavaScript and TypeScript codebases.
    """
    IMPORT_REGEX = re.compile(
        r'''(?:import\s+(?:(?:[\w*\s{},]*\s+from\s+)|)|export\s+(?:(?:[\w*\s{},]*\s+from\s+)|))['"]([^'"]+)['"]|require\(['"]([^'"]+)['"]\)'''
    )
    
    SYMBOL_REGEX = re.compile(
        r'''(?:export\s+(?:default\s+)?)?(?:async\s+)?(function|class|const|let)\s+([a-zA-Z0-9_$]+)'''
    )

    EXTENSIONS = [
        "",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".json",
        ".css",
        "/index.ts",
        "/index.tsx",
        "/index.js",
        "/index.jsx",
    ]

    def __init__(self, all_file_paths: List[str]):
        self.all_paths: Set[str] = {p.replace("\\", "/").strip("/") for p in all_file_paths}

    def resolve_file_imports(self, file_path: str, content: str) -> List[JSExtractedImport]:
        """
        Extract and resolve import statements in a JS/TS source file.
        """
        results: List[JSExtractedImport] = []
        normalized_current = file_path.replace("\\", "/").strip("/")
        current_dir = os.path.dirname(normalized_current).replace("\\", "/")

        for line_num, line in enumerate(content.splitlines(), start=1):
            for match in self.IMPORT_REGEX.finditer(line):
                raw_target = match.group(1) or match.group(2)
                if not raw_target:
                    continue

                import_type = "REQUIRE" if "require(" in match.group(0) else "ES_IMPORT"
                resolved_target = None

                # 1. Relative import (./ or ../)
                if raw_target.startswith("."):
                    base_rel = os.path.normpath(os.path.join(current_dir, raw_target)).replace("\\", "/")
                    resolved_target = self._match_candidate(base_rel)

                # 2. Project root or @/ path alias
                elif raw_target.startswith("@/"):
                    alias_rel = raw_target[2:]
                    resolved_target = self._match_candidate(alias_rel)
                    if not resolved_target:
                        resolved_target = self._match_candidate(f"src/{alias_rel}")

                results.append(
                    JSExtractedImport(
                        target_raw=raw_target,
                        target_path=resolved_target,
                        import_type=import_type,
                        line_number=line_num
                    )
                )

        return results

    def extract_symbols(self, content: str) -> List[JSExtractedSymbol]:
        """
        Extract top-level functions, classes, and constants.
        """
        symbols: List[JSExtractedSymbol] = []
        seen = set()

        for line_num, line in enumerate(content.splitlines(), start=1):
            match = self.SYMBOL_REGEX.search(line)
            if match:
                kind_raw = match.group(1)
                name = match.group(2)
                if name in seen or name in ("if", "for", "while", "switch"):
                    continue
                seen.add(name)

                sym_type = "FUNCTION"
                if kind_raw == "class":
                    sym_type = "CLASS"
                elif kind_raw in ("const", "let"):
                    sym_type = "VARIABLE"

                symbols.append(
                    JSExtractedSymbol(
                        name=name,
                        symbol_type=sym_type,
                        line_number=line_num
                    )
                )

        return symbols

    def _match_candidate(self, base_path: str) -> str | None:
        """Test candidate extensions against existing repository files."""
        clean_base = base_path.replace("\\", "/").strip("/")
        for ext in self.EXTENSIONS:
            candidate = f"{clean_base}{ext}"
            if candidate in self.all_paths:
                return candidate
        return None

