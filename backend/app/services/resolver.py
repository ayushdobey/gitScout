import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Set

from app.services.ast_parser import ExtractedImport


@dataclass
class ResolvedDependency:
    source_path: str
    target_path: str | None
    dependency_type: str  # DIRECT_IMPORT, FROM_IMPORT, DYNAMIC_IMPORT
    imported_symbol: str | None
    line_number: int
    is_internal: bool


class ModuleResolver:
    """
    Resolves Python import statements to concrete files within a repository.
    Handles absolute imports, relative dot-imports (PEP 328), and src/ layout normalization.
    """
    def __init__(self, file_paths: List[str]):
        self.file_paths: List[str] = [self._normalize_path(p) for p in file_paths]
        self.path_set: Set[str] = set(self.file_paths)
        
        # Standard library module names in Python 3.10+
        self.stdlib_modules: Set[str] = getattr(sys, "stdlib_module_names", set())

        # Build module mapping: e.g. "app.models.user" -> "app/models/user.py"
        self.module_to_path: Dict[str, str] = {}
        self._build_module_map()

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Convert all separators to standard forward slashes."""
        return path.replace("\\", "/").strip("/")

    def _build_module_map(self):
        for path in self.file_paths:
            if not path.endswith(".py"):
                continue

            # Remove .py extension
            without_ext = path[:-3]
            parts = without_ext.split("/")

            # Handle __init__.py package paths
            if parts[-1] == "__init__":
                module_name = ".".join(parts[:-1])
            else:
                module_name = ".".join(parts)

            if module_name:
                self.module_to_path[module_name] = path

            # Also index without 'src.' prefix if repository uses a src/ layout
            if parts and parts[0] == "src" and len(parts) > 1:
                src_stripped = parts[1:]
                if src_stripped[-1] == "__init__":
                    alt_module = ".".join(src_stripped[:-1])
                else:
                    alt_module = ".".join(src_stripped)
                if alt_module:
                    self.module_to_path[alt_module] = path

    def resolve_relative_import(self, current_file: str, level: int, module: str | None) -> str | None:
        """
        Resolve relative imports (e.g. from ..core import config with level=2).
        level 1 = current directory, level 2 = parent directory, etc.
        """
        norm_current = self._normalize_path(current_file)
        current_dir = os.path.dirname(norm_current).replace("\\", "/")
        dir_parts = current_dir.split("/") if current_dir else []

        # level 1 = directory of current file
        # level 2 = parent of directory of current file
        steps_back = level - 1
        if steps_back > len(dir_parts):
            return None

        base_parts = dir_parts[:len(dir_parts) - steps_back] if steps_back > 0 else dir_parts
        target_parts = list(base_parts)
        if module:
            target_parts.extend(module.split("."))

        # 1. Try file path directly
        potential_file = "/".join(target_parts) + ".py"
        if potential_file in self.path_set:
            return potential_file

        # 2. Try package __init__.py
        potential_init = "/".join(target_parts) + "/__init__.py"
        if potential_init in self.path_set:
            return potential_init

        return None

    def resolve_absolute_import(self, module_name: str) -> str | None:
        """
        Resolve absolute module import to repository file path.
        e.g., 'app.models.user' -> 'app/models/user.py'
        """
        # Exact match
        if module_name in self.module_to_path:
            return self.module_to_path[module_name]

        # Check prefix matches for imported symbols:
        # e.g., 'from app.models.user import User' where imported module might be parsed as 'app.models.user'
        parts = module_name.split(".")
        for i in range(len(parts), 0, -1):
            sub_mod = ".".join(parts[:i])
            if sub_mod in self.module_to_path:
                return self.module_to_path[sub_mod]

        return None

    def resolve_import(self, current_file: str, imp: ExtractedImport) -> List[ResolvedDependency]:
        """
        Resolve an ExtractedImport into discrete ResolvedDependency objects.
        """
        results: List[ResolvedDependency] = []
        source_path = self._normalize_path(current_file)

        if imp.is_from_import:
            # from X import Y
            target_path = None
            if imp.level > 0:
                # Relative import
                target_path = self.resolve_relative_import(source_path, imp.level, imp.module)
            elif imp.module:
                # Absolute import
                target_path = self.resolve_absolute_import(imp.module)

            is_internal = target_path is not None

            for sym_name, _ in imp.names:
                results.append(
                    ResolvedDependency(
                        source_path=source_path,
                        target_path=target_path,
                        dependency_type="FROM_IMPORT",
                        imported_symbol=sym_name,
                        line_number=imp.line_number,
                        is_internal=is_internal
                    )
                )
        else:
            # import X, Y as Z
            for mod_name, _ in imp.names:
                target_path = self.resolve_absolute_import(mod_name)
                is_internal = target_path is not None
                results.append(
                    ResolvedDependency(
                        source_path=source_path,
                        target_path=target_path,
                        dependency_type="DIRECT_IMPORT",
                        imported_symbol=mod_name,
                        line_number=imp.line_number,
                        is_internal=is_internal
                    )
                )

        return results
