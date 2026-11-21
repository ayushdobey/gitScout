import hashlib
import io
import os
import re
import tarfile
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import httpx

from app.core.config import settings


@dataclass
class ExtractedSourceFile:
    path: str  # relative path within repository
    filename: str
    extension: str
    language: str
    file_size: int
    content: str
    content_hash: str  # SHA-256


@dataclass
class IngestionResult:
    owner: str
    name: str
    default_branch: str
    stars: int
    forks: int
    primary_language: str | None
    files: List[ExtractedSourceFile]
    total_files: int
    total_bytes: int


# File extension to programming language mapping
EXTENSION_LANGUAGE_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".html": "HTML",
    ".css": "CSS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Text",
    ".sql": "SQL",
    ".sh": "Shell",
}

# Directories excluded from analysis
IGNORED_DIRECTORIES = {
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    ".env",
    "node_modules",
    ".tox",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".egg-info",
    ".idea",
    ".vscode",
    "site-packages",
    "migrations",
}

# Binary and non-source extensions to skip
IGNORED_EXTENSIONS = {
    ".pyc", ".pyd", ".so", ".dll", ".dylib", ".exe", ".bin",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".lock", ".map",
}


def parse_github_url(url: str) -> Tuple[str, str]:
    """Extract (owner, repo_name) from public GitHub repository URL."""
    clean = url.strip().rstrip("/")
    pattern = r"^https?://(www\.)?github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)"
    match = re.match(pattern, clean)
    if not match:
        raise ValueError(f"Invalid GitHub URL: '{url}'. Expected format: https://github.com/owner/repository")
    return match.group(2), match.group(3)


class GitHubIngestionService:
    """
    Ingests public GitHub repositories safely via streaming archive download.
    Enforces path traversal guards, zip bomb limits, and binary file filtering.
    """
    def __init__(self, github_token: str | None = None):
        self.github_token = github_token or settings.GITHUB_TOKEN
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitScout-Code-Intelligence-App"
        }
        if self.github_token:
            self.headers["Authorization"] = f"Bearer {self.github_token}"

    def fetch_metadata(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetch repository details and rate limit telemetry via GitHub API."""
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(api_url, headers=self.headers)
            if resp.status_code == 404:
                raise ValueError(f"Repository '{owner}/{repo}' not found on GitHub. Verify that it is public.")
            if resp.status_code == 403:
                raise PermissionError("GitHub API rate limit exceeded or access forbidden. Configure GITHUB_TOKEN in .env.")
            resp.raise_for_status()
            return resp.json()

    def download_and_extract(
        self,
        owner: str,
        repo: str,
        branch: str | None = None
    ) -> IngestionResult:
        """
        Download repository tarball, unpack safely with sandbox guards, and return source files.
        """
        metadata = self.fetch_metadata(owner, repo)
        target_branch = branch or metadata.get("default_branch", "main")
        stars = metadata.get("stargazers_count", 0)
        forks = metadata.get("forks_count", 0)
        primary_lang = metadata.get("language")

        tarball_url = f"https://api.github.com/repos/{owner}/{repo}/tarball/{target_branch}"

        extracted_files: List[ExtractedSourceFile] = []
        total_decompressed_bytes = 0
        max_bytes = settings.MAX_REPO_SIZE_MB * 1024 * 1024
        max_files = settings.MAX_FILES_COUNT

        # Download archive
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            with client.stream("GET", tarball_url, headers=self.headers) as resp:
                if resp.status_code != 200:
                    raise RuntimeError(f"Failed to download tarball from GitHub: HTTP {resp.status_code}")

                # Read archive into in-memory buffer
                archive_bytes = bytearray()
                for chunk in resp.iter_bytes(chunk_size=65536):
                    archive_bytes.extend(chunk)
                    if len(archive_bytes) > max_bytes:
                        raise ValueError(f"Repository archive exceeds maximum permitted size of {settings.MAX_REPO_SIZE_MB}MB.")

        # Unpack archive safely
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:*") as tar:
            members = tar.getmembers()
            
            # The top directory in GitHub tarballs is typically `{owner}-{repo}-{commit}`
            top_prefix = ""
            if members and members[0].isdir():
                top_prefix = members[0].name.split("/")[0]

            for member in members:
                # Security Check 1: Prevent Path Traversal (Slip Attack)
                normalized_name = member.name.replace("\\", "/")
                if normalized_name.startswith("/") or ".." in normalized_name.split("/"):
                    continue

                if not member.isfile():
                    continue

                # Strip top commit directory prefix
                rel_path = normalized_name
                if top_prefix and rel_path.startswith(top_prefix):
                    rel_path = rel_path[len(top_prefix):].lstrip("/")

                if not rel_path:
                    continue

                # Directory exclusion check
                path_segments = set(rel_path.split("/"))
                if any(ignored in path_segments for ignored in IGNORED_DIRECTORIES):
                    continue

                # File extension check
                _, ext = os.path.splitext(rel_path)
                ext = ext.lower()
                if ext in IGNORED_EXTENSIONS:
                    continue

                # Check cumulative decompressed size (Zip Bomb guard)
                total_decompressed_bytes += member.size
                if total_decompressed_bytes > max_bytes:
                    raise ValueError(f"Decompressed repository size exceeds {settings.MAX_REPO_SIZE_MB}MB safety limit.")

                if len(extracted_files) >= max_files:
                    break

                # Extract and decode text content
                file_obj = tar.extractfile(member)
                if file_obj is None:
                    continue

                raw_bytes = file_obj.read()
                
                # Check for binary content (null bytes)
                if b"\x00" in raw_bytes[:1024]:
                    continue

                try:
                    content_str = raw_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        content_str = raw_bytes.decode("latin-1")
                    except (UnicodeDecodeError, ValueError):
                        continue

                content_hash = hashlib.sha256(raw_bytes).hexdigest()
                language = EXTENSION_LANGUAGE_MAP.get(ext, "Unknown")
                filename = os.path.basename(rel_path)

                extracted_files.append(
                    ExtractedSourceFile(
                        path=rel_path,
                        filename=filename,
                        extension=ext,
                        language=language,
                        file_size=member.size,
                        content=content_str,
                        content_hash=content_hash
                    )
                )

        return IngestionResult(
            owner=owner,
            name=repo,
            default_branch=target_branch,
            stars=stars,
            forks=forks,
            primary_language=primary_lang,
            files=extracted_files,
            total_files=len(extracted_files),
            total_bytes=total_decompressed_bytes
        )
