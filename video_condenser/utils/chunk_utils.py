"""
Chunking helpers for long transcripts and segment batches.
Used by summarizer (text chunks) and embedding_engine (batch encode).
"""
from typing import List, TypeVar

T = TypeVar("T")


def chunk_text(
    text: str,
    chunk_size: int,
    overlap: int = 0,
) -> List[str]:
    """
    Split text into chunks by character count.
    Optional overlap keeps context across chunk boundaries.
    """
    if not text or chunk_size <= 0:
        return [text] if text else []
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start = end - overlap if overlap > 0 else end
    return chunks if chunks else [text]


def batch_list(items: List[T], batch_size: int) -> List[List[T]]:
    """Split a list into batches of at most batch_size."""
    if batch_size <= 0:
        return [items]
    return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]
