import numpy as np
from typing import List, Dict
from sentence_transformers import SentenceTransformer
from google import genai
from sklearn.metrics.pairwise import cosine_similarity


class SummarizerService:
    def __init__(
        self,
        gemini_api_key: str,
        model_name: str = "all-MiniLM-L6-v2",
        context_threshold_delta: float = 0.15,
        mmr_lambda: float = 0.6,
    ):
        # Initialize Google GenAI Client
        self.client = genai.Client(api_key=gemini_api_key)  
        self.summary_model = "gemini-2.5-flash"

        self.embedder = SentenceTransformer(model_name)
        self.context_threshold_delta = context_threshold_delta
        self.mmr_lambda = mmr_lambda

    def _clean_intra_block(
        self,
        sentences: List[Dict],
        tangent_threshold: float = 0.50,
        repeat_threshold: float = 0.92,
    ) -> List[Dict]:
        """
        Performs semantic filtering within a block.
        Removes:
          1. Sentences far from the block centroid (tangents / filler).
          2. Sentences too similar to already-kept ones (redundancy).
        """
        if len(sentences) <= 2:
            return sentences

        texts = [s["text"] for s in sentences]
        embeddings = self.embedder.encode(texts)

        centroid = embeddings.mean(axis=0).reshape(1, -1)
        sim_to_centroid = cosine_similarity(embeddings, centroid).flatten()

        cleaned = []
        kept_embeddings = []

        for i, sent in enumerate(sentences):
            # Drop tangents / filler
            if sim_to_centroid[i] < tangent_threshold:
                continue

            # Drop redundant sentences
            is_redundant = False
            if kept_embeddings:
                current_emb = embeddings[i].reshape(1, -1)
                sims_to_kept = cosine_similarity(
                    current_emb, np.array(kept_embeddings)
                ).flatten()
                if np.max(sims_to_kept) > repeat_threshold:
                    is_redundant = True

            if not is_redundant:
                cleaned.append(sent)
                kept_embeddings.append(embeddings[i])

        return cleaned

    def _prepare_full_context(self, blocks: List[Dict]) -> str:
        """Concatenates cleaned transcripts and visuals for the LLM prompt."""
        context_parts = []
        for i, b in enumerate(blocks):
            cleaned_text = " ".join([s["text"] for s in b["cleaned_sentences"]])
            visuals = " | ".join(b.get("visual_context", []))
            part = f"BLOCK {i}\n[Cleaned Transcript]: {cleaned_text}\n[Visuals]: {visuals}\n"
            context_parts.append(part)
        return "\n---\n".join(context_parts)

    def generate_abstractive_summary(
        self, blocks: List[Dict], length_option: str = "medium"
    ) -> List[str]:
        """
        Calls Gemini 3 Flash to produce an abstractive summary.
        """
        full_context = self._prepare_full_context(blocks)

        lengths = {
        "short":  "up to 3 or 4 unique, comprehensive sentences",
        "medium": "exactly 6 to 8 unique, comprehensive sentences",
        "long":   "at least 10 or more unique, comprehensive sentences",
        }

        system_instruction = f"""
        You are a content extraction specialist. 
        Your goal is to identify the most significant and distinct topics within the provided video data.

        STRICT RULES:
        1. Write {lengths.get(length_option, lengths['medium'])}.
        2. MAXIMIZE DIVERSITY: Each sentence must cover a completely different topic, theme, or segment of the video. Do not repeat the same concept across multiple lines.
        3. NO NARRATIVE FLOW: Ignore the logical flow or transitions between sentences. Treat each line as a standalone "main aspect" extraction.
        4. COMPREHENSIVE COVERAGE: Ensure the selected sentences represent the entire duration of the video, from start to finish.
        5. STANDALONE CLARITY: Each sentence must be a complete thought. Avoid pronouns like 'it', 'this', or 'they' without a specific subject (use visual context to name objects or actions).
        6. Return ONLY the sentences, one per line. No headers, bullet points, numbering, or acknowledgements.
        """

        response = self.client.models.generate_content(
            model=self.summary_model,
            contents=full_context,
            config={
                "system_instruction": system_instruction,
                "temperature": 0.3,
            },
        )

        return [s.strip() for s in response.text.split("\n") if s.strip()]

    def _select_blocks_mmr(
        self,
        sentence_embeddings: np.ndarray,
        block_embeddings: np.ndarray,
        blocks_with_sentences: List[Dict],
        length: str,
    ) -> List[int]:
        n_blocks = len(blocks_with_sentences)

        target_counts = {
            "short": max(2, int(n_blocks * 0.35)),
            "medium": max(3, int(n_blocks * 0.55)),
            "long": max(4, int(n_blocks * 0.80)),
        }
        target_n = target_counts.get(length, int(n_blocks * 0.50))
        summary_emb = sentence_embeddings.mean(axis=0)

        # Phase 1: MMR
        selected_indices: List[int] = []
        remaining = list(range(n_blocks))

        while len(selected_indices) < target_n and remaining:
            best_idx, best_score = None, -np.inf
            for i in remaining:
                relevance = cosine_similarity(
                    block_embeddings[i].reshape(1, -1),
                    summary_emb.reshape(1, -1),
                )[0][0]

                if selected_indices:
                    redundancy = max(
                        cosine_similarity(
                            block_embeddings[i].reshape(1, -1),
                            block_embeddings[j].reshape(1, -1),
                        )[0][0]
                        for j in selected_indices
                    )
                else:
                    redundancy = 0.0

                score = self.mmr_lambda * relevance - (1 - self.mmr_lambda) * redundancy
                if score > best_score:
                    best_score = score
                    best_idx = i

            selected_indices.append(best_idx)
            remaining.remove(best_idx)

        # Phase 2: Context expansion
        expanded = set(selected_indices)
        for s_emb in sentence_embeddings:
            sims = cosine_similarity(s_emb.reshape(1, -1), block_embeddings)[0]
            best_score = float(sims[int(np.argmax(sims))])
            cutoff = best_score - self.context_threshold_delta

            for i, sim in enumerate(sims):
                if sim >= cutoff:
                    expanded.add(i)

        return sorted(expanded)

    def run_pipeline(
        self,
        blocks_with_sentences: List[Dict],
        length: str,
        output_cuts_path: str,
    ) -> List[str]:
        # 1. Intra-block cleaning
        print("Cleaning blocks (removing tangents and redundancy)...")
        for block in blocks_with_sentences:
            block["cleaned_sentences"] = self._clean_intra_block(block["sentences"])
            block["cleaned_text_raw"] = " ".join(
                [s["text"] for s in block["cleaned_sentences"]]
            )

        blocks_with_sentences = [
            b for b in blocks_with_sentences if b["cleaned_sentences"]
        ]
        if not blocks_with_sentences:
            print("No blocks remaining after cleaning. Aborting.")
            return []

        # 2. Abstractive summary
        print(f"Generating {length} abstractive summary with Gemini 3 Flash...")
        summary_sentences = self.generate_abstractive_summary(
            blocks_with_sentences, length
        )

        # 3. MMR + context expansion block selection
        print("Mapping summary to semantic blocks (MMR + context expansion)...")
        block_embeddings = self.embedder.encode(
            [b["cleaned_text_raw"] for b in blocks_with_sentences]
        )
        sentence_embeddings = self.embedder.encode(summary_sentences)

        selected_indices = self._select_blocks_mmr(
            sentence_embeddings=sentence_embeddings,
            block_embeddings=block_embeddings,
            blocks_with_sentences=blocks_with_sentences,
            length=length,
        )

        print(f"Selected {len(selected_indices)}/{len(blocks_with_sentences)} blocks.")

        # 4. Build cut list and evaluation transcript
        final_segments = []
        summary_transcript_parts = []

        for idx in selected_indices:
            target_block = blocks_with_sentences[idx]
            summary_transcript_parts.append(target_block["cleaned_text_raw"])
            for s in target_block["cleaned_sentences"]:
                final_segments.append(f"{s['start']},{s['end']}")

        with open(output_cuts_path, "w", encoding="utf-8") as f:
            f.write("\n".join(final_segments))

        transcript_path = output_cuts_path.replace(".txt", "_transcript.txt")
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(summary_transcript_parts))

        print(f"Exported segments → {output_cuts_path}")
        print(f"Exported transcript → {transcript_path}")

        return final_segments
