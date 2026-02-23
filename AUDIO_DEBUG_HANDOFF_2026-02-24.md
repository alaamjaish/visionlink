# VisionLink Audio Debug Handoff (2026-02-24)

This document captures the full mic/speaker debugging work done on the Raspberry Pi, what failed, what worked, and how to reproduce the current good state quickly.

## 1. Executive Outcome

- Speaker output on I2S is confirmed working.
- Microphone input is confirmed working.
- Mic quality issue is no longer "no signal"; it is now a "noise floor / tuning" problem.
- Recording is now automated in project code via ALSA (`arecord`) backend fallback, so we no longer depend on ad-hoc terminal debug sequences.

## 2. Root Causes Found

1. I2S was initially disabled (`dtparam=i2s=on` was commented out).
2. ALSA routing was missing or inconsistent during early tests.
3. Overlay experiments showed `max98357a` + `adau7002-simple` conflict on the same `sound` node (last overlay wins), which broke simultaneous capture/playback for our setup.
4. On `googlevoicehat-soundcard`, mic data appeared on one slot only (left), while the other slot was zero.
5. VNC was misleading for audio validation (video/sound in VNC is not a reliable hardware audio check).

## 3. Final Working System State

### 3.1 Boot config

File: `/boot/firmware/config.txt`

Required lines:

```ini
dtparam=i2s=on

# VisionLink I2S Audio (mic + speaker/amp)
dtoverlay=googlevoicehat-soundcard
#dtoverlay=max98357a,no-sdmode
#dtoverlay=adau7002-simple,card-name=mic
```

### 3.2 ALSA user config

File: `~/.asoundrc`

Current behavior:
- Defines `speaker`, `mic_left_raw`, `mic_right_raw`, `mic_left`, `mic_right`.
- Default capture is routed to `mic_left`.
- Default playback is routed to `speaker`.

### 3.3 Hardware cards (expected)

- `aplay -l` should include card 3: `snd_rpi_googlevoicehat_soundcard`
- `arecord -l` should include card 3 capture device

## 4. Validation Results That Proved It

## 4.1 Speaker proven

- `speaker-test -D plughw:3,0 -c 2 -t sine -f 1000 -l 1`
- `aplay -D plughw:3,0 /usr/share/sounds/alsa/Front_Center.wav`

Both produced audible output from the physical speaker.

## 4.2 Mic proven

Successful captures produced non-zero bytes and measurable levels, e.g.:
- `mean_volume` around `-33 dB` to `-24 dB` depending on speaking distance
- non-zero sample percentage > 50% on working captures

Earlier all-zero captures (`-91 dB`) were real failures, not playback UI issues.

## 5. Why Voice Sounded Bad Even After It Started Working

- Signal was present but noisy.
- Quiet-vs-speech delta was small in raw data (~2-3 dB in one test), indicating high noise floor.
- This is now a quality-tuning problem (filters/gain/noise suppression), not a “mic not connected” problem.

## 6. Automation Added In Repo

## 6.1 One-command audio workflows

File: `Makefile`

Commands:

```bash
cd ~/Desktop/visionlink
make audio-devices
make audio-capture DURATION=5
make audio-capture-noplay DURATION=5
make audio-default-check
```

`audio-capture` runs the full flow: capture raw -> auto-select active channel -> clean output -> optional playback.

## 6.2 Reusable capture/clean script

File: `tests/hardware/mic_capture_clean.sh`

Usage:

```bash
./tests/hardware/mic_capture_clean.sh 5 /home/visionlink/Desktop/visionlink/tests/hardware/mic_run play
```

Outputs:
- `<base>_raw.wav`
- `<base>_clean.wav`
- selected channel + volume stats

## 6.3 App-level recording automation (important)

File updated: `src/hardware/audio.py`

`AudioRecorder` now:
- Prefers ALSA `arecord` backend automatically (`AUDIO_BACKEND=auto`)
- Falls back to PyAudio only if needed
- Uses ALSA default input device from config (`AUDIO_INPUT_DEVICE=default`)

This means main app recording buttons now use the stable ALSA route without manual debug commands.

## 6.4 Audio config knobs added

File updated: `config.py` and `.env.example`

New options:
- `AUDIO_BACKEND` (`auto` / `alsa` / `pyaudio`)
- `AUDIO_INPUT_DEVICE` (default `default`)
- `AUDIO_ARECORD_FORMAT` (default `S16_LE`)

## 7. Files Changed During This Fix

Inside repo (`~/Desktop/visionlink`):
- `src/hardware/audio.py`
- `config.py`
- `.env.example`
- `Makefile`
- `tests/hardware/mic_capture_clean.sh`
- `AUDIO_DEBUG_HANDOFF_2026-02-24.md` (this file)

Outside repo (system/user config):
- `/boot/firmware/config.txt`
- `~/.asoundrc`

## 8. Fast Recovery Checklist (If Audio Breaks Again)

1. Verify overlay lines in `/boot/firmware/config.txt`.
2. Reboot.
3. Run `make audio-devices` and confirm card 3 capture+playback exists.
4. Run `make audio-default-check` and verify file is non-empty.
5. Run `make audio-capture DURATION=5` and listen to `*_clean.wav`.
6. If capture is zero:
   - Re-check mic wiring: BCLK(GPIO18), LRCLK(GPIO19), DOUT(GPIO20), SEL->GND
   - Confirm shared GND
   - Re-seat jumper wires

## 9. Practical Next Steps

1. Integrate the clean filter chain into STT preprocessing path (optional but recommended).
2. Add a startup self-test routine (10-second audio health check) and log pass/fail.
3. Optionally add AGC/noise suppression tuning for your real room environment.

