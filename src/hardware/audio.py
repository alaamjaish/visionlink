"""
Audio Module

Handles microphone recording and speaker playback.
- Recording: PyAudio (for STT input)
- Playback: pygame (for TTS output and beeps)
"""

import io
import wave
import struct
import threading
import time
from pathlib import Path

try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False

try:
    import pygame
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent))

import config
from src.utils.logger import get_logger

logger = get_logger("audio")


class AudioPlayer:
    """Handles audio playback via pygame."""

    def __init__(self):
        self._initialized = False

    def setup(self):
        """Initialize pygame mixer for audio playback."""
        if not HAS_PYGAME:
            logger.warning("pygame not available - audio playback disabled")
            return False

        try:
            pygame.mixer.init(frequency=config.TTS_SAMPLE_RATE, size=-16, channels=1)
            self._initialized = True
            logger.info("Audio player initialized")
            return True
        except Exception as e:
            logger.error(f"Audio player setup failed: {e}", exc_info=True)
            return False

    def play_wav(self, wav_path: str):
        """Play a WAV file."""
        if not self._initialized:
            logger.error("Audio player not initialized")
            return

        try:
            start = time.time()
            pygame.mixer.music.load(wav_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            elapsed = time.time() - start
            logger.info(f"Played audio: {wav_path} ({elapsed:.2f}s)")
        except Exception as e:
            logger.error(f"Audio playback failed: {e}", exc_info=True)

    def play_pcm(self, pcm_data: bytes, sample_rate: int = None):
        """Play raw PCM 16-bit data by converting to WAV in memory."""
        if not self._initialized:
            logger.error("Audio player not initialized")
            return

        if sample_rate is None:
            sample_rate = config.TTS_SAMPLE_RATE

        try:
            # Convert PCM to WAV in memory
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(sample_rate)
                wf.writeframes(pcm_data)
            wav_buffer.seek(0)

            pygame.mixer.music.load(wav_buffer, "wav")
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            logger.info(f"Played PCM audio ({len(pcm_data)} bytes)")
        except Exception as e:
            logger.error(f"PCM playback failed: {e}", exc_info=True)

    def play_beep(self):
        """Play a short beep for button feedback."""
        if not self._initialized:
            return

        try:
            beep_file = config.SOUNDS_DIR / "beep.wav"
            if beep_file.exists():
                pygame.mixer.Sound(str(beep_file)).play()
            else:
                # Generate a simple beep tone
                self._play_tone(frequency=1000, duration_ms=100)
            logger.debug("Beep played")
        except Exception as e:
            logger.error(f"Beep failed: {e}", exc_info=True)

    def _play_tone(self, frequency: int = 1000, duration_ms: int = 100):
        """Generate and play a simple sine wave tone."""
        sample_rate = 44100
        n_samples = int(sample_rate * duration_ms / 1000)
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            import math
            for i in range(n_samples):
                value = int(16000 * math.sin(2 * math.pi * frequency * i / sample_rate))
                wf.writeframes(struct.pack('<h', value))
        buf.seek(0)
        sound = pygame.mixer.Sound(buf)
        sound.play()
        time.sleep(duration_ms / 1000 + 0.05)

    def speak(self, text: str):
        """Speak text using Gemini TTS. Placeholder - actual TTS in ai/tts.py."""
        logger.info(f"speak() called with: {text[:80]}...")

    def cleanup(self):
        """Clean up pygame mixer."""
        if self._initialized:
            pygame.mixer.quit()
            logger.info("Audio player cleaned up")


class AudioRecorder:
    """Handles microphone recording via PyAudio."""

    def __init__(self):
        self._pa = None
        self._stream = None
        self._recording = False
        self._frames = []

    def setup(self):
        """Initialize PyAudio."""
        if not HAS_PYAUDIO:
            logger.warning("pyaudio not available - recording disabled")
            return False

        try:
            self._pa = pyaudio.PyAudio()
            logger.info("Audio recorder initialized")
            return True
        except Exception as e:
            logger.error(f"Audio recorder setup failed: {e}", exc_info=True)
            return False

    def start_recording(self):
        """Start recording from microphone."""
        if not self._pa:
            logger.error("Audio recorder not initialized")
            return False

        if self._recording:
            logger.warning("Already recording")
            return False

        try:
            self._frames = []
            self._stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=config.AUDIO_CHANNELS,
                rate=config.AUDIO_SAMPLE_RATE,
                input=True,
                frames_per_buffer=config.AUDIO_CHUNK_SIZE,
                stream_callback=self._audio_callback
            )
            self._recording = True
            logger.info("Microphone recording started")
            return True
        except Exception as e:
            logger.error(f"Recording start failed: {e}", exc_info=True)
            return False

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback to collect audio frames."""
        if self._recording:
            self._frames.append(in_data)
        return (None, pyaudio.paContinue)

    def stop_recording(self) -> bytes:
        """Stop recording and return WAV data as bytes."""
        if not self._recording:
            return b""

        self._recording = False

        try:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None

            # Convert to WAV bytes
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(config.AUDIO_CHANNELS)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(config.AUDIO_SAMPLE_RATE)
                wf.writeframes(b''.join(self._frames))
            wav_data = wav_buffer.getvalue()

            logger.info(f"Recording stopped ({len(self._frames)} chunks, {len(wav_data)} bytes)")
            self._frames = []
            return wav_data
        except Exception as e:
            logger.error(f"Recording stop failed: {e}", exc_info=True)
            return b""

    def save_recording(self, output_path: str) -> bool:
        """Stop recording and save to WAV file."""
        wav_data = self.stop_recording()
        if not wav_data:
            return False

        try:
            with open(output_path, 'wb') as f:
                f.write(wav_data)
            logger.info(f"Recording saved: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Save recording failed: {e}", exc_info=True)
            return False

    def is_recording(self) -> bool:
        return self._recording

    def cleanup(self):
        """Clean up PyAudio resources."""
        if self._recording:
            self.stop_recording()
        if self._pa:
            self._pa.terminate()
            self._pa = None
        logger.info("Audio recorder cleaned up")
