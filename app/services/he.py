import json
import os
from sentence_transformers import SentenceTransformer, util

def deduplicate_vision_context(file_path: str, threshold: float = 0.90):
    """
    Reads vision context, removes redundant frames based on semantic similarity,
    and saves the cleaned data.
    """
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not data:
        return

    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    cleaned_data = []
    last_kept_description = ""
    last_embedding = None

    for entry in data:
        current_desc = entry["description"]
        
        # Always keep the first frame
        if not cleaned_data:
            cleaned_data.append(entry)
            last_kept_description = current_desc
            last_embedding = model.encode(current_desc, convert_to_tensor=True)
            continue

        # Compute semantic similarity
        current_embedding = model.encode(current_desc, convert_to_tensor=True)
        similarity = util.cos_sim(last_embedding, current_embedding).item()

        if similarity < threshold:
            cleaned_data.append(entry)
            last_kept_description = current_desc
            last_embedding = current_embedding
            print(f"New context detected at {entry['time_offset']}s (Similarity: {similarity:.2f})")
        else:
            pass

    # Save the deduplicated data
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=2)

    print(f"Deduplication complete. Reduced {len(data)} frames to {len(cleaned_data)}.")
    return cleaned_data