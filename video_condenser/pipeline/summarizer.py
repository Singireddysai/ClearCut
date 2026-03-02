"""
Summarize transcript using HuggingFace pipeline or LLM (OpenRouter gpt-oss-20b).
Chunks long transcripts to stay within model limits; removes ads/filler.
"""
import logging
from pathlib import Path
from typing import List, Dict, Any

from ..config.settings import Settings, default_settings
from ..utils.chunk_utils import chunk_text

logger = logging.getLogger(__name__)

# Typical max input length for BART-style models (chars approx)
DEFAULT_MODEL_MAX_CHARS = 1024 * 4  # ~4k chars per chunk safe for many models
# LLM context: use chunk size that fits typical context windows (leave room for response)
LLM_CHUNK_CHARS = 120_000  # ~30k tokens for gpt-oss-20b 131k window


def _full_text_from_segments(segments: List[Dict[str, Any]]) -> str:
    """Concatenate segment texts into one transcript string."""
    return " ".join((s.get("text") or "").strip() for s in segments).strip()


def summarize_transcript(
    segments: List[Dict[str, Any]],
    output_path: str | None = None,
    settings: Settings | None = None,
) -> str:
    """
    Summarize full transcript; chunk if too long.
    Uses LLM (OpenRouter gpt-oss-20b) when use_llm_summarization and API key/base_url set.
    """
    settings = settings or default_settings
    full_text = _full_text_from_segments(segments)
    if not full_text:
        logger.warning("Empty transcript; returning empty summary")
        if output_path is None:
            output_path = settings.summary_path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text("", encoding="utf-8")
        return ""

    use_llm = settings.use_llm_summarization and settings.get_openai_api_key() and settings.get_openai_base_url()
    if use_llm:
        summary = _summarize_llm(full_text, settings)
    else:
        summary = _summarize_huggingface(full_text, settings)

    if output_path is None:
        output_path = settings.summary_path
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(summary, encoding="utf-8")
    logger.info("Summary saved to %s (length %d)", output_path, len(summary))
    return summary


def _summarize_llm(full_text: str, settings: Settings) -> str:
    """Summarize via OpenRouter chat completions (e.g. openai/gpt-oss-20b)."""
    from openai import OpenAI
    client = OpenAI(
        api_key=settings.get_openai_api_key(),
        base_url=settings.get_openai_base_url().rstrip("/"),
    )
    chunks = chunk_text(full_text, chunk_size=LLM_CHUNK_CHARS, overlap=500)
    summaries = []
    system_prompt = (
        "You are a summarizer. Summarize the following transcript. "
        "Keep only semantically important content. Remove ads, filler speech, and redundant sentences. "
        "Output a single concise summary paragraph."
    )
    for i, chunk in enumerate(chunks):
        logger.info("LLM summarization chunk %d/%d", i + 1, len(chunks))
        resp = client.chat.completions.create(
            model=settings.summarization_llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chunk},
            ],
            max_tokens=1024,
        )
        text = (resp.choices[0].message.content or "").strip()
        if text:
            summaries.append(text)
    combined = " ".join(summaries)
    if len(summaries) > 1 and len(combined) > LLM_CHUNK_CHARS:
        resp = client.chat.completions.create(
            model=settings.summarization_llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": combined[:LLM_CHUNK_CHARS]},
            ],
            max_tokens=1024,
        )
        combined = (resp.choices[0].message.content or "").strip() or combined
    return combined


def _summarize_huggingface(full_text: str, settings: Settings) -> str:
    """Summarize via HuggingFace pipeline (BART etc.)."""
    chunk_size = settings.transcript_chunk_size
    chunks = chunk_text(full_text, chunk_size=chunk_size, overlap=200)
    pipeline = _get_summarizer(settings)
    if len(chunks) == 1:
        summary = _summarize_one(pipeline, chunks[0], settings)
    else:
        chunk_summaries = [_summarize_one(pipeline, c, settings) for c in chunks]
        combined = " ".join(chunk_summaries)
        summary = _summarize_one(pipeline, combined, settings) if len(combined) > chunk_size else combined
    return summary


def _get_summarizer(settings: Settings):
    """Lazy load HuggingFace summarization pipeline."""
    from transformers import pipeline
    logger.info("Loading summarization model: %s", settings.summarization_model)
    return pipeline(
        "summarization",
        model=settings.summarization_model,
        max_length=settings.summarization_max_length,
        min_length=settings.summarization_min_length,
    )


def _summarize_one(pipeline, text: str, settings: Settings) -> str:
    """Run pipeline on one chunk. Truncate to model max if needed."""
    # Many models have 1024 or 512 token limit; ~4 chars per token
    max_chars = min(len(text), DEFAULT_MODEL_MAX_CHARS)
    text = text[:max_chars].strip()
    if not text:
        return ""
    out = pipeline(text, max_length=settings.summarization_max_length, min_length=settings.summarization_min_length)
    if isinstance(out, list) and out:
        return (out[0].get("summary_text") or "").strip()
    return (out.get("summary_text") or "").strip() if isinstance(out, dict) else ""
