import json
from typing import List, Dict
from nltk.tokenize import TextTilingTokenizer
import nltk

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

class TopicProcessor:
    def __init__(self):
        # w: pseudosentence size, k: block size
        self.tt = TextTilingTokenizer(w=20, k=10)

    def process_topics(self, transcript_json_path: str, vision_json_path: str, output_path: str):
        # 1. Load Data
        with open(transcript_json_path, "r", encoding="utf-8") as f:
            transcript_data = json.load(f)
        
        with open(vision_json_path, "r", encoding="utf-8") as f:
            vision_data = json.load(f) 

        # Use the flat word list directly
        words = transcript_data.get("words", [])
        if not words:
            print("Error: No 'words' found in transcript JSON.")
            return []

        full_text = " ".join([w["word"] for w in words])

        # 2. Perform TextTiling
        try:
            # TextTiling works best with some paragraph-like breaks
            # We insert double newlines every few sentences to help the algorithm
            formatted_text = full_text.replace(". ", ".\n\n")
            tiles = self.tt.tokenize(formatted_text)
        except Exception as e:
            print(f"TextTiling failed: {e}. Falling back to single block.")
            tiles = [full_text]

        # 3. Reconstruct Blocks with Timestamps
        blocks = []
        current_word_idx = 0
        
        for tile in tiles:
            # Clean tile text for matching
            tile_clean = tile.replace("\n\n", " ").strip()
            tile_words = tile_clean.split()
            
            if not tile_words:
                continue
                
            # Get start time from the first word of the tile
            start_time = words[current_word_idx]["start"]
            
            # Find the end timestamp by matching the word count
            # We use min() to prevent index out of bounds at the very end
            end_idx = min(current_word_idx + len(tile_words) - 1, len(words) - 1)
            end_time = words[end_idx]["end"]
            
            blocks.append({
                "text": tile_clean,
                "start": round(start_time, 2),
                "end": round(end_time, 2),
                "visual_context": []
            })
            
            current_word_idx += len(tile_words)

        # 4. Enrich with Visual Context
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
                # If frame falls in a tiny gap, attach to the numerically closest block
                closest_block = min(blocks, key=lambda b: min(abs(t_frame - b["start"]), abs(t_frame - b["end"])))
                closest_block["visual_context"].append(desc)

        # 5. Save
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(blocks, f, indent=2)
        
        return blocks