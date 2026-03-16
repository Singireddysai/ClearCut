import json
import os
import csv
from pathlib import Path
import ffmpeg
from bert_score import score
from google import genai


def get_video_duration(video_path: str) -> float:
    """Uses FFmpeg probe to get the exact duration of a video file."""
    if not os.path.exists(video_path):
        return 0.0
    try:
        probe = ffmpeg.probe(video_path)
        return float(probe['format']['duration'])
    except Exception as e:
        print(f"Error probing {video_path}: {e}")
        return 0.0


def load_original_transcript(json_path: str) -> str:
    """Extracts the full text from the original transcript JSON."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    words = data.get("words", [])
    return " ".join([w["word"] for w in words])


def load_summary_transcript(txt_path: str) -> str:
    """Loads the summary text blob."""
    if not os.path.exists(txt_path):
        return ""
    with open(txt_path, "r", encoding="utf-8") as f:
        return f.read().replace('\n', ' ')


def get_llm_score(original: str, summary: str, api_key: str) -> dict:
    """Uses the new google-genai Client for Gemini 3 Flash evaluation."""
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are an expert academic evaluator scoring a video summary.
    Compare the Summary against the Original Transcript.

    Original Transcript: {original}
    
    Summary: {summary}

    Evaluate the summary on a scale of 1 to 10. Return ONLY a JSON object with these exact keys:
    1. "fluency" (How natural, cohesive, and logically structured the summary reads)
    2. "coverage" (How well it retains the most critical information and concepts)
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt,
            config={
                "response_mime_type": "application/json"
            }
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"LLM Judging failed: {e}")
        return {"fluency": 0, "coverage": 0}


def write_csv(results: list[dict], output_path: str = "evaluation_results.csv"):
    """Writes evaluation results to a CSV file."""
    fieldnames = [
        "video_hash",
        "label",
        # Video / length stats
        "duration_seconds",
        "duration_minutes",
        "summary_words",
        "original_words",
        "length_ratio_pct",
        # BERTScore
        "bertscore_precision",
        "bertscore_recall",
        "bertscore_f1",
        # Custom metric
        "coverage_efficiency",
        # LLM as a Judge Metrics
        "llm_fluency",
        "llm_coverage"
    ]

    file_exists = os.path.exists(output_path)

    with open(output_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(results)

    print(f"\nResults appended to: {os.path.abspath(output_path)}")


def get_metrics(original_transcript_path: str, dir_path: str, google_api_key: str):
    dir_path = Path(dir_path)
    video_hash = dir_path.name  # Extracts the folder name
    
    tasks = {
        "short":  {"txt": dir_path / "short_transcript.txt",  "vid": dir_path / "summary_short.mp4"},
        "medium": {"txt": dir_path / "medium_transcript.txt", "vid": dir_path / "summary_medium.mp4"},
        "long":   {"txt": dir_path / "long_transcript.txt",   "vid": dir_path / "summary_long.mp4"},
    }

    csv_output_path = "evaluation_results.csv"

    print(f"\nProcessing Video Hash: {video_hash}")
    print("Loading original transcript...")
    orig_text = load_original_transcript(original_transcript_path)
    orig_words = len(orig_text.split())
    print(f"Original Word Count: {orig_words}\n")

    if orig_words == 0:
        print("Original transcript is empty. Exiting.")
        return

    csv_rows = []

    for label, files in tasks.items():
        print(f"{'='*40}")
        print(f"EVALUATING: {label.upper()}")
        print(f"{'='*40}")

        sum_text = load_summary_transcript(files["txt"])
        video_path = str(files["vid"])

        if not sum_text:
            print(f"Missing transcript for {label} ({files['txt']}). Skipping.\n")
            continue

        sum_words = len(sum_text.split())
        length_ratio = sum_words / orig_words

        print("Calculating BERTScore...")
        P, R, F1 = score([sum_text], [orig_text], lang="en", verbose=False)

        precision = P.item()
        recall    = R.item()
        f1        = F1.item()

        coverage_efficiency = recall / length_ratio if length_ratio > 0 else 0

        duration_sec  = get_video_duration(video_path)
        duration_mins = duration_sec / 60
        
        print("Calculating LLM Judge Metrics (Gemini 3 Flash)...")
        llm_scores = get_llm_score(orig_text, sum_text, google_api_key)

        print(f"--- Video Stats ---")
        print(f"Final Duration : {duration_mins:.2f} minutes ({duration_sec:.1f} seconds)")
        print(f"Summary Words  : {sum_words} ({length_ratio*100:.1f}% of original)")

        print(f"\n--- Metrics ---")
        print(f"BERTScore F1   : {f1:.4f}")
        print(f"LLM Fluency    : {llm_scores.get('fluency')}/10")
        print(f"LLM Coverage   : {llm_scores.get('coverage')}/10")

        csv_rows.append({
            "video_hash":             video_hash,
            "label":                  label,
            "duration_seconds":       round(duration_sec, 2),
            "duration_minutes":       round(duration_mins, 4),
            "summary_words":          sum_words,
            "original_words":         orig_words,
            "length_ratio_pct":       round(length_ratio * 100, 2),
            "bertscore_precision":    round(precision, 6),
            "bertscore_recall":       round(recall, 6),
            "bertscore_f1":           round(f1, 6),
            "coverage_efficiency":    round(coverage_efficiency, 6),
            "llm_fluency":            llm_scores.get("fluency", 0),
            "llm_coverage":           llm_scores.get("coverage", 0)
        })

    if csv_rows:
        write_csv(csv_rows, csv_output_path)