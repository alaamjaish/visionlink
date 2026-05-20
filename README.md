<a id="readme-top"></a>

<div align="center">

<h1>VisionLink</h1>

<p><strong>A wearable industrial assistant for factory workers.</strong><br/>
Six buttons. One Raspberry Pi. Real-time AI vision and voice. A live supervisor dashboard. Zero friction.</p>

<p>
  <img src="https://img.shields.io/badge/Raspberry%20Pi-4B-A22846?style=for-the-badge&logo=raspberrypi&logoColor=white" alt="Raspberry Pi 4B">
  <img src="https://img.shields.io/badge/Hands--free-100%25-2ea44f?style=for-the-badge" alt="Hands-free">
  <img src="https://img.shields.io/badge/Latency-~200ms-blue?style=for-the-badge" alt="Latency">
  <img src="https://img.shields.io/badge/Parts%20cost-%E2%82%AC120-orange?style=for-the-badge" alt="Cost">
  <img src="https://img.shields.io/badge/Vision-Gemini%20%2B%20OpenAI-8E75B2?style=for-the-badge" alt="AI">
</p>

</div>

---

> **Press a button. Talk to an AI that sees what you see. Save a life in under a second.**

VisionLink turns any worker into a connected one — without taking their hands off the job. No phone to unlock. No app to open. No screen to read. Just six tactile buttons within reach, mapped to the moments that matter on a factory floor: ask the AI, capture the evidence, document the shift, scream for help.

---

## Table of Contents

