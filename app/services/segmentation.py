import json
import numpy as np
from typing import List, Dict
import nltk
from nltk.tokenize import sent_tokenize
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from scipy.signal import argrelextrema
from app.services.he import deduplicate_vision_context
# Ensure NLTK resources are available (NLTK 3.9+ uses punkt_tab for sent_tokenize)
for resource in ("punkt_tab", "punkt"):
    try:
        nltk.data.find(f"tokenizers/{resource}")
    except LookupError:
        nltk.download(resource)

class TopicProcessor:
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """Initializes the processor with a sentence-transformer model."""
        self.encoder = SentenceTransformer(model_name)

    def _get_dynamic_params(self, total_sentences: int) -> int:
        """Dynamically calculates window size (k) based on transcript length."""
        if total_sentences < 100:
            return 2
        elif total_sentences < 500:
            return 3
        else:
            return 5

    def _build_sentences_with_timestamps(self, words: List[Dict]) -> List[Dict]:
        full_text = " ".join([w["word"] for w in words])
        raw_sentences = sent_tokenize(full_text)

        sentences = []
        word_idx = 0
        total_words = len(words)

        for text in raw_sentences:
            # Check if we've already consumed all words
            if word_idx >= total_words:
                break

            sent_words = text.split()
            if not sent_words:
                continue

            # DEFENSIVE: Ensure word_idx doesn't overshoot
            start_time = words[word_idx]["start"]
            
            # Calculate end_idx carefully
            end_idx = min(word_idx + len(sent_words) - 1, total_words - 1)
            end_time = words[end_idx]["end"]

            sentences.append({
                "text": text,
                "start": start_time,
                "end": end_time
            })
            
            # Advance word_idx, but cap it at total_words
            word_idx = min(word_idx + len(sent_words), total_words)

        return sentences

    def _semantic_text_tiling(self, sentences: List[Dict]) -> List[Dict]:
        """Splits sentences into blocks using embedding-based depth scores."""
        if not sentences:
            return []

        texts = [s["text"] for s in sentences]
        embeddings = self.encoder.encode(texts)

        total_sentences = len(sentences)
        k = self._get_dynamic_params(total_sentences)

        # If too short for tiling, return as a single block
        if total_sentences <= k * 2:
            return [{
                "sentences": sentences, # Required for SummarizerService
                "text": " ".join(texts),
                "start": sentences[0]["start"],
                "end": sentences[-1]["end"],
                "visual_context": []
            }]

        # 1. Calculate Cosine Similarity between sliding windows
        similarities = []
        for i in range(k, total_sentences - k):
            left = embeddings[i-k:i].mean(axis=0)
            right = embeddings[i:i+k].mean(axis=0)
            sim = cosine_similarity([left], [right])[0][0]
            similarities.append(sim)

        similarities = np.array(similarities)
        
        # 2. Smooth the similarity curve
        smoothed_sims = np.convolve(similarities, np.ones(3)/3, mode="same")
        
        # 3. Calculate Depth Scores to find significant shifts
        valleys = argrelextrema(smoothed_sims, np.less)[0]
        depth_scores = []

        for v in valleys:
            # Find the peaks to the left and right of the valley
            left_peak = np.max(smoothed_sims[:v]) if v > 0 else smoothed_sims[v]
            right_peak = np.max(smoothed_sims[v+1:]) if v < len(smoothed_sims)-1 else smoothed_sims[v]
            
            # Depth is how much the similarity 'drops' compared to surrounding context
            depth = (left_peak - smoothed_sims[v]) + (right_peak - smoothed_sims[v])
            depth_scores.append((v, depth))

        # 4. Filter valleys based on a depth threshold (1.2x Mean Depth)
        if depth_scores:
            mean_depth = np.mean([d for _, d in depth_scores])
            threshold = mean_depth * 1.2
            valleys = [v for v, d in depth_scores if d > threshold]
        else:
            valleys = []

        # 5. Construct blocks
        blocks = []
        current_block_start = 0

        for valley_idx in valleys:
            split_point = valley_idx + k
            
            # Prevent creating tiny, non-comprehensive blocks
            if split_point - current_block_start < k * 2:
                continue

            block_sentences = sentences[current_block_start:split_point]
            blocks.append({
                "sentences": block_sentences, # FIX: SummarizerService needs this
                "text": " ".join([s["text"] for s in block_sentences]),
                "start": block_sentences[0]["start"],
                "end": block_sentences[-1]["end"],
                "visual_context": []
            })
            current_block_start = split_point

        # Add the remaining text as the final block
        if current_block_start < total_sentences:
            block_sentences = sentences[current_block_start:]
            blocks.append({
                "sentences": block_sentences,
                "text": " ".join([s["text"] for s in block_sentences]),
                "start": block_sentences[0]["start"],
                "end": block_sentences[-1]["end"],
                "visual_context": []
            })

        return blocks

    def process_topics(self, transcript_json_path: str, vision_json_path: str, output_path: str):
        """Orchestrates the full topic extraction and visual context mapping."""
        
        # Note: Ensure he.py is in the same directory for this import
        deduplicate_vision_context(vision_json_path, threshold=0.90)

        with open(transcript_json_path, "r", encoding="utf-8") as f:
            transcript_data = json.load(f)

        with open(vision_json_path, "r", encoding="utf-8") as f:
            vision_data = json.load(f)

        words = transcript_data.get("words", [])
        if not words:
            print("Error: No 'words' found in transcript JSON.")
            return []

        # Step 1: Group words into sentences
        sentences = self._build_sentences_with_timestamps(words)

        # Step 2: Slice sentences into semantic blocks
        blocks = self._semantic_text_tiling(sentences)

        # Step 3: Interleave Visual Context
        for frame in vision_data:
            t_frame = frame["time_offset"]
            desc = frame["description"]
            assigned = False

            for block in blocks:
                if block["start"] <= t_frame <= block["end"]:
                    block["visual_context"].append(desc)
                    assigned = True
                    break

            if not assigned and blocks:
                # Find the numerically closest block if frame falls in a timing gap
                closest_block = min(
                    blocks,
                    key=lambda b: min(abs(t_frame - b["start"]), abs(t_frame - b["end"]))
                )
                closest_block["visual_context"].append(desc)

        # Step 4: Final Output
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(blocks, f, indent=2)

        print(f"Generated {len(blocks)} independent semantic blocks with sentence lists.")
        return blocks