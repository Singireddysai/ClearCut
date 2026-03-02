"""
Semantic matching: which transcript segments align with the summary?
Cosine similarity + threshold, merge close segments, enforce min clip duration.
Optional redundancy removal via segment-to-segment similarity.
"""
import logging
from typing import List, Dict, Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from ..config.settings import Settings, default_settings

logger = logging.getLogger(__name__)


def match_segments(
    segments: List[Dict[str, Any]],
    segment_embeddings: np.ndarray,
    summary_embedding: np.ndarray,
    settings: Settings | None = None,
) -> List[Dict[str, float]]:
    """
    Select segments that match the summary above threshold.
    Apply redundancy removal, merge close segments, drop too-short spans.
    Returns list of {"start": float, "end": float} in ascending order.
    """
    settings = settings or default_settings
    # summary_embedding: (1, dim) or (n, dim)
    if summary_embedding.ndim == 1:
        summary_embedding = summary_embedding.reshape(1, -1)
    # Per-segment similarity to summary (use max over summary vectors if multiple)
    sims = cosine_similarity(segment_embeddings, summary_embedding)
    if sims.shape[1] > 1:
        segment_scores = np.max(sims, axis=1)
    else:
        segment_scores = sims.ravel()

    # 1) Mark relevant by threshold
    relevant_indices = [i for i in range(len(segments)) if segment_scores[i] >= settings.similarity_threshold]
    if not relevant_indices:
        logger.warning("No segments above similarity threshold %.2f", settings.similarity_threshold)
        return []

    # 2) Optional redundancy: drop segment if very similar to a prior segment (keep first)
    if settings.redundancy_similarity_threshold is not None:
        relevant_indices = _drop_redundant(
            relevant_indices,
            segment_embeddings,
            segment_scores,
            settings.redundancy_similarity_threshold,
        )

    # Build (start, end) list from relevant indices
    spans = [{"start": segments[i]["start"], "end": segments[i]["end"]} for i in relevant_indices]
    spans.sort(key=lambda x: x["start"])

    # 3) Merge spans within merge_gap_sec
    spans = _merge_close_spans(spans, settings.merge_gap_sec)

    # 4) Enforce minimum clip duration (merge short with adjacent or drop)
    spans = _enforce_min_duration(spans, settings.min_clip_duration_sec)

    logger.info("Matcher: %d segments -> %d spans after threshold, merge, min_duration", len(relevant_indices), len(spans))
    return spans


def _drop_redundant(
    indices: List[int],
    segment_embeddings: np.ndarray,
    segment_scores: np.ndarray,
    redundancy_threshold: float,
) -> List[int]:
    """Drop segment if it is too similar to an earlier kept segment (redundant)."""
    if len(indices) <= 1:
        return indices
    kept = [indices[0]]
    for i in indices[1:]:
        emb_i = segment_embeddings[i : i + 1]
        kept_emb = segment_embeddings[np.array(kept)]
        sims = cosine_similarity(emb_i, kept_emb).ravel()
        max_sim = float(np.max(sims))
        if max_sim >= redundancy_threshold:
            # Redundant with an earlier segment; keep the one with higher summary score
            j_idx = int(np.argmax(sims))
            j = kept[j_idx]
            if segment_scores[i] <= segment_scores[j]:
                continue  # drop i
            kept[j_idx] = i  # replace j with i
        else:
            kept.append(i)
    return sorted(kept)


def _merge_close_spans(spans: List[Dict[str, float]], gap_sec: float) -> List[Dict[str, float]]:
    """Merge two spans if span[i].end + gap_sec >= span[i+1].start."""
    if not spans or gap_sec <= 0:
        return spans
    out = [dict(spans[0])]
    for s in spans[1:]:
        if out[-1]["end"] + gap_sec >= s["start"]:
            out[-1]["end"] = max(out[-1]["end"], s["end"])
        else:
            out.append(dict(s))
    return out


def _enforce_min_duration(
    spans: List[Dict[str, float]],
    min_sec: float,
) -> List[Dict[str, float]]:
    """Merge short spans with adjacent or drop if too short and isolated."""
    if not spans or min_sec <= 0:
        return spans
    out = []
    for s in spans:
        dur = s["end"] - s["start"]
        if dur >= min_sec:
            out.append(s)
        elif out and (out[-1]["end"] < s["start"] + 0.5):
            # Merge with previous if close
            out[-1]["end"] = s["end"]
        elif out and (s["end"] - out[-1]["start"]) >= min_sec:
            # Merge with previous
            out[-1]["end"] = s["end"]
        # else drop this short span
    return out
