.PHONY: audio-devices audio-capture audio-capture-noplay audio-default-check

DURATION ?= 5
AUDIO_OUT ?= tests/hardware/mic_run_$(shell date +%Y%m%d_%H%M%S)

# Show ALSA playback/capture hardware cards.
audio-devices:
	aplay -l
	@echo
	arecord -l

# Capture + clean + auto-channel-select + playback.
audio-capture:
	./tests/hardware/mic_capture_clean.sh $(DURATION) "$(PWD)/$(AUDIO_OUT)" play

# Same as audio-capture, but does not play the result.
audio-capture-noplay:
	./tests/hardware/mic_capture_clean.sh $(DURATION) "$(PWD)/$(AUDIO_OUT)" noplay

# Sanity-check the app's default capture path (used by AudioRecorder backend=alsa).
audio-default-check:
	arecord -D default -f S16_LE -r 16000 -c 1 -d 2 "$(PWD)/tests/hardware/mic_default_check.wav"

.PHONY: video-av

VIDEO_DURATION ?= 10
VIDEO_OUT ?= tests/hardware/av_$(shell date +%Y%m%d_%H%M%S).mp4

# Record one single MP4 with camera + mic together.
video-av:
	./scripts/capture_av_mp4.sh $(VIDEO_DURATION) "$(PWD)/$(VIDEO_OUT)"
