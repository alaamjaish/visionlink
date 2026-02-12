# VisionLink - Unanswered Questions

Questions to revisit as development progresses.

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
- [ ] What microphone model are we using? (USB? I2S?)
- [ ] What speaker/output device? (3.5mm? Bluetooth? Bone conduction?)
- [ ] Power supply details for field use?

## Supabase
- [ ] Project URL and keys (need to create the project)
- [ ] Any rate limits or storage limits to worry about?

## Demo
- [ ] Which specific machines/equipment for the demo?
- [ ] What QR codes to prepare?
- [ ] Demo scenario/script?

## General
- [ ] How long should voice recording last per question? (currently hardcoded 5s)
- [ ] Should auto-capture photos be uploaded immediately or at session end?
- [ ] Battery life expectations?
