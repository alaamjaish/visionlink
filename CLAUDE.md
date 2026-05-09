# CLAUDE.md — VisionLink Quick Context

This is the entry point for any AI agent landing on this repo. Read
this once. For everything else, follow the pointers below.

---

## What VisionLink is (one paragraph)

A wearable industrial assistant for factory workers, built on a
**Raspberry Pi 4B** with a Pi Camera 3, an I²S microphone, an I²S
amplifier + speaker, and six tactile buttons on a breadboard. The
worker presses buttons to talk to a cloud AI, raise emergencies, or
record their shift. Everything streams in real time to a Next.js
supervisor dashboard via Supabase.

## Single source of truth

**📘 [`Documentation/MASTER.md`](Documentation/MASTER.md)** is the
authoritative technical reference. If anything in this file disagrees
with the master, the master wins.

A polished PDF version is at `Documentation/MASTER.pdf` (cover page,
page numbers, A4 — for handing to the professor).

## The six buttons (canonical naming as of 2026-05-09)

| # | Button | Function | GPIO | Pin |
|---|--------|----------|------|-----|
| 1 | **Agent** | Audio-only AI | 5 | 29 |
| 2 | **Agent + Vision** | AI + camera | 6 | 31 |
| 3 | **SOS** | Panic mode (double-click) | 13 | 33 |
| 4 | **Documentation Session** | Open / close session | 23 | 16 |
| 5 | **Voice** | Press-to-toggle voice note | 22 | 15 |
| 6 | **Visual** | Single = photo, double = video | 25 | 22 |

> The Python code internally uses older constant names (`BTN_SESSION`,
> `BTN_AI_CAMERA`, etc.) and `b1_…` through `b6_…` handler names. Do
> not refactor those — the mapping is consistent and the code works.

## What runs where

- `dashboard/server.py` — FastAPI on `:8000`, voice command center +
  AudioBridge + camera lock manager
- `ops/` — Next.js 16 supervisor dashboard on `:3000`, two pages
  (Agent at `/`, Documentation at `/documentation`)
- `scripts/gpio_bridge.py` — physical-button → HTTP sidecar, log at
  `/tmp/vl_bridge.log`
- Cloud: **Supabase** (PostgreSQL + storage + realtime) + **Gemini**
  + **OpenAI Realtime** + **Gmail SMTP**

## Where to find current state

- `Documentation/MASTER.md` — comprehensive reference (this is what
  you want most of the time)
- `Documentation/sessions/` — per-session work logs, newest is current
- `Documentation/NEXT_SESSION_PLAN.md` — what we tackle next

## Communication notes

The lead developer is a small team of students — smart but not deeply
technical. When explaining things:

- Use simple language, no jargon dump
- Step-by-step checklists over paragraphs
- For hardware instructions: pin numbers, wire colors, exact steps
- When something can break the hardware, **warn loudly**

## Don't touch

- `~/.asoundrc` — disappears intermittently, dashboard self-heals.
  Don't try to "fix" it preemptively.
- Internal Python button numbering (`BTN_SESSION` etc.) — leave alone.
- `dashboard/audio_worker.py` and `dashboard/audio_bridge.py` — load-
  bearing, don't refactor without a specific reason.

## Project basics

- **Project root**: `~/Desktop/visionlink/`
- **Branch**: `openai-sdk`
- **GitHub**: `https://github.com/alaamjaish/visionlink`
- **Team**: Alaa, Ali Salih, F-Alaa, Defne
- **Deadline**: mid-May 2026

---

*For everything else, open [`Documentation/MASTER.md`](Documentation/MASTER.md).*
