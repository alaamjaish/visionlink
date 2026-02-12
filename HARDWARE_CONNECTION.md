# VisionLink - Hardware Connection Guide

## Our Hardware

| Component | Model | Interface |
|-----------|-------|-----------|
| Computer | Raspberry Pi 4B (8GB RAM) | - |
| Camera | Raspberry Pi Camera Module 3 | CSI ribbon cable |
| Microphone | SPH0645LM4H (I2S MEMS) | I2S (GPIO wires) |
| Amplifier | MAX98357A (I2S Mono) | I2S (GPIO wires) |
| Speaker | 8 Ohm 1W Mini Oval (Adafruit) | Wires to amplifier |
| Buttons | Tactile push buttons x6 | GPIO pins |
| Power | Power bank (TBD) | USB-C |

---

## 1. Camera Module 3 (CSI Connection)

**What you need:** The camera + its flat ribbon cable.

### Steps:
1. **Power off** the Pi completely (unplug power)
2. Locate the **CSI camera port** - it's the slot between the HDMI and audio jack, labeled "CAMERA"
3. Gently pull up the black plastic clip on the CSI connector
4. Insert the ribbon cable with the **blue side facing the USB ports** (metal contacts face the HDMI side)
5. Push the black clip back down firmly to lock the cable
6. Power on the Pi

### Software Setup:
```bash
# Test if camera is detected
libcamera-hello --timeout 5000

# Take a test photo
libcamera-still -o test.jpg

# If not working, check config
sudo raspi-config
# -> Interface Options -> Camera -> Enable
# Reboot after enabling
```

### Troubleshooting:
- "No cameras available" → reseat the ribbon cable, make sure clip is locked
- Cable is fragile - don't bend it sharply
- The camera module 3 uses libcamera (not the old raspistill)

---

## 2. I2S MEMS Microphone - SPH0645LM4H

**IMPORTANT:** This is an I2S digital microphone, NOT a USB mic. It connects directly to GPIO pins and needs kernel driver configuration.

### Wiring (Microphone → Raspberry Pi)

| Mic Pin | Pi Pin | Pi GPIO | Description |
|---------|--------|---------|-------------|
| 3V | Pin 1 | 3.3V Power | Power supply |
| GND | Pin 6 | Ground | Ground |
| BCLK | Pin 12 | GPIO 18 | Bit clock |
| LRCLK (WS) | Pin 35 | GPIO 19 | Word select (left/right) |
| DOUT | Pin 38 | GPIO 20 | Data out (mic audio) |
| SEL | GND or leave floating | - | Channel select (GND=left, 3V=right) |

### Software Setup:
```bash
# Step 1: Enable I2S
sudo nano /boot/firmware/config.txt
# Add this line at the end:
dtoverlay=googlevoicehat-soundcard
# OR for generic I2S input:
# dtoverlay=i2s-mmap

# Step 2: Reboot
sudo reboot

# Step 3: Check if microphone is detected
arecord -l
# Should show a capture device

# Step 4: Test recording (5 seconds)
arecord -D plughw:1,0 -f S32_LE -r 16000 -c 1 -d 5 test_mic.wav

# Step 5: Play back to verify
aplay test_mic.wav
```

### ALSA Configuration:
Create/edit `~/.asoundrc`:
```
pcm.!default {
    type asym
    playback.pcm "speaker"
    capture.pcm "mic"
}

pcm.mic {
    type plug
    slave {
        pcm "hw:1,0"
        format S32_LE
        rate 16000
        channels 1
    }
}

pcm.speaker {
    type plug
    slave {
        pcm "hw:2,0"
    }
}
```
**Note:** The card numbers (hw:1,0 and hw:2,0) may be different on your Pi. Run `arecord -l` and `aplay -l` to find the correct numbers.

### Open Questions:
- [ ] Which I2S overlay works best with SPH0645? (`googlevoicehat-soundcard` vs `i2s-mmap` vs custom overlay)
- [ ] SEL pin: connect to GND for left channel, or leave floating?
- [ ] Does the mic need a specific format (S32_LE) or can we use S16_LE?

---

## 3. I2S Amplifier - MAX98357A + Speaker

**IMPORTANT:** This is also I2S. Both the mic and amp share the I2S bus but use different data pins.

### Wiring (Amplifier → Raspberry Pi)

| Amp Pin | Pi Pin | Pi GPIO | Description |
|---------|--------|---------|-------------|
| Vin | Pin 2 | 5V Power | Power (5V for louder output) |
| GND | Pin 9 | Ground | Ground |
| BCLK | Pin 12 | GPIO 18 | Bit clock (SHARED with mic) |
| LRC (LRCLK) | Pin 35 | GPIO 19 | Word select (SHARED with mic) |
| DIN | Pin 40 | GPIO 21 | Data in (audio to speaker) |
| GAIN | Leave floating | - | 9dB gain (or wire to GND for 12dB, or 3.3V for 15dB) |
| SD | Leave floating or 3.3V | - | Shutdown (floating=on, GND=shutdown) |

### Speaker Connection:
- Solder/connect the **8 Ohm 1W speaker** wires to the **+ and -** terminals on the MAX98357A board
- Polarity matters: match + to + if marked on speaker

### Software Setup:
```bash
# Step 1: Enable I2S output
sudo nano /boot/firmware/config.txt
# Add (if not already there from mic setup):
dtoverlay=hifiberry-dac
# OR if using googlevoicehat-soundcard, it may handle both

# Step 2: Reboot
sudo reboot

# Step 3: Check if speaker is detected
aplay -l
# Should show a playback device

# Step 4: Test playback
speaker-test -t wav -c 1

# Step 5: Adjust volume
alsamixer
# Use arrow keys to adjust, ESC to exit
```

