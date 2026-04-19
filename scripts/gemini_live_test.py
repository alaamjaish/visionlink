"""
Gemini Live API smoke test for VisionLink.

What this does:
  - Opens the I2S microphone (through ALSA "default")
  - Streams your voice in real time to Google's gemini-3.1-flash-live-preview
  - Plays Gemini's voice response out through the I2S speaker
  - Prints everything happening to the terminal

Run:
    python3 scripts/gemini_live_test.py

Stop:
    Press Ctrl+C

Requires:
    - GEMINI_API_KEY set in .env (in project root)
    - google-genai >= 1.73.0
    - sounddevice + libportaudio2
    - /boot/firmware/config.txt with dtoverlay=googlevoicehat-soundcard
    - ~/.asoundrc routing default playback to "speaker" and capture to "mic_left"
"""

import asyncio
import os
import signal
import sys
import traceback
from pathlib import Path

import sounddevice as sd
from dotenv import load_dotenv
from google import genai
from google.genai import types


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = "gemini-3.1-flash-live-preview"

MIC_RATE = 16000        # Gemini Live input format
SPEAKER_RATE = 24000    # Gemini Live output format
CHANNELS = 1
BLOCK = 1600            # 100 ms @ 16 kHz


def header(msg: str) -> None:
    print(f"\n==== {msg} ====", flush=True)


def fail(msg: str) -> None:
    print(f"[X] {msg}", flush=True)


def info(msg: str) -> None:
    print(f"[.] {msg}", flush=True)


async def send_mic(session, mic_stream):
    """Read PCM frames from the mic and forward to Gemini."""
    info("Mic task started - speak into the microphone now.")
    loop = asyncio.get_running_loop()
    while True:
        data, _ = await loop.run_in_executor(None, mic_stream.read, BLOCK)
        await session.send_realtime_input(
            audio=types.Blob(data=bytes(data), mime_type=f"audio/pcm;rate={MIC_RATE}")
        )


async def receive_audio(session, spk_stream):
    """Receive audio + text events from Gemini and play / print them."""
    info("Receive task started - waiting for Gemini response.")
    async for message in session.receive():
        if getattr(message, "data", None):
            spk_stream.write(message.data)
        server_content = getattr(message, "server_content", None)
        if server_content is None:
            continue
        input_tx = getattr(server_content, "input_transcription", None)
        output_tx = getattr(server_content, "output_transcription", None)
        if input_tx and input_tx.text:
            print(f"[you said]  {input_tx.text}", flush=True)
        if output_tx and output_tx.text:
            print(f"[gemini]    {output_tx.text}", flush=True)
        if getattr(server_content, "turn_complete", False):
            print("[.] --- turn complete ---", flush=True)


async def run():
    header("VisionLink Gemini Live smoke test")

    if not API_KEY:
        fail("GEMINI_API_KEY is empty in .env. Paste your key there and re-run.")
        return

    info(f"Model: {MODEL}")
    info(f"Mic in: {MIC_RATE} Hz mono  ->  Speaker out: {SPEAKER_RATE} Hz mono")

    client = genai.Client(api_key=API_KEY, http_options={"api_version": "v1alpha"})
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        system_instruction=types.Content(parts=[types.Part.from_text(
            text=(
                "You are VisionLink, a friendly wearable assistant for a factory worker. "
                "Keep replies short and spoken-friendly. If the user greets you, greet back "
                "and confirm you can hear them."
            )
        )]),
    )

    header("Opening audio devices")
    mic_stream = sd.RawInputStream(
        samplerate=MIC_RATE, channels=CHANNELS, dtype="int16", blocksize=BLOCK
    )
    spk_stream = sd.RawOutputStream(
        samplerate=SPEAKER_RATE, channels=CHANNELS, dtype="int16"
    )
    mic_stream.start()
    spk_stream.start()
    info("Mic + speaker streams open.")

    header("Connecting to Gemini Live")
    try:
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            info("Connected. Start talking - press Ctrl+C to end.")
            await asyncio.gather(
                send_mic(session, mic_stream),
                receive_audio(session, spk_stream),
            )
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        fail(f"Gemini Live error: {exc}")
        traceback.print_exc()
    finally:
        mic_stream.stop(); mic_stream.close()
        spk_stream.stop(); spk_stream.close()
        info("Audio devices closed.")


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(run())
    try:
        loop.add_signal_handler(signal.SIGINT, task.cancel)
    except NotImplementedError:
        pass
    try:
        loop.run_until_complete(task)
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\n[.] Stopped by user.")
    finally:
        loop.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
