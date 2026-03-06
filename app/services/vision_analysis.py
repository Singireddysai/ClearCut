import os
import json
import asyncio
import logging
import sys
from google import genai
from google.genai import types
from pydantic import BaseModel

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class SceneDescription(BaseModel):
    time_offset: int
    description: str
    frame_path: str

class VisionService:
    def __init__(self, api_key: str, rpm_limit: int = 30):
        self.client = genai.Client(api_key=api_key)
        self.model_id = 'gemma-3-27b-it'
        
        self.rate_limiter = asyncio.Semaphore(1)
        self.delay = 60.0 / rpm_limit
        logger.info(f"VisionService initialized with {rpm_limit} RPM limit.")
    
    async def process_frames(self, frame_paths, interval: int = 10, context_file: str = None):
        # Cache Check: Return existing data if available
        if context_file and os.path.exists(context_file):
            logger.info(f"Found existing vision context at {context_file}. Loading from cache.")
            try:
                with open(context_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                
                # Reconstruct the Pydantic models from the JSON dicts
                logger.info("Successfully loaded vision context from file.")
                return [SceneDescription(**item) for item in cached_data]
            except Exception as e:
                logger.error(f"Failed to load cache from {context_file}: {e}. Falling back to API.")
        
        logger.info(f"Starting analysis for {len(frame_paths)} frames at {interval}s intervals.")
        tasks = []

        for frame_path in frame_paths:
            try:
                # Extract frame index from filename
                frame_index = int(frame_path.split("_")[-1].split(".")[0]) - 1
                offset = frame_index * interval
                tasks.append(self.analyze_frame(frame_path, offset))
            except Exception as e:
                logger.error(f"Failed to parse offset for frame {frame_path}: {e}")

        results = await asyncio.gather(*tasks)
        results.sort(key=lambda x: x.time_offset)
        
        logger.info("Vision analysis of all frames complete.")
        return results

    async def analyze_frame(self, frame_path: str, time_offset: int) -> SceneDescription:
        async with self.rate_limiter:
            try:
                logger.info(f"Analyzing frame at {time_offset}s: {frame_path}")
                
                with open(frame_path, "rb") as f:
                    image_bytes = f.read()

                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.models.generate_content(
                        model=self.model_id,
                        contents=[
                            types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                            'Describe this image in one line capturing the details visible. Do not give any fillers or acknowledgements. Format: The image shows [action or objects in the image]'
                        ]
                    )
                )

                description = response.text.strip()
                logger.info(f"Success at {time_offset}s: {description[:50]}...")

                # Rate limit buffer
                await asyncio.sleep(self.delay)

                return SceneDescription(
                    time_offset=time_offset,
                    description=description,
                    frame_path=frame_path
                )

            except Exception as e:
                logger.error(f"Vision Error at {time_offset}s ({frame_path}): {e}")
                return SceneDescription(
                    time_offset=time_offset,
                    description="[Description unavailable]",
                    frame_path=frame_path
                )