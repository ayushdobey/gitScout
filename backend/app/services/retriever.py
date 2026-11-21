import re
from dataclasses import dataclass
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.chunk import CodeChunk
from app.models.file import FileRecord
from app.services.embedder import get_embedder


@dataclass
class RetrievedChunk:
    chunk_id: str
    file_id: str
    file_path: str
    start_line: int
    end_line: int
    content: str
    rrf_score: float
    dense_rank: int | None = None
    lexical_rank: int | None = None


class HybridRetriever:
    """
    Hybrid Codebase Retriever combining dense semantic vector similarity (pgvector)
    and lexical keyword matching via Reciprocal Rank Fusion (RRF).
    """
    def __init__(self, db: Session, rrf_k: int = 60):
        self.db = db
        self.rrf_k = rrf_k
        self.embedder = get_embedder()

    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Calculate cosine similarity between two unit vectors: dot(a, b)."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        return sum(x * y for x, y in zip(vec_a, vec_b))

    def dense_search(self, analysis_id: str, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Retrieve chunks using dense semantic vector similarity.
        Uses PostgreSQL pgvector <=> cosine distance if available, or in-memory cosine fallback.
        """
        query_vec = self.embedder.embed_text(query)

        # Query all chunks belonging to files in this analysis snapshot
        chunks = (
            self.db.query(CodeChunk, FileRecord.path.label("file_path"))
            .join(FileRecord, CodeChunk.file_id == FileRecord.id)
            .filter(FileRecord.analysis_id == analysis_id)
            .all()
        )

        scored_chunks = []
        for chunk, path in chunks:
            if chunk.embedding is not None:
                sim = self._cosine_similarity(query_vec, chunk.embedding)
                scored_chunks.append({
                    "chunk": chunk,
                    "file_path": path,
                    "score": sim
                })

        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        return scored_chunks[:limit]

    def lexical_search(self, analysis_id: str, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Retrieve chunks using lexical keyword and symbol matching.
        """
        tokens = [t.lower() for t in re.findall(r'[a-zA-Z0-9_]+', query) if len(t) >= 2]
        if not tokens:
            return []

        chunks = (
            self.db.query(CodeChunk, FileRecord.path.label("file_path"))
            .join(FileRecord, CodeChunk.file_id == FileRecord.id)
            .filter(FileRecord.analysis_id == analysis_id)
            .all()
        )

        scored_chunks = []
        for chunk, path in chunks:
            content_lower = chunk.content.lower()
            path_lower = path.lower()

            # Term frequency / keyword hit count
            match_score = 0
            for token in tokens:
                if token in path_lower:
                    match_score += 3  # High weight if token is in file path
                if token in content_lower:
                    match_score += 1 + content_lower.count(token) * 0.2

            if match_score > 0:
                scored_chunks.append({
                    "chunk": chunk,
                    "file_path": path,
                    "score": match_score
                })

        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        return scored_chunks[:limit]

    def hybrid_search(self, analysis_id: str, query: str, top_k: int = 5) -> List[RetrievedChunk]:
        """
        Combines dense and lexical search results using Reciprocal Rank Fusion (RRF):
        RRF(d) = sum( 1 / (k + rank_m(d)) ) for m in [dense, lexical]
        """
        dense_results = self.dense_search(analysis_id, query, limit=15)
        lexical_results = self.lexical_search(analysis_id, query, limit=15)

        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, Dict[str, Any]] = {}
        dense_ranks: Dict[str, int] = {}
        lexical_ranks: Dict[str, int] = {}

        # 1. Accumulate Dense Ranks
        for rank, item in enumerate(dense_results, start=1):
            cid = item["chunk"].id
            dense_ranks[cid] = rank
            chunk_map[cid] = item
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (self.rrf_k + rank))

        # 2. Accumulate Lexical Ranks
        for rank, item in enumerate(lexical_results, start=1):
            cid = item["chunk"].id
            lexical_ranks[cid] = rank
            chunk_map[cid] = item
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (self.rrf_k + rank))

        # 3. Sort by aggregated RRF score
        sorted_chunk_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

        final_chunks: List[RetrievedChunk] = []
        for cid in sorted_chunk_ids[:top_k]:
            item = chunk_map[cid]
            chunk = item["chunk"]
            final_chunks.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    file_id=chunk.file_id,
                    file_path=item["file_path"],
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk.content,
                    rrf_score=round(rrf_scores[cid], 5),
                    dense_rank=dense_ranks.get(cid),
                    lexical_rank=lexical_ranks.get(cid)
                )
            )

        return final_chunks
