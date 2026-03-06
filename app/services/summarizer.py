import json
import numpy as np
from typing import List, Dict
from sentence_transformers import SentenceTransformer
from groq import Groq
from sklearn.metrics.pairwise import cosine_similarity

class SummarizerService:
    def __init__(self, groq_api_key: str, model_name: str = "all-MiniLM-L6-v2"):
        self.client = Groq(api_key=groq_api_key)
        # Local embedder - fast and accurate for sentence similarity
        self.embedder = SentenceTransformer(model_name)
        self.summary_model = "llama-3.3-70b-versatile"

    def _prepare_full_context(self, blocks: List[Dict]) -> str:
        """Concatenates all enriched blocks into a single string for the LLM."""
        context_parts = []
        for i, b in enumerate(blocks):
            visuals = " | ".join(b["visual_context"])
            part = f"BLOCK {i}\n[Transcript]: {b['text']}\n[Visuals]: {visuals}\n"
            context_parts.append(part)
        return "\n---\n".join(context_parts)

    def generate_abstractive_summary(self, blocks: List[Dict], length_option: str = "medium") -> List[str]:
        """
        Sends the enriched blocks to the LLM to get a fresh narrative.
        Length options: 'short' (3-5 sentences), 'medium' (7-10), 'long' (15+).
        """
        full_context = self._prepare_full_context(blocks)
        
        lengths = {
            "short": "5 to 7 detailed comprehensive sentences",
            "medium": "8 to 12 detailed comprehensive sentences",
            "long": "15 or more detailed sentences"
        }
        
        system_prompt = f"""
        You are a video editor and content strategist. 
        Based on the provided transcripts and visual descriptions, create an abstractive summary of the video.
        
        STRICT RULES:
        1. Write exactly {lengths.get(length_option, lengths['medium'])}.
        2. Each sentence must be a 'standalone' thought—avoid using pronouns like 'it' or 'this' without clear subjects.
        3. Do not quote the transcript directly; describe what is happening.
        4. Focus on the core value and narrative flow.
        5. Return ONLY the sentences, one per line. No headers or bullet points.
        """

        response = self.client.chat.completions.create(
            model=self.summary_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_context}
            ],
            temperature=0.3
        )

        # Split into a list of clean sentences
        summary_text = response.choices[0].message.content
        return [s.strip() for s in summary_text.split('\n') if s.strip()]

    def map_summary_to_blocks(self, summary_sentences: List[str], blocks: List[Dict]) -> List[int]:
        """
        Embeds sentences and blocks, then uses Cosine Similarity to find the best matches.
        """
        # 1. Create block strings (Text + Visuals) for better embedding matches
        block_texts = [f"{b['text']} {' '.join(b['visual_context'])}" for b in blocks]
        
        # 2. Generate Embeddings
        block_embeddings = self.embedder.encode(block_texts)
        sentence_embeddings = self.embedder.encode(summary_sentences)

        selected_indices = set()

        # 3. For each summary sentence, find the most semantically similar video block
        for s_emb in sentence_embeddings:
            # Reshape for sklearn
            s_emb = s_emb.reshape(1, -1)
            similarities = cosine_similarity(s_emb, block_embeddings)[0]
            
            best_match_idx = int(np.argmax(similarities))
            
            # You can add a similarity threshold here if needed (e.g., > 0.3)
            selected_indices.add(best_match_idx)

        # 4. Return sorted unique indices for chronological video assembly
        return sorted(list(selected_indices))

    def run_pipeline(self, enriched_json_path: str, length: str, output_cuts_path: str):
        with open(enriched_json_path, "r") as f:
            blocks = json.load(f)

        print(f"Generating {length} abstractive summary...")
        summary_sentences = self.generate_abstractive_summary(blocks, length)
        
        print("Matching summary to video blocks...")
        matched_indices = self.map_summary_to_blocks(summary_sentences, blocks)
        
        # Create final cut list
        final_cuts = [blocks[i] for i in matched_indices]
        
        with open(output_cuts_path, "w") as f:
            json.dump(final_cuts, f, indent=2)
            
        return final_cuts