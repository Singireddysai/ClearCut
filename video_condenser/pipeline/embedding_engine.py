"""
Generate embeddings for transcript segments and summary using sentence-transformers (BGE).
Batch encoding to avoid OOM on long videos.
"""
import logging
from typing import List, Dict, Any, Union

import numpy as np
from ..config.settings import Settings, default_settings
from ..utils.chunk_utils import chunk_text, batch_list

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """Encode segments and summary with BGE; normalize for cosine similarity."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or default_settings
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model: %s", self.settings.embedding_model)
            self._model = SentenceTransformer(self.settings.embedding_model)
        return self._model

    def encode_segments(
        self,
        segments: List[Dict[str, Any]],
    ) -> np.ndarray:
        """
        Encode each segment's text in batches.
        Returns array of shape (n_segments, dim).
        """
        texts = [(s.get("text") or "").strip() for s in segments]
        batch_size = self.settings.embedding_batch_size
        batches = batch_list(texts, batch_size)
        all_embeddings = []
        for i, batch in enumerate(batches):
            emb = self.model.encode(
                batch,
                normalize_embeddings=self.settings.normalize_embeddings,
                show_progress_bar=len(batches) > 1,
            )
            all_embeddings.append(emb)
        return np.vstack(all_embeddings).astype(np.float32)

    def encode_summary(self, summary: str) -> np.ndarray:
        """
        Encode summary. If long, chunk and average (or use one vector per chunk for matching).
        Returns array of shape (1, dim) for single vector, or (n_chunks, dim) for chunked.
        We use a single vector: chunk summary if needed and average embeddings.
        """
        if not summary.strip():
            # Return zero vector matching segment dim (will be set after first encode_segments)
            return np.zeros((1, 1024), dtype=np.float32)  # BGE large dim
        chunk_size = 2000  # safe for one forward pass
        chunks = chunk_text(summary.strip(), chunk_size=chunk_size)
        emb = self.model.encode(
            chunks,
            normalize_embeddings=self.settings.normalize_embeddings,
        )
        # Single summary vector = mean of chunk embeddings, then re-normalize
        summary_vec = np.mean(emb, axis=0, keepdims=True).astype(np.float32)
        if self.settings.normalize_embeddings:
            norm = np.linalg.norm(summary_vec, axis=1, keepdims=True)
            norm = np.where(norm == 0, 1, norm)
            summary_vec = summary_vec / norm
        return summary_vec