1. [Meet VisionLink](#meet-visionlink)
2. [The Problem It Solves](#the-problem-it-solves)
3. [Six Buttons. One Worker. Zero Friction.](#six-buttons-one-worker-zero-friction)
4. [The SOS Promise](#the-sos-promise)
5. [It Sees What You See](#it-sees-what-you-see)
6. [It Remembers Every Shift](#it-remembers-every-shift)
7. [The Brain Behind the Button](#the-brain-behind-the-button)
8. [The Tools the AI Wields](#the-tools-the-ai-wields)
9. [The Supervisor's Window](#the-supervisors-window)
10. [How the System Connects](#how-the-system-connects)
11. [Engineered on a Raspberry Pi](#engineered-on-a-raspberry-pi)
12. [Specs at a Glance](#specs-at-a-glance)

---

## Meet VisionLink

VisionLink is a **wearable industrial assistant** — built like a smart-glasses module or a helmet attachment — that puts the power of multimodal AI directly onto a factory worker's body. It sees through a Pi Camera 3, hears through a digital I²S microphone, speaks through an amplified speaker, and connects everything to a cloud database that a supervisor watches in real time from anywhere.

The worker never has to stop working. Their fingers stay on the wrench, the welder, the pneumatic gun. Whenever they want to talk to the AI, raise an alarm, snap a photo, or dictate a note, they reach up and tap one of six tactile buttons. The hardware does the rest.

This is not a prototype concept. This is a **working build** with real GPIO interrupts, real cloud streaming, real tool-calling AI, and a real supervisor UI updating live over WebSocket. Built from a Raspberry Pi 4B and off-the-shelf I²S audio components. Total parts bill: **under €120**.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## The Problem It Solves

Factory floors are loud. They are dangerous. They are hands-busy.

A worker wrestling a pneumatic torque wrench cannot stop to type into a tablet, scroll a manual, or fumble for a radio. Yet the same worker is the single best sensor in the plant — they see the cracked weld, smell the burning bearing, hear the leak before any SCADA system reports a deviation. The knowledge is *in their head*, but there has historically been no fast, hands-free way to get it out.

What's been tried before:
- **Radios** — broadcast to everyone, no filtering, no audit trail.
- **Tablets / shop terminals** — require stopping work, walking somewhere, and typing.
- **Phones** — banned in most safety-critical zones and unusable with gloves anyway.
- **Voice-only assistants** — can't see what the worker is pointing at.

**VisionLink fills the gap.** Hands stay on the tool. Eyes stay on the work. One button press streams audio (and optionally a fresh camera frame) to a multimodal AI that can answer the question, log the incident, request the spare part, or escalate to safety — and every action is auditable in a database the supervisor sees live.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Six Buttons. One Worker. Zero Friction.

The six buttons split into two groups: **AI Assistant** (talk to the AI, raise emergencies) and **Documentation** (record the shift). Each button is a single tactile switch on a breadboard, wired directly to a GPIO pin. Single press, double press — that's the entire interaction vocabulary.

### 1 · Agent — Talk to the AI

The worker's everyday assistant. One press opens a streaming bidirectional voice session with a cloud AI. The AI hears them. They hear the AI speak back through the amplified speaker. The AI has access to the factory's parts catalog, the worker's task list, the procurement queue, and email templates — and it can act on all of them in real time.

*"What torque does an M12 hex bolt take on a Bosch GBH 11 DE?"*
*"I just finished the bearing swap on Press 3."*
*"Send the morning safety report to the line supervisor."*

Single press starts. Double press ends.

### 2 · Agent + Vision — Show the AI What You're Looking At

Same as Agent, but every single press also captures a fresh frame from the Pi Camera and sends it to the AI. Now the AI can identify the component the worker is pointing at, read a serial number off a label, recognize a fluid leak, or compare two parts.

Three vision modes are available — single snapshot per press, continuous 1-fps video stream (Gemini only), or auto-snap every 4 seconds. The supervisor picks the mode from the dashboard.

### 3 · SOS — When Seconds Save Lives

The emergency button. A single press is treated as a pocket-dial — it shows a warning toast and does nothing destructive. A **double press within 500 ms** triggers the full panic flow. *See [The SOS Promise](#the-sos-promise) below.*

### 4 · Documentation Session — Bracket the Shift

Press once at the start of a job or shift to **open a session** in the database. Every photo, video, and voice note captured from that moment forward is automatically attached to that session. Press the button again to close it. An 800 ms cooldown absorbs hardware bounce — no accidental double-toggles.

### 5 · Voice — Dictate a Hands-Free Note

Press once to start recording. Speak. Press once again to stop, upload, and attach the voice note to the current session. The audio is recorded directly off the I²S microphone — no phone, no app, no transcription delay.

If no documentation session is open, the voice note is parked in an `_orphan/` folder so nothing is ever lost.

### 6 · Visual — Photo or Video, One Button

Single press = **JPEG photo** at 1024 × 576, captured through the Pi Camera 3 and uploaded to cloud storage. Double press = **5-second MP4 video clip**. Both go straight into the current session — or the orphan bucket if no session is open.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## The SOS Promise

The double-press is unmistakable. Pocket-dial protection means a single tap is harmless — it shows a brief warning and resets. Two firm presses within half a second commits the worker to emergency mode.

**The instant the double press fires, in parallel:**

1. **A row is inserted into `sos_events`** — the supervisor's SOS panel turns red within ~200 ms.
2. **Any open documentation session is auto-closed** — the worker should not be doing paperwork during an emergency.
3. **The safety officer is emailed** — via Gmail SMTP, with the worker's identity, location (if available), and a direct link to the supervisor panel.
4. **An OpenAI Realtime session opens** — using a hand-tuned "calm emergency operator" persona that asks short questions, describes the situation back, and keeps the worker grounded until help arrives.
5. **Live camera frames stream out every 10 seconds** — uploaded to cloud storage and displayed to the supervisor in real time. The supervisor watches what the worker sees, hears the AI conversation transcript, and stays in the loop.

The supervisor can flip a `resolved` flag at any moment to remotely stand the wearable down. The wearable polls every 2 seconds and tears the session down within ~2 seconds of the flip. A hard ten-minute timeout backstops everything regardless.

**This is the feature that, alone, justifies the build.**

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## It Sees What You See

The Pi Camera Module 3 sits on the wearable, pointed forward, and feeds frames straight into the AI session whenever the worker hits the **Agent + Vision** button or triggers SOS.

Three vision modes, switchable from the supervisor dashboard:

| Mode | Behavior | Best For |
|------|----------|----------|
| `snap_on_press` *(default)* | One fresh frame per button press | Lookups, identifications, "what is this?" |
| `gemini_video` | Continuous 1-fps video stream (Gemini Live only) | Real-time guided procedures |
| `auto_snap_4s` | Auto-snap every 4 seconds during a session | Inspections, walkthroughs |

Photos captured manually via the **Visual** button are JPEG at 1024 × 576 — sharp enough to read part labels and small enough to upload over a hotspot connection without choking. Videos are 5-second MP4 clips through `rpicam-vid` and `libav`.

Every frame, photo, and video is uploaded directly to Supabase Storage. A row in the database carries the public URL — the supervisor's browser pulls it inline within a couple hundred milliseconds.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## It Remembers Every Shift

A "session" is the container that bundles all the evidence from a period of work — every photo, every video clip, every voice note, every AI conversation transcript. The worker opens one with a single button press, captures whatever they need throughout their shift, and closes it with another press.

Sessions show up live on the supervisor's **Documentation** page:

- A **Sessions panel** lists every shift with its open/closed status, duration, and asset counts.
- A **Captures panel** shows the photos, videos, and voice notes in a tabbed grid — All / Photos / Videos / Voice / Orphans — with click-to-zoom and inline playback.
- A **stats strip** at the top summarises captures-per-day, total session time, and unresolved incidents.

Nothing gets lost. If a worker captures something without opening a session first, the asset is parked in an orphan folder and surfaced for the supervisor to triage. Everything is timestamped, attributed, and auditable.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## The Brain Behind the Button

VisionLink does not lock itself to a single AI vendor. It speaks to **three different cloud providers**, each chosen for a specific strength.

| Provider | Model | Used For | Why |
|----------|-------|----------|-----|
| **Google Gemini Live** | `gemini-3.1-flash-live-preview` | Default Agent + Vision | Native multimodal — audio, image, and text in one stream. Fastest first-token latency. Lowest cost per minute. Excellent at general conversation and tool calling. |
| **OpenAI Realtime** | `gpt-realtime-2` | Alternative Agent · **always SOS** | Strongest instruction-following for tightly scripted personas — the "calm emergency operator" voice is unmatched. Voice "Cedar", reasoning_effort "medium", playback speed 1.2× by default. |
| **Anthropic Claude** | Claude Sonnet 4.6 | Email drafting *(planned)* | Best long-form writing quality. Polishes emergency or shift reports into professional emails before Gmail sends them. |

The supervisor flips between Gemini and OpenAI for normal Agent sessions from the **Wearable Settings** panel — no restart, no redeploy. The setting takes effect on the next button press. SOS always uses OpenAI regardless.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## The Tools the AI Wields

Both Gemini and OpenAI sessions expose the same **six tools**. Tools are how the AI takes real action — not just talk. Every tool call is a real database write or a real email send, audited in Postgres.

| # | Tool | What It Does |
|---|------|--------------|
| 1 | `lookup_component(query)` | Searches the parts catalog by part code (exact) then by name (fuzzy). Returns up to 3 rows with torque spec, maintenance interval, and safety notes. |
| 2 | `log_incident(description, category?, severity?, location?)` | Logs an incident the moment a worker reports something wrong. Goes straight into the `incidents` table for the supervisor. |
| 3 | `mark_task_complete(task_query)` | Fuzzy-matches against the worker's open tasks and closes the matching one. No more "I'll mark it done later." |
| 4 | `get_my_assignments(include_complete?)` | Reads back the worker's pending or complete tasks out loud. |
| 5 | `request_part(part_query, quantity?, urgency?, reason?)` | Files a procurement request without a single keystroke. |
| 6 | `send_report(report_name, recipient_role?, ..., custom_message?)` | Pulls a pre-defined HTML email template, looks up the right recipient by role, injects live data, and sends it via Gmail SMTP. Every send is logged. |

Three guardrails built into the system prompt prevent the AI from going rogue:

1. **Never lie about completing actions.** *"I logged it"* is only allowed if the tool actually fired.
2. **Verb triggers.** Words like *log*, *mark*, *send*, *request* fire the matching tool immediately — no needless follow-up questions.
3. **No info-collection trap.** The AI never asks more than one clarifying question. It commits to action with reasonable defaults.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## The Supervisor's Window

Two web dashboards run on the wearable itself, served from the Pi and reachable on the local network at `visionlink.local`.

### Voice Command Center
A simulator built for the worker side — six on-screen buttons that match the physical ones, the live AI transcript, recent captures, and debug overrides. Useful during testing and demos when the worker isn't wearing the device.

### Ops Dashboard — The Supervisor's HQ
Built with Next.js 16, React 19, and Tailwind 4. Two pages, switchable from the top nav.

**Agent page (`/`)** — nine live panels, each subscribed to its own Postgres table over realtime WebSocket:

| Panel | What It Shows |
|-------|---------------|
| **Incidents** | Every problem the worker has reported, with severity and timestamp |
| **Tasks** | The worker's task board — open and complete |
| **Parts** | Pending procurement requests from the AI's `request_part` tool |
| **Components** | The factory's parts catalog the AI can search |
| **Managers** | Who gets emailed for which kind of report |
| **Report Templates** | The pre-defined email bodies the AI can send |
| **Sent Reports** | An audit log of every email that has gone out |
| **SOS** | Live emergency events with frame-by-frame camera feed |
| **Wearable Settings** | Pick the AI provider, change vision mode, tune SOS thresholds |

**Documentation page (`/documentation`)** — a stats strip plus a Sessions panel (list of shifts with asset counts) plus a Captures panel (tabbed grid: All / Photos / Videos / Voice / Orphans, click-to-zoom, inline playback).

Every panel updates in **~200 milliseconds** when a new row hits the database. No refresh. No polling. No spinners.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## How the System Connects

```
┌─────────────────────────────────────────────────────────────────┐
│  CLOUD                                                          │
│  Supabase (Postgres + Storage + Realtime)                       │
│  Google Gemini Live · OpenAI Realtime · Gmail SMTP              │
└─────────────────────────────────────────────────────────────────┘
            ▲  HTTPS · WebSocket · Realtime channel
            │
┌─────────────────────────────────────────────────────────────────┐
│  RASPBERRY PI 4B  (worn by the worker)                          │
│                                                                 │
│  ┌────────────────────────┐    ┌──────────────────────────────┐ │
│  │  GPIO Bridge           │───►│  FastAPI Dashboard           │ │
│  │  6 falling-edge        │HTTP│  - Voice command center      │ │
│  │  interrupts            │    │  - AudioBridge (mic + amp)   │ │
│  └────────────────────────┘    │  - Camera lock manager       │ │
│                                │  - AI session orchestrator   │ │
│                                └──────────────────────────────┘ │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Next.js 16 Ops Dashboard                                  │ │
│  │  - Agent page (9 live panels)                              │ │
│  │  - Documentation page (sessions + captures)                │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
            ▲   GPIO  ·  CSI ribbon  ·  I²S
            │
┌─────────────────────────────────────────────────────────────────┐
│  PHYSICAL WEARABLE                                              │
│  6 buttons · Pi Camera 3 · I²S mic · I²S amp + speaker          │
└─────────────────────────────────────────────────────────────────┘
```

The Raspberry Pi runs the entire local stack — button handling, audio capture, camera control, AI session orchestration, and both dashboards. Cloud-side, it talks to Supabase for the database, storage bucket, and realtime push channel, and to Google / OpenAI / (planned) Anthropic for AI inference. Gmail SMTP delivers emails. That's the whole network surface.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Engineered on a Raspberry Pi

The whole wearable is built from consumer-grade Raspberry Pi hardware and off-the-shelf I²S audio components. **Total parts cost: under €120.**

| Component | Model | Role | Connection |
|-----------|-------|------|-----------|
| Computer | Raspberry Pi 4B (8 GB RAM) | The brain — runs every line of the local stack | USB-C 5 V / 3 A |
| Camera | Pi Camera Module 3 | Photos, video, live AI vision frames | CSI ribbon cable |
| Microphone | SPH0645LM4H (GY-SPH0645 board) | Digital I²S mic — for voice and AI input | GPIO 18 BCLK · 19 LRCLK · 20 DOUT |
| Amplifier | MAX98357A | Drives the speaker from a digital I²S signal | GPIO 18 BCLK · 19 LRCLK · 21 DIN |
| Speaker | 8 Ω 1 W oval (Adafruit-style) | AI voice and UI beeps | Screw terminals on the amp |
| Buttons | 6 × tactile push-button switches | Worker input | GPIO 5 · 6 · 13 · 22 · 23 · 25 + shared GND |
| Power | USB-C PSU or USB power bank | Standalone wearable power | USB-C |

The microphone and amplifier share I²S clock lines (BCLK on GPIO 18, LRCLK on GPIO 19) and have separate data lines (mic DOUT on GPIO 20, amp DIN on GPIO 21). All audio runs on four wires plus power and ground.

Each button has two wires: signal goes to its GPIO pin, the diagonally-opposite leg goes to ground. Pressing the button shorts the pin to ground; the Pi's internal pull-up resistor detects the falling edge. A 200 ms hardware debounce filters mechanical bounce. Per-button software cooldowns handle the rest.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Specs at a Glance

| Capability | Value |
|------------|-------|
| Physical buttons | 6 tactile switches |
| Press vocabulary | Single press · Double press (500 ms window) |
| Camera resolution (photo) | 1024 × 576 JPEG |
| Camera resolution (video) | 5-second MP4 (libav-mp4) |
| Microphone | 16 kHz mono PCM over I²S |
| Audio output | I²S amp + 8 Ω 1 W speaker |
| Default AI (voice + vision) | Google Gemini Live |
| Emergency AI | OpenAI Realtime (`gpt-realtime-2`) |
| AI tool count | 6 (catalog, incidents, tasks, parts, reports, assignments) |
| Database | Managed Postgres (Supabase) |
| Realtime push latency | ~200 ms end-to-end |
| SOS escalation | < 1 second from double-press to email + AI session |
| SOS auto-frame interval | 10 seconds |
| SOS hard timeout | 10 minutes |
| Network | Wi-Fi via `visionlink.local` mDNS |
| Power | USB-C 5 V / 3 A or USB power bank |
| Total parts cost | **Under €120** |

<p align="right">(<a href="#readme-top">back to top</a>)</p>