### Open Questions:
- [ ] Can googlevoicehat-soundcard handle BOTH mic input and amp output simultaneously?
- [ ] If not, do we need a custom device tree overlay?
- [ ] GAIN pin setting: what volume level do we need for industrial environment? (probably 15dB = Vin)
- [ ] SD pin: should we wire it to a GPIO so we can mute programmatically?

---

## 4. Buttons (6x Tactile Push Buttons)

### Wiring (for each button)

Each button connects between a **GPIO pin** and **GND**. The Pi's internal pull-up resistor is enabled in software.

```
Button Pin 1 ──── GPIO pin (e.g., GPIO 17)
Button Pin 2 ──── GND (any GND pin on Pi)
```

### Pin Assignment (PROPOSED - can change)

| Button | Function | GPIO (BCM) | Pi Pin # |
|--------|----------|-----------|----------|
| 1 | Session Start/Stop | GPIO 17 | Pin 11 |
| 2 | Photo / Video | GPIO 27 | Pin 13 |
| 3 | Voice Note (hold) | GPIO 22 | Pin 15 |
| 4 | AI Camera + QR | GPIO 5 | Pin 29 |
| 5 | AI Voice Q&A | GPIO 6 | Pin 31 |
| 6 | AI Agent Command | GPIO 13 | Pin 33 |

### GND pins you can use:
Pin 6, Pin 9, Pin 14, Pin 20, Pin 25, Pin 30, Pin 34, Pin 39

You can share GND pins - multiple buttons can connect to the same GND pin.

### Tips:
- No resistors needed (we use internal pull-ups in software)
- Use jumper wires or a breadboard for prototyping
- For the final build, solder connections or use a proto HAT

---

## 5. Complete GPIO Pin Map

Here's every pin we're using:

```
Raspberry Pi 4B GPIO Header (looking at Pi with USB ports at bottom)

                    3.3V [1]  [2]  5V          ← Amp Vin
            Mic 3.3V/Power [1]
                         [3]  [4]  5V
                         [5]  [6]  GND         ← Mic GND
                         [7]  [8]
                     GND [9]  [10]              ← Amp GND
   BTN1 (Session) GPIO17 [11] [12] GPIO18 BCLK ← Mic+Amp shared
   BTN2 (Photo)   GPIO27 [13] [14] GND
   BTN3 (Voice)   GPIO22 [15] [16]
                    3.3V [17] [18]
                         [19] [20] GND          ← Button GND
                         [21] [22]
                         [23] [24]
                     GND [25] [26]
                         [27] [28]
   BTN4 (AI Cam)   GPIO5 [29] [30]
   BTN5 (AI Voice)  GPIO6 [31] [32]
   BTN6 (Agent)   GPIO13 [33] [34]
          Mic LRCLK GPIO19 [35] [36]
                         [37] [38] GPIO20      ← Mic DOUT
                     GND [39] [40] GPIO21      ← Amp DIN
```

---

## 6. Assembly Order (Recommended)

Do it in this order so you can test each component as you add it:

### Step 1: Camera (easiest)
1. Connect ribbon cable to CSI port
2. Test: `libcamera-hello`

### Step 2: Amplifier + Speaker (I2S output)
1. Wire MAX98357A to Pi (5V, GND, BCLK, LRC, DIN)
2. Solder speaker wires to amp board
3. Edit `/boot/firmware/config.txt` - add overlay
4. Reboot and test: `speaker-test -t wav`

### Step 3: Microphone (I2S input)
1. Wire SPH0645LM4H to Pi (3.3V, GND, BCLK, LRCLK, DOUT)
2. Update config.txt if needed for input overlay
3. Reboot and test: `arecord` then `aplay`

### Step 4: Buttons
1. Wire 6 buttons between GPIO pins and GND
2. Test with a simple Python script:
```python
import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
for pin in [17, 27, 22, 5, 6, 13]:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

while True:
    for pin in [17, 27, 22, 5, 6, 13]:
        if GPIO.input(pin) == GPIO.LOW:
            print(f"Button on GPIO {pin} pressed!")
    time.sleep(0.1)
```

---

## 7. Important Notes

### I2S Bus Sharing
The microphone and amplifier SHARE the I2S clock lines (BCLK on GPIO 18, LRCLK on GPIO 19). This is normal for I2S - they use separate data lines (mic=GPIO 20, amp=GPIO 21). However, getting both to work simultaneously may require the right device tree overlay.

### Power
- Pi needs 5V 3A (USB-C) minimum
- Camera, mic, and amp all draw power from the Pi
- For portable use, a good power bank with USB-C PD is recommended
- **Do NOT use a cheap power bank** - undervoltage causes random crashes

### Impact on Software
Since we're using I2S (not USB audio), the `audio.py` module needs to use ALSA/sounddevice instead of PyAudio. This is a change from the original plan:
- **Recording:** Use `sounddevice` library or direct ALSA via `alsaaudio`
- **Playback:** Use `pygame` (works with ALSA) or `sounddevice`
- PyAudio may still work if ALSA is configured correctly with `~/.asoundrc`

### What to Buy Still
- [ ] Power bank (USB-C PD, 5V 3A minimum, 10000mAh+ recommended)
- [ ] Jumper wires (female-to-female for Pi GPIO)
- [ ] Breadboard (for prototyping)
- [ ] Micro SD card (32GB+ recommended, already have?)
