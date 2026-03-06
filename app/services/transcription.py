import os
import asyncio
import json
from typing import List
from groq import AsyncGroq
from pydantic import BaseModel
import ffmpeg
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class Word(BaseModel):
    word: str
    start: float
    end: float

class TranscriptionResult(BaseModel):
    text: str
    words: List[Word]
    language: str

class TranscriptionService:
    def __init__(self, api_key: str):
        self.client = AsyncGroq(api_key=api_key)
        self.model = "whisper-large-v3-turbo"
        self.chunk_duration = 600

    async def _get_duration(self, audio_path: str) -> float:
        loop = asyncio.get_event_loop()
        probe = await loop.run_in_executor(None, ffmpeg.probe, audio_path)
        return float(probe["format"]["duration"])

    async def _split_audio(self, audio_path: str, duration: float) -> List[tuple[str, float]]:
        chunks = []
        base_dir = os.path.dirname(audio_path)
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        loop = asyncio.get_event_loop()
        num_chunks = int((duration // self.chunk_duration) + 1)

        for i in range(num_chunks):
            start_time = i * self.chunk_duration
            out_path = os.path.join(base_dir, f"{base_name}_chunk_{i}.mp3")
            stream = (
                ffmpeg
                .input(audio_path, ss=start_time, t=self.chunk_duration)
                .output(out_path, acodec="copy", loglevel="error")
            )
            await loop.run_in_executor(None, lambda: stream.run(overwrite_output=True))
            chunks.append((out_path, start_time))
        return chunks

    async def transcribe(self, audio_path: str, context_file: str = None) -> TranscriptionResult:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found {audio_path}")
        if context_file and os.path.exists(context_file):
            try:
                with open(context_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                if cached_data and "words" in cached_data and len(cached_data["words"]) > 0:
                    print(f"--- Cache Hit: Loading transcript from {context_file} ---")
                    return TranscriptionResult(**cached_data)
                else:
                    print(f"--- Cache Invalid: {context_file} is empty or malformed. Falling back to API. ---")
            except (json.JSONDecodeError, KeyError, Exception) as e:
                print(f"--- Cache Error: Could not read {context_file} ({e}). Falling back to API. ---")
        duration = await self._get_duration(audio_path)
        chunks = await self._split_audio(audio_path, duration)

        all_words = []
        full_text = ""
        detected_language = "en"

        for chunk_path, time_offset in chunks:
            try:
                with open(chunk_path, "rb") as file:
                    transcription = await self.client.audio.transcriptions.create(
                        file=(os.path.basename(chunk_path), file.read()),
                        model=self.model,
                        response_format="verbose_json",
                        timestamp_granularities=["word"] # Only requesting words
                    )

                    data = transcription.to_dict() if hasattr(transcription, "to_dict") else transcription.model_dump()
                    detected_language = data.get("language", detected_language)
                    full_text += data.get("text", "") + " "

                    # Verbose JSON with word granularity returns a top-level 'words' list
                    if "words" in data and data["words"]:
                        for word_data in data["words"]:
                            all_words.append(
                                Word(
                                    word=word_data["word"],
                                    start=word_data["start"] + time_offset,
                                    end=word_data["end"] + time_offset
                                )
                            )
            finally:
                if os.path.exists(chunk_path):
                    os.remove(chunk_path)

        return TranscriptionResult(
            text=full_text.strip(),
            words=all_words,
            language=detected_language
        )

    def save_transcription(self, result: TranscriptionResult, path: str):
        """Saves the flat word-level transcript."""
        data = result.model_dump()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)