import ast
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class ExtractedImport:
    module: str | None
    names: List[Tuple[str, str | None]]  # (imported_name, alias)
    is_from_import: bool
    level: int  # 0 for absolute, >0 for relative (e.g., . or ..)
    line_number: int


@dataclass
class ExtractedSymbol:
    name: str
    symbol_type: str  # FUNCTION, ASYNC_FUNCTION, CLASS, METHOD
    signature: str | None
    start_line: int
    end_line: int
    docstring: str | None
    cyclomatic_complexity: int = 1
    decorators: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ASTParseResult:
    is_valid_python: bool
    symbols: List[ExtractedSymbol]
    imports: List[ExtractedImport]
    is_entry_point: bool
    error: str | None = None
    line_count: int = 0


class CyclomaticComplexityVisitor(ast.NodeVisitor):
    """
    Computes McCabe's Cyclomatic Complexity for an AST node by counting decision branches:
    Complexity = 1 + Decision Points (if, while, for, except, boolean operations).
    """
    def __init__(self):
        self.complexity = 1

    def visit_If(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_IfExp(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncWith(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_Assert(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        # Each operand beyond the first introduces an additional branch
        self.complexity += max(0, len(node.values) - 1)
        self.generic_visit(node)


class CodeIntelligenceASTVisitor(ast.NodeVisitor):
    """
    Deterministic AST visitor extracting code symbols, docstrings, signatures,
    imports, and entry-point heuristics.
    """
    def __init__(self, source_code: str):
        self.source_code = source_code
        self.symbols: List[ExtractedSymbol] = []
        self.imports: List[ExtractedImport] = []
        self.is_entry_point = False
        self._current_class: str | None = None

    def _format_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Format parameters and return annotations into standard Python signature."""
        try:
            # Reconstruct arguments safely
            args_parts = []
            args = node.args

            # Positional arguments with defaults
            num_defaults = len(args.defaults)
            pos_args = args.args
            offset = len(pos_args) - num_defaults

            for idx, arg in enumerate(pos_args):
                arg_str = arg.arg
                if arg.annotation:
                    arg_str += f": {ast.unparse(arg.annotation)}"
                if idx >= offset:
                    default_idx = idx - offset
                    arg_str += f" = {ast.unparse(args.defaults[default_idx])}"
                args_parts.append(arg_str)

            # *args
            if args.vararg:
                vararg_str = f"*{args.vararg.arg}"
                if args.vararg.annotation:
                    vararg_str += f": {ast.unparse(args.vararg.annotation)}"
                args_parts.append(vararg_str)
            elif args.kwonlyargs:
                args_parts.append("*")

            # Keyword-only arguments
            for kwarg, default in zip(args.kwonlyargs, args.kw_defaults):
                kw_str = kwarg.arg
                if kwarg.annotation:
                    kw_str += f": {ast.unparse(kwarg.annotation)}"
                if default is not None:
                    kw_str += f" = {ast.unparse(default)}"
                args_parts.append(kw_str)

            # **kwargs
            if args.kwarg:
                kwarg_str = f"**{args.kwarg.arg}"
                if args.kwarg.annotation:
                    kwarg_str += f": {ast.unparse(args.kwarg.annotation)}"
                args_parts.append(kwarg_str)

            params = ", ".join(args_parts)
            prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
            sig = f"{prefix}{node.name}({params})"
            if node.returns:
                sig += f" -> {ast.unparse(node.returns)}"
            return sig
        except Exception:
            return f"def {node.name}(...)"

    def _extract_decorators(self, decorator_list: List[ast.expr]) -> List[str]:
        decorators = []
        for dec in decorator_list:
            try:
                decorators.append(f"@{ast.unparse(dec)}")
            except Exception:
                decorators.append("@<decorator>")
        return decorators

    def _calculate_complexity(self, node: ast.AST) -> int:
        visitor = CyclomaticComplexityVisitor()
        visitor.visit(node)
        return visitor.complexity

    def visit_ClassDef(self, node: ast.ClassDef):
        bases = []
        for b in node.bases:
            try:
                bases.append(ast.unparse(b))
            except Exception:
                bases.append("object")

        decorators = self._extract_decorators(node.decorator_list)
        docstring = ast.get_docstring(node)

        symbol = ExtractedSymbol(
            name=node.name,
            symbol_type="CLASS",
            signature=f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}",
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            docstring=docstring,
            cyclomatic_complexity=1,
            decorators=decorators,
            metadata={"bases": bases}
        )
        self.symbols.append(symbol)

        # Track class nesting for methods
        previous_class = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = previous_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._process_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._process_function(node, is_async=True)

    def _process_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool):
        is_method = self._current_class is not None
        symbol_type = "METHOD" if is_method else ("ASYNC_FUNCTION" if is_async else "FUNCTION")
        display_name = f"{self._current_class}.{node.name}" if is_method else node.name
        
        signature = self._format_signature(node)
        decorators = self._extract_decorators(node.decorator_list)
        docstring = ast.get_docstring(node)
        complexity = self._calculate_complexity(node)

        symbol = ExtractedSymbol(
            name=display_name,
            symbol_type=symbol_type,
            signature=signature,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            docstring=docstring,
            cyclomatic_complexity=complexity,
            decorators=decorators,
            metadata={
                "is_async": is_async,
                "is_method": is_method,
                "parent_class": self._current_class
            }
        )
        self.symbols.append(symbol)

        # Do not recurse into inner functions with same class context
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        names = [(alias.name, alias.asname) for alias in node.names]
        self.imports.append(
            ExtractedImport(
                module=None,
                names=names,
                is_from_import=False,
                level=0,
                line_number=node.lineno
            )
        )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        names = [(alias.name, alias.asname) for alias in node.names]
        self.imports.append(
            ExtractedImport(
                module=node.module,
                names=names,
                is_from_import=True,
                level=node.level,
                line_number=node.lineno
            )
        )
        self.generic_visit(node)

    def visit_If(self, node: ast.If):
        # Check for `if __name__ == '__main__':` entry point idiom
        if isinstance(node.test, ast.Compare):
            left = node.test.left
            if isinstance(left, ast.Name) and left.id == "__name__":
                for comparator in node.test.comparators:
                    if isinstance(comparator, ast.Constant) and comparator.value == "__main__":
                        self.is_entry_point = True

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # Heuristic: detect web framework app instantiation: `app = FastAPI()`, `app = Flask(__name__)`
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in ("app", "application", "router"):
                if isinstance(node.value, ast.Call):
                    func = node.value.func
                    func_name = getattr(func, "id", None) or getattr(func, "attr", None)
                    if func_name in ("FastAPI", "Flask", "Sanic", "Tornado", "APIRouter"):
                        self.is_entry_point = True

        self.generic_visit(node)


def parse_python_source(source_code: str) -> ASTParseResult:
    """
    Parse Python source code deterministically using Python standard AST.
    Safely captures syntax errors and returns extracted symbols and imports.
    """
    line_count = len(source_code.splitlines()) if source_code else 0
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        return ASTParseResult(
            is_valid_python=False,
            symbols=[],
            imports=[],
            is_entry_point=False,
            error=f"SyntaxError at line {e.lineno}: {e.msg}",
            line_count=line_count
        )
    except Exception as e:
        return ASTParseResult(
            is_valid_python=False,
            symbols=[],
            imports=[],
            is_entry_point=False,
            error=str(e),
            line_count=line_count
        )

    visitor = CodeIntelligenceASTVisitor(source_code)
    visitor.visit(tree)

    return ASTParseResult(
        is_valid_python=True,
        symbols=visitor.symbols,
        imports=visitor.imports,
        is_entry_point=visitor.is_entry_point,
        error=None,
        line_count=line_count
    )
