import pytest

from app.services.ingestion import IGNORED_DIRECTORIES, IGNORED_EXTENSIONS, parse_github_url


def test_parse_github_url_valid_and_invalid():
    """Verify GitHub repository URL extraction and validation."""
    owner, repo = parse_github_url("https://github.com/pallets/flask")
    assert owner == "pallets"
    assert repo == "flask"

    owner2, repo2 = parse_github_url("https://www.github.com/encode/fastapi/")
    assert owner2 == "encode"
    assert repo2 == "fastapi"

    with pytest.raises(ValueError):
        parse_github_url("https://gitlab.com/owner/repo")

    with pytest.raises(ValueError):
        parse_github_url("https://github.com/invalid-path")


def test_ignored_folders_and_extensions_filters():
    """Verify exclusions for virtual environments, caches, and binary formats."""
    assert "__pycache__" in IGNORED_DIRECTORIES
    assert "node_modules" in IGNORED_DIRECTORIES
    assert ".venv" in IGNORED_DIRECTORIES

    assert ".pyc" in IGNORED_EXTENSIONS
    assert ".so" in IGNORED_EXTENSIONS
    assert ".zip" in IGNORED_EXTENSIONS
    assert ".png" in IGNORED_EXTENSIONS

