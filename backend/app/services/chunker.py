import ast
from dataclasses import dataclass
from typing import List


@dataclass
class CodeChunkData:
    content: str
    start_line: int
    end_line: int
    token_count: int
    symbol_name: str | None = None


class SyntaxAwareChunker:
    """
    Syntax-Aware Code Chunker.
    Instead of arbitrary token sliding windows that slice functions and statements in half,
    this chunker uses the Python AST to divide source code along logical programming boundaries
    (classes, functions, methods, and preamble).
    """
    def __init__(self, max_chunk_lines: int = 60, min_chunk_lines: int = 5):
        self.max_chunk_lines = max_chunk_lines
        self.min_chunk_lines = min_chunk_lines

    def chunk_python_source(self, source_code: str, path: str) -> List[CodeChunkData]:
        """
        Chunk Python source code based on AST function and class definitions.
        Falls back to line-based chunking if syntax error occurs.
        """
        lines = source_code.splitlines(keepends=True)
        total_lines = len(lines)
        if total_lines == 0:
            return []

        try:
            tree = ast.parse(source_code)
        except Exception:
            return self.chunk_text_source(source_code, path)

        chunks: List[CodeChunkData] = []
        covered_lines = set()

        # Step 1: Collect top-level functions and classes
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = node.lineno
                end = node.end_lineno or node.lineno
                
                # Check for decorator lines preceding the definition
                if node.decorator_list:
                    start = min(start, min(d.lineno for d in node.decorator_list))

                chunk_content = "".join(lines[start - 1 : end])
                token_count = max(1, len(chunk_content.split()))

                name = getattr(node, "name", "unknown")
                chunks.append(
                    CodeChunkData(
                        content=chunk_content.strip(),
                        start_line=start,
                        end_line=end,
                        token_count=token_count,
                        symbol_name=name
                    )
                )
                for line_idx in range(start, end + 1):
                    covered_lines.add(line_idx)

        # Step 2: Capture module preamble (imports, global constants)
        preamble_lines = []
        preamble_start = 1
        for idx, line in enumerate(lines, start=1):
            if idx not in covered_lines:
                preamble_lines.append(line)
            else:
                if len(preamble_lines) >= self.min_chunk_lines:
                    content = "".join(preamble_lines).strip()
                    if content:
                        chunks.append(
                            CodeChunkData(
                                content=content,
                                start_line=preamble_start,
                                end_line=idx - 1,
                                token_count=max(1, len(content.split())),
                                symbol_name="module_preamble"
                            )
                        )
                preamble_lines = []
                preamble_start = idx + 1

        if len(preamble_lines) >= self.min_chunk_lines:
            content = "".join(preamble_lines).strip()
            if content:
                chunks.append(
                    CodeChunkData(
                        content=content,
                        start_line=preamble_start,
                        end_line=total_lines,
                        token_count=max(1, len(content.split())),
                        symbol_name="module_preamble"
                    )
                )

        # If file had no AST functions/classes, return entire content or text chunks
        if not chunks:
            content = "".join(lines).strip()
            chunks.append(
                CodeChunkData(
                    content=content,
                    start_line=1,
                    end_line=total_lines,
                    token_count=max(1, len(content.split())),
                    symbol_name=None
                )
            )

        # Sort chunks by start_line
        chunks.sort(key=lambda c: c.start_line)
        return chunks

    def chunk_text_source(self, text: str, path: str) -> List[CodeChunkData]:
        """
        Generic line-window chunker with overlap for Markdown, documentation, and configs.
        """
        lines = text.splitlines(keepends=True)
        total_lines = len(lines)
        if total_lines == 0:
            return []

        chunks: List[CodeChunkData] = []
        step = max(1, self.max_chunk_lines - 10)  # 10 line overlap

        for start_idx in range(0, total_lines, step):
            end_idx = min(total_lines, start_idx + self.max_chunk_lines)
            chunk_content = "".join(lines[start_idx:end_idx]).strip()
            if chunk_content:
                chunks.append(
                    CodeChunkData(
                        content=chunk_content,
                        start_line=start_idx + 1,
                        end_line=end_idx,
                        token_count=max(1, len(chunk_content.split())),
                        symbol_name=None
                    )
                )

        return chunks
