from app.services.ast_parser import parse_python_source

SAMPLE_PYTHON_CODE = '''"""Module docstring explaining architecture."""
import os
import sys
from typing import List, Optional, Dict
from .utils import helper_func
from ..core.config import settings

@decorator_one
@decorator_two(param="value")
class DatabaseService(BaseService):
    """Handles connection pooling and transactional lifecycles."""
    
    def __init__(self, dsn: str, max_connections: int = 10):
        self.dsn = dsn
        self.max_connections = max_connections

    async def execute_query(self, query: str, timeout: Optional[float] = None) -> List[Dict]:
        """Execute async SQL statement."""
        if timeout and timeout > 0:
            if timeout > 30:
                print("Long running query")
        return []

def calculate_checksum(data: bytes, salt: str = "default_salt") -> str:
    """Calculates SHA256 checksum."""
    return "checksum_hex"

if __name__ == "__main__":
    app = FastAPI()
'''


def test_ast_symbol_extraction():
    """Verify deterministic extraction of classes, functions, methods, docstrings, and signatures."""
    result = parse_python_source(SAMPLE_PYTHON_CODE)
    assert result.is_valid_python is True
    assert result.is_entry_point is True
    assert result.error is None
    assert result.line_count > 20

    # Verify Class Symbol
    class_syms = [s for s in result.symbols if s.symbol_type == "CLASS"]
    assert len(class_syms) == 1
    db_class = class_syms[0]
    assert db_class.name == "DatabaseService"
    assert "BaseService" in db_class.metadata["bases"]
    assert db_class.docstring == "Handles connection pooling and transactional lifecycles."
    assert len(db_class.decorators) == 2
    assert "@decorator_one" in db_class.decorators

    # Verify Method Symbol
    methods = [s for s in result.symbols if s.symbol_type in ("METHOD", "ASYNC_FUNCTION")]
    assert len(methods) > 0
    init_method = next(s for s in result.symbols if s.name == "DatabaseService.__init__")
    assert init_method.symbol_type == "METHOD"
    assert "dsn: str" in init_method.signature
    assert "max_connections: int = 10" in init_method.signature

    async_method = next(s for s in result.symbols if s.name == "DatabaseService.execute_query")
    assert async_method.metadata["is_async"] is True
    assert "async def execute_query" in async_method.signature
    assert "-> List[Dict]" in async_method.signature
    assert async_method.docstring == "Execute async SQL statement."
    # Cyclomatic complexity: 1 base + 1 (if timeout) + 1 (and) + 1 (if timeout > 30) = 4
    assert async_method.cyclomatic_complexity >= 3

    # Verify Standalone Function
    func = next(s for s in result.symbols if s.name == "calculate_checksum")
    assert func.symbol_type == "FUNCTION"
    assert "data: bytes" in func.signature
    assert "salt: str = 'default_salt'" in func.signature or 'salt: str = "default_salt"' in func.signature
    assert "-> str" in func.signature


def test_ast_imports_extraction():
    """Verify extraction of direct, from, and relative imports."""
    result = parse_python_source(SAMPLE_PYTHON_CODE)
    assert result.is_valid_python is True

    direct_imports = [imp for imp in result.imports if not imp.is_from_import]
    assert len(direct_imports) == 2
    modules = [name[0] for imp in direct_imports for name in imp.names]
    assert "os" in modules
    assert "sys" in modules

    from_imports = [imp for imp in result.imports if imp.is_from_import]
    # typing, .utils, ..core.config
    assert len(from_imports) == 3

    # Relative imports
    rel_utils = next(imp for imp in from_imports if imp.module == "utils")
    assert rel_utils.level == 1  # .utils

    rel_config = next(imp for imp in from_imports if imp.module == "core.config")
    assert rel_config.level == 2  # ..core.config


def test_ast_syntax_error_resilience():
    """Verify that malformed Python syntax does not raise unhandled exceptions."""
    invalid_code = "def broken_function(: return 42"
    result = parse_python_source(invalid_code)
    assert result.is_valid_python is False
    assert result.error is not None
    assert "SyntaxError" in result.error
    assert len(result.symbols) == 0

