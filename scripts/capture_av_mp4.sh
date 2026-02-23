#!/usr/bin/env bash
set -euo pipefail

DURATION="${1:-10}"
OUT_MP4="${2:-/home/visionlink/Desktop/visionlink/tests/hardware/av_$(date +%Y%m%d_%H%M%S).mp4}"
WIDTH="${WIDTH:-1920}"
HEIGHT="${HEIGHT:-1080}"
FPS="${FPS:-30}"
VIDEO_BITRATE="${VIDEO_BITRATE:-12000000}"
AUDIO_DEVICE="${AUDIO_DEVICE:-default}"
# Additional manual tweak after automatic offset compensation (ms, can be negative)
SYNC_TWEAK_MS="${SYNC_TWEAK_MS:-0}"

mkdir -p "$(dirname "$OUT_MP4")"
TMPDIR=$(mktemp -d)
VID_H264="$TMPDIR/video.h264"
AUD_WAV="$TMPDIR/audio.wav"

cleanup() {
  rm -rf "$TMPDIR"
}
trap cleanup EXIT

# Record audio + video simultaneously.
audio_start_ns=$(date +%s%N)
arecord -D "$AUDIO_DEVICE" -f S16_LE -r 16000 -c 1 -d "$DURATION" "$AUD_WAV" >/tmp/visionlink_av_arecord.log 2>&1 &
APID=$!

video_start_ns=$(date +%s%N)
rpicam-vid -o "$VID_H264" --width "$WIDTH" --height "$HEIGHT" --framerate "$FPS" --bitrate "$VIDEO_BITRATE" -t "$((DURATION * 1000))" >/tmp/visionlink_av_rpicam.log 2>&1
wait "$APID"

# Compute start offset (seconds):
# offset > 0 means video started later than audio (audio should be delayed).
offset_sec=$(python3 - <<PY
audio_ns=$audio_start_ns
video_ns=$video_start_ns
tweak_ms=$SYNC_TWEAK_MS
print(((video_ns - audio_ns) / 1e9) + (tweak_ms / 1000.0))
PY
)

# Build final single MP4 with louder, limited audio.
python3 - <<PY > "$TMPDIR/mux_cmd.sh"
import shlex
fps = "$FPS"
vid = "$VID_H264"
aud = "$AUD_WAV"
out = "$OUT_MP4"
offset = float("$offset_sec")
base = [
    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
]
if offset >= 0:
    # Audio started earlier => delay audio input
    cmd = base + [
        "-framerate", fps, "-i", vid,
        "-itsoffset", f"{offset:.6f}", "-i", aud,
    ]
else:
    # Video started earlier => delay video input
    cmd = base + [
        "-itsoffset", f"{abs(offset):.6f}", "-framerate", fps, "-i", vid,
        "-i", aud,
    ]
cmd += [
    "-filter:a", "volume=2.5,alimiter=limit=0.95",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "128k", "-shortest", out,
]
print("#!/usr/bin/env bash")
print("set -euo pipefail")
print(" ".join(shlex.quote(x) for x in cmd))
PY
chmod +x "$TMPDIR/mux_cmd.sh"
"$TMPDIR/mux_cmd.sh"

echo "Created: $OUT_MP4"
echo "Auto sync offset applied (seconds): $offset_sec"
