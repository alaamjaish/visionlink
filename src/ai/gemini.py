"""
Gemini AI Integration

Handles multimodal AI queries (text + image) using Google Gemini.
Maintains conversation history with a 30-minute sliding window.
"""

import time
import base64
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent))

import config
from src.utils.logger import get_logger

logger = get_logger("gemini")


class GeminiAI:
    """Gemini AI client for multimodal queries and agent functions."""

    def __init__(self):
        self._client = None
        self._history = []  # List of {"role": str, "text": str, "timestamp": float}

    def setup(self) -> bool:
        """Initialize Gemini client."""
        if not HAS_GENAI:
            logger.warning("google-genai package not available")
            return False

        if not config.GEMINI_API_KEY:
            logger.warning("Gemini API key not configured")
            return False

        try:
            start = time.time()
            self._client = genai.Client(api_key=config.GEMINI_API_KEY)
            elapsed = time.time() - start
            logger.info(f"Gemini AI initialized ({elapsed:.2f}s)")
            return True
        except Exception as e:
            logger.error(f"Gemini setup failed: {e}", exc_info=True)
            return False

    def _get_system_prompt(self) -> str:
        """Return the system prompt for the AI assistant."""
        lang_note = "Respond in English." if config.LANGUAGE == "en" else "Respond in Turkish."
        return f"""You are VisionLink, a wearable industrial assistant on a factory floor.
You help workers with machine operation, maintenance, troubleshooting, and safety.
Keep responses concise and clear - they will be spoken aloud.
{lang_note}
If you see a QR code or machine label in an image, identify it and provide relevant information.
If asked about maintenance, safety, or procedures, give step-by-step instructions.
Be helpful, professional, and safety-conscious."""

    def _prune_history(self):
        """Remove conversation entries older than AI_MEMORY_WINDOW."""
        cutoff = time.time() - config.AI_MEMORY_WINDOW
        before = len(self._history)
        self._history = [h for h in self._history if h["timestamp"] > cutoff]
        pruned = before - len(self._history)
        if pruned > 0:
            logger.debug(f"Pruned {pruned} old history entries")

    def _build_contents(self, text: str, image_path: str = None) -> list:
        """Build the contents list for a Gemini request."""
        self._prune_history()

        contents = []

        # Add system prompt
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(self._get_system_prompt())]
        ))
        contents.append(types.Content(
            role="model",
            parts=[types.Part.from_text("Understood. I'm VisionLink, ready to assist.")]
        ))

        # Add history
        for entry in self._history:
            contents.append(types.Content(
                role=entry["role"],
                parts=[types.Part.from_text(entry["text"])]
            ))

        # Add current query
        parts = []
        if image_path and Path(image_path).exists():
            with open(image_path, "rb") as f:
                image_data = f.read()
            parts.append(types.Part.from_bytes(
                data=image_data,
                mime_type="image/jpeg"
            ))
        parts.append(types.Part.from_text(text))

        contents.append(types.Content(role="user", parts=parts))

        return contents

    def query(self, text: str, image_path: str = None) -> str:
        """Send a query to Gemini and get a text response."""
        if not self._client:
            logger.error("Gemini not initialized")
            return "AI is not available right now."

        try:
            start = time.time()
            contents = self._build_contents(text, image_path)

            response = self._client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=contents,
            )

            result = response.text
            elapsed = time.time() - start

            # Save to history
            self._history.append({"role": "user", "text": text, "timestamp": time.time()})
            self._history.append({"role": "model", "text": result, "timestamp": time.time()})

            logger.info(f"Gemini query ({elapsed:.2f}s): '{text[:60]}...' -> '{result[:60]}...'")
            return result
        except Exception as e:
            logger.error(f"Gemini query failed: {e}", exc_info=True)
            return "Sorry, I couldn't process that request."

    def query_with_image(self, text: str, image_path: str) -> str:
        """Query with both text and an image."""
        return self.query(text, image_path=image_path)

    def clear_history(self):
        """Clear conversation history."""
        self._history.clear()
        logger.info("AI conversation history cleared")
