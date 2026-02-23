#!/usr/bin/env bash
set -euo pipefail

DURATION="${1:-10}"
OUT_MP4="${2:-/home/visionlink/Desktop/visionlink/tests/hardware/av_$(date +%Y%m%d_%H%M%S).mp4}"
WIDTH="${WIDTH:-1920}"
HEIGHT="${HEIGHT:-1080}"
FPS="${FPS:-30}"
VIDEO_BITRATE="${VIDEO_BITRATE:-12000000}"
AUDIO_DEVICE="${AUDIO_DEVICE:-default}"

mkdir -p "$(dirname "$OUT_MP4")"
TMPDIR=$(mktemp -d)
VID_H264="$TMPDIR/video.h264"
AUD_WAV="$TMPDIR/audio.wav"

cleanup() {
  rm -rf "$TMPDIR"
}
trap cleanup EXIT

# Record audio + video simultaneously.
arecord -D "$AUDIO_DEVICE" -f S16_LE -r 16000 -c 1 -d "$DURATION" "$AUD_WAV" >/tmp/visionlink_av_arecord.log 2>&1 &
APID=$!

rpicam-vid -o "$VID_H264" --width "$WIDTH" --height "$HEIGHT" --framerate "$FPS" --bitrate "$VIDEO_BITRATE" -t "$((DURATION * 1000))" >/tmp/visionlink_av_rpicam.log 2>&1
wait "$APID"

# Build final single MP4 with louder, limited audio.
ffmpeg -hide_banner -loglevel error -y \
  -framerate "$FPS" -i "$VID_H264" -i "$AUD_WAV" \
  -filter:a "volume=2.5,alimiter=limit=0.95" \
  -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 128k -shortest "$OUT_MP4"

echo "Created: $OUT_MP4"
