"""
Gemini Text-to-Speech Integration

Converts text to speech using Gemini TTS (gemini-2.5-flash-tts).
Output: Raw PCM 16-bit 24kHz -> converted to WAV for playback.
"""

import io
import time
import wave

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

logger = get_logger("tts")


class TextToSpeech:
    """Gemini TTS client for converting text to speech."""

    def __init__(self):
        self._client = None

    def setup(self) -> bool:
        """Initialize Gemini client for TTS."""
        if not HAS_GENAI:
            logger.warning("google-genai package not available")
            return False

        if not config.GEMINI_API_KEY:
            logger.warning("Gemini API key not configured")
            return False

        try:
            self._client = genai.Client(api_key=config.GEMINI_API_KEY)
            logger.info("Gemini TTS initialized")
            return True
        except Exception as e:
            logger.error(f"TTS setup failed: {e}", exc_info=True)
            return False

    def synthesize(self, text: str) -> bytes:
        """Convert text to PCM audio bytes (16-bit, 24kHz, mono)."""
        if not self._client:
            logger.error("TTS not initialized")
            return b""

        try:
            start = time.time()

            response = self._client.models.generate_content(
                model=config.GEMINI_TTS_MODEL,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=config.GEMINI_TTS_VOICE,
                            )
                        )
                    ),
                ),
            )

            # Extract PCM audio data
            pcm_data = b""
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    pcm_data += part.inline_data.data

            elapsed = time.time() - start
            logger.info(f"TTS synthesized ({elapsed:.2f}s): '{text[:60]}...' -> {len(pcm_data)} bytes PCM")
            return pcm_data
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}", exc_info=True)
            return b""

    def synthesize_to_wav(self, text: str) -> bytes:
        """Convert text to WAV audio bytes (ready for playback)."""
        pcm_data = self.synthesize(text)
        if not pcm_data:
            return b""

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(config.TTS_SAMPLE_RATE)
            wf.writeframes(pcm_data)
        return wav_buffer.getvalue()

    def save_wav(self, text: str, output_path: str) -> bool:
        """Synthesize text and save as WAV file."""
        wav_data = self.synthesize_to_wav(text)
        if not wav_data:
            return False

        try:
            with open(output_path, 'wb') as f:
                f.write(wav_data)
            logger.info(f"TTS saved: {output_path}")
            return True
        except Exception as e:
            logger.error(f"TTS save failed: {e}", exc_info=True)
            return False
