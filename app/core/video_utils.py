from pathlib import Path
from typing import List, Dict
import ffmpeg
import shutil

class VideoUtils:
    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir

    def extract_audio(self, video_path: str) -> str:
        output_path = self.workspace_dir / "audio.mp3"
        (
            ffmpeg
            .input(video_path)
            .output(str(output_path), acodec="libmp3lame", ab="128k", vn=None, loglevel="error")
            .run(overwrite_output=True)
        )
        return str(output_path)

    def extract_frames(self, video_path: str, interval: int = 10) -> List[str]:
        frames_dir = self.workspace_dir / "frames"
        frames_dir.mkdir(exist_ok=True)
        (
            ffmpeg
            .input(video_path)
            .filter("fps", fps=1 / interval)
            .output(str(frames_dir / "frame_%04d.jpg"), **{"q:v": 4}, loglevel="error")
            .run(overwrite_output=True)
        )
        return sorted(str(p) for p in frames_dir.glob("*.jpg"))

    def _merge_adjacent_segments(self, segments: List[Dict[str, float]], threshold: float = 1) -> List[Dict[str, float]]:
        if not segments: return []
        merged = [segments[0]]
        for i in range(1, len(segments)):
            prev = merged[-1]
            curr = segments[i]
            if curr["start"] - prev["end"] <= threshold:
                prev["end"] = curr["end"]
            else:
                merged.append(curr)
        return merged

    def stitch_clips_from_file(self, video_path: str, cuts_txt_path: Path, output_path: str):
        # 1. Load and Merge Segments
        raw_segments = []
        with open(cuts_txt_path, "r", encoding="utf-8") as f:
            for line in f:
                if "," not in line: continue
                start, end = line.strip().split(",")
                raw_segments.append({"start": float(start), "end": float(end)})

        segments = self._merge_adjacent_segments(raw_segments)
        if not segments: return

        # 2. Setup Temporary Part Directory
        parts_dir = self.workspace_dir / "temp_parts"
        if parts_dir.exists(): shutil.rmtree(parts_dir)
        parts_dir.mkdir(exist_ok=True)

        list_file_path = parts_dir / "input_list.txt"
        
        # 3. Cut individual segments into .ts files
        # Using .ts avoids header corruption common in partial .mp4s
        with open(list_file_path, "w") as f:
            for i, seg in enumerate(segments):
                part_filename = f"part_{i:04d}.ts"
                part_path = parts_dir / part_filename
                
                duration = seg["end"] - seg["start"]
                if duration <= 0: continue

                (
                    ffmpeg
                    .input(video_path, ss=seg["start"], t=duration)
                    .output(str(part_path), vcodec="libx264", acodec="aac", loglevel="error")
                    .run(overwrite_output=True)
                )
                
                # Write the absolute path to the list file for FFmpeg
                f.write(f"file '{part_path.absolute()}'\n")

        # 4. Concatenate the segments
        # The '-f concat' demuxer is the "industry standard" for joining files safely
        try:
            (
                ffmpeg
                .input(str(list_file_path), format="concat", safe=0)
                .output(output_path, vcodec="copy", acodec="copy", movflags="faststart", loglevel="error")
                .run(overwrite_output=True)
            )
            print(f"Successfully stitched {len(segments)} segments into {output_path}")
        except Exception as e:
            print(f"Error during final stitch: {e}")
        finally:
            # Cleanup: Remove the temporary segments to save disk space
            if parts_dir.exists():
                shutil.rmtree(parts_dir)