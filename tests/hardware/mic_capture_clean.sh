#!/usr/bin/env bash
set -euo pipefail

DURATION="${1:-5}"
OUT_BASE="${2:-/home/visionlink/Desktop/visionlink/tests/hardware/mic_run}"
PLAY="${3:-play}" # play|noplay

RAW="${OUT_BASE}_raw.wav"
CLEAN="${OUT_BASE}_clean.wav"

mkdir -p "$(dirname "$OUT_BASE")"

# 1) Capture hardware-native stream.
arecord -D hw:3,0 -f S32_LE -r 48000 -c 2 -d "$DURATION" "$RAW" >/tmp/mic_capture_clean.log 2>&1

# 2) Pick the active channel based on RMS power.
CH=$(RAW_PATH="$RAW" python3 - <<'PY'
import os, struct
p=os.environ["RAW_PATH"]
with open(p,'rb') as f: b=f.read()
d=b[44:]
N=len(d)//8
if N<=0:
    print('left')
    raise SystemExit(0)
ls=0.0
rs=0.0
for i in range(N):
    l=struct.unpack_from('<i',d,i*8)[0]
    r=struct.unpack_from('<i',d,i*8+4)[0]
    ls += l*l
    rs += r*r
lr=(ls/N)**0.5
rr=(rs/N)**0.5
print('left' if lr>=rr else 'right')
PY
)

if [[ "$CH" == "left" ]]; then
  PAN="pan=mono|c0=c0"
else
  PAN="pan=mono|c0=c1"
fi

# 3) Cleanup chain tuned for this noisy setup.
# Adjustments are intentionally conservative to preserve speech consonants.
FF="${PAN},highpass=f=140,lowpass=f=3400,agate=threshold=0.02:ratio=5:attack=15:release=220,volume=12,alimiter=limit=0.95"
ffmpeg -hide_banner -loglevel error -y -i "$RAW" -af "$FF" -ar 16000 -ac 1 -c:a pcm_s16le "$CLEAN"

# 4) Print quick stats.
RAW_STATS=$(RAW_PATH="$RAW" python3 - <<'PY'
import os, math, struct
p=os.environ["RAW_PATH"]
with open(p,'rb') as f:b=f.read()
d=b[44:]
N=len(d)//8
if N<=0:
    print('{"frames":0}')
    raise SystemExit(0)
ls=0.0; rs=0.0
for i in range(N):
    l=struct.unpack_from('<i',d,i*8)[0]
    r=struct.unpack_from('<i',d,i*8+4)[0]
    ls+=l*l; rs+=r*r
lr=(ls/N)**0.5; rr=(rs/N)**0.5
ldb=-999 if lr==0 else 20*math.log10(lr/2147483647)
rdb=-999 if rr==0 else 20*math.log10(rr/2147483647)
print('{"left_rms_dbfs":%.2f,"right_rms_dbfs":%.2f}'%(ldb,rdb))
PY
)

CLEAN_VOL=$(ffmpeg -hide_banner -i "$CLEAN" -af volumedetect -f null /dev/null 2>&1 | grep -E 'mean_volume|max_volume' | tr '\n' '; ')

echo "capture_log: /tmp/mic_capture_clean.log"
echo "selected_channel: $CH"
echo "raw_file: $RAW"
echo "clean_file: $CLEAN"
echo "raw_stats: $RAW_STATS"
echo "clean_stats: $CLEAN_VOL"

if [[ "$PLAY" == "play" ]]; then
  aplay -D speaker "$CLEAN"
fi
