# VisionLink - Unanswered Questions

Questions to revisit as development progresses.

## Current Review - 2026-04-19
- [ ] Are all 6 buttons now physically connected, and do they match the current BCM pins in `config.py`? (17, 27, 22, 5, 6, 13)
- [ ] Should Button 2 video use the newer single-file audio+video path from `scripts/capture_av_mp4.sh` instead of the current camera-only app path?
- [ ] Which speech-to-text path should we finish first: Soniox as originally planned, or a simpler temporary STT option for the demo?
- [ ] Should documentation-mode spoken feedback be wired through real TTS? `AudioPlayer.speak()` currently only logs text.
- [ ] Where are the real `.env` values? The local project currently has no configured API/service secrets.
- [ ] Should `visionlink.service` be corrected from `/home/visionlink/Desktop/VisionLink` to `/home/visionlink/Desktop/visionlink` before enabling auto-start?

## Soniox SDK
- [ ] What is the exact Python API for transcription? (file vs stream vs bytes)
- [ ] Does it support Turkish language?
- [ ] What audio format does it expect? (WAV, PCM, sample rate)
- [ ] Is there a streaming mode for real-time transcription?

## Gemini TTS
- [ ] Does gemini-2.5-flash-tts support Turkish language?
- [ ] Which voice works best for industrial assistant context?
- [ ] What's the latency like on Pi over Wi-Fi?

## Hardware
- [ ] Which exact GPIO pins will the 6 buttons use? (currently using 17,27,22,5,6,13)
- [x] What microphone model are we using? SPH0645LM4H I2S MEMS microphone.
- [x] What speaker/output device? MAX98357A I2S amplifier with 8 Ohm mini speaker.
- [ ] Power supply details for field use?

## Supabase
- [ ] Project URL and keys (need to create the project)
- [ ] Any rate limits or storage limits to worry about?

## Demo
- [ ] Which specific machines/equipment for the demo?
- [ ] What QR codes to prepare?
- [ ] Demo scenario/script?
- [ ] What's the ONE storyline for the final grad presentation? (e.g. "worker documents a broken machine" vs "worker asks AI what a part is")

## General
- [ ] How long should voice recording last per question? (currently hardcoded 5s)
- [ ] Should auto-capture photos be uploaded immediately or at session end?
- [ ] Battery life expectations?
- [ ] Startup behavior on boot: play confirmation sound, speak a phrase, or silent?
- [ ] Offline fallback: what should the device do if Wi-Fi drops mid-operation? (queue + retry / error speech / silently fail?)
- [ ] When Button 2 is in video mode, should Button 1 (end session) be blocked, or should it stop the video first and then end?
- [ ] Should "documentation mode" and "AI assistant mode" share the same session folder, or be entirely separate logs?

## Video + Audio Sync (new, Apr 2026)
- [ ] Confirmed approach for recording sound WITH video (currently camera.py has no audio track) — tracked as Q3 in today's kickoff conversation
