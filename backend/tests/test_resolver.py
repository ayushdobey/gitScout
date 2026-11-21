from app.services.resolver import ModuleResolver


def test_resolver_absolute_and_init_mapping():
    """Test resolution of standard module paths and __init__.py packages."""
    repo_files = [
        "app/main.py",
        "app/core/config.py",
        "app/models/__init__.py",
        "app/models/user.py",
        "app/utils/helpers.py"
    ]
    resolver = ModuleResolver(repo_files)

    # Absolute file import
    assert resolver.resolve_absolute_import("app.core.config") == "app/core/config.py"
    assert resolver.resolve_absolute_import("app.models.user") == "app/models/user.py"

    # Package __init__.py import
    assert resolver.resolve_absolute_import("app.models") == "app/models/__init__.py"

    # External library should return None (not an internal repository file)
    assert resolver.resolve_absolute_import("fastapi") is None
    assert resolver.resolve_absolute_import("sqlalchemy.orm") is None


def test_resolver_relative_imports():
    """Test relative dot import resolution across directory depths."""
    repo_files = [
        "src/app/main.py",
        "src/app/utils.py",
        "src/app/api/endpoints.py",
        "src/app/core/config.py"
    ]
    resolver = ModuleResolver(repo_files)

    # Level 1: same directory (from . import utils from src/app/main.py)
    res_same = resolver.resolve_relative_import("src/app/main.py", level=1, module="utils")
    assert res_same == "src/app/utils.py"

    # Level 2: parent directory (from ..core.config import settings from src/app/api/endpoints.py)
    # endpoints.py dir: src/app/api -> parent dir: src/app -> core/config.py
    res_parent = resolver.resolve_relative_import("src/app/api/endpoints.py", level=2, module="core.config")
    assert res_parent == "src/app/core/config.py"


def test_resolver_src_layout_normalization():
    """Test that repositories with src/ directory layout resolve seamlessly."""
    repo_files = [
        "src/my_pkg/__init__.py",
        "src/my_pkg/service.py"
    ]
    resolver = ModuleResolver(repo_files)

    # Can resolve both with 'src.' and stripped 'my_pkg.service'
    assert resolver.resolve_absolute_import("my_pkg.service") == "src/my_pkg/service.py"
    assert resolver.resolve_absolute_import("src.my_pkg.service") == "src/my_pkg/service.py"

