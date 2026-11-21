import abc
import hashlib
import math
import re
from typing import List

from app.core.config import settings


class BaseEmbedder(abc.ABC):
    """Abstract interface for dense code and text vector embedding providers."""
    
    @abc.abstractmethod
    def embed_text(self, text: str) -> List[float]:
        pass

    @abc.abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        pass


class FastDeterministicEmbedder(BaseEmbedder):
    """
    High-speed deterministic vector generator utilizing n-gram hashing and L2 normalization.
    Produces repeatable 384-dimensional dense vectors without requiring multi-gigabyte PyTorch binaries.
    Ideal for unit testing, CI pipelines, and resource-constrained environments.
    """
    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def _hash_token(self, token: str) -> int:
        return int(hashlib.md5(token.encode('utf-8'), usedforsecurity=False).hexdigest(), 16)

    def embed_text(self, text: str) -> List[float]:
        vec = [0.0] * self.dimension
        if not text:
            return vec

        # Tokenize code identifiers and keywords (splitting on camelCase, snake_case, whitespace)
        tokens = re.findall(r'[a-zA-Z0-9_]+', text.lower())
        if not tokens:
            return vec

        for idx, token in enumerate(tokens):
            h = self._hash_token(token)
            pos = h % self.dimension
            weight = 1.0 + (1.0 / (idx + 1))  # Give higher initial weight to early tokens
            vec[pos] += weight

            # Also hash bigrams for localized syntax context
            if idx > 0:
                bi_h = self._hash_token(f"{tokens[idx-1]}_{token}")
                bi_pos = bi_h % self.dimension
                vec[bi_pos] += 0.5

        # L2 Vector Normalization (unit length: ||v|| = 1.0)
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [round(x / norm, 6) for x in vec]

        return vec

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


class SentenceTransformerEmbedder(BaseEmbedder):
    """
    Production dense embedder using local HuggingFace / SentenceTransformers models.
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except ImportError:
                raise ImportError(
                    "sentence-transformers is not installed. "
                    "Run `pip install -r backend/requirements-ai.txt` or use FastDeterministicEmbedder."
                )
        return self._model

    def embed_text(self, text: str) -> List[float]:
        model = self._get_model()
        vec = model.encode(text, normalize_embeddings=True)
        return vec.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        model = self._get_model()
        vecs = model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vecs]


def get_embedder() -> BaseEmbedder:
    """
    Embedder factory.
    Gracefully uses SentenceTransformerEmbedder if available, otherwise falls back to FastDeterministicEmbedder.
    """
    try:
        import sentence_transformers  # noqa: F401
        return SentenceTransformerEmbedder(model_name=settings.EMBEDDING_MODEL_NAME)
    except ImportError:
        return FastDeterministicEmbedder(dimension=settings.EMBEDDING_DIMENSION)
