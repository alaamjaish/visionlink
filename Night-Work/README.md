# Night Work — VisionLink Launch Kit

**Date:** 2026-05-20 → 2026-05-21
**Live URL:** https://visionlink-wearable.netlify.app
**Purpose:** Everything generated overnight to support the VisionLink demo — the marketing website, the AI chatbot, the internal team guide, and the QR code for the demo poster.

---

## What's in this folder

```
Night-Work/
├── README.md                       # this file
├── internal-team-guide.html        # editable source of the 5-page team PDF
├── internal-team-guide.pdf         # rendered 5-page PDF (683 KB)
├── visionlink-qr.png               # 1000×1000 static QR → live site
├── visionlink-qr.svg               # vector QR, scales to any poster size
└── website/                        # Netlify-deployed marketing site
    ├── index.html                  # Turkish landing (default locale)
    ├── how-to-use.html             # TR — A-to-Z scenario walkthrough
    ├── the-six-buttons.html        # TR — deep dive on B1–B6
    ├── hardware.html               # TR — components, GPIO map, BOM
    ├── software-and-ai.html        # TR — stack, AI providers, tools
    ├── team.html                   # TR — roles + SDGs
    ├── en/                         # English mirror at /en/
    │   ├── index.html
    │   ├── how-to-use.html
    │   ├── the-six-buttons.html
    │   ├── hardware.html
    │   ├── software-and-ai.html
    │   └── team.html
    ├── assets/
    │   ├── styles.css              # shared dark-navy/sky-blue/gold theme
    │   ├── logo.svg                # VisionLink mark
    │   ├── nav.js                  # injects nav + footer + chatbot, lang switcher
    │   └── chatbot.js              # frontend logic for the chatbot widget
    ├── netlify/
    │   └── functions/
    │       └── chat.js             # serverless proxy → OpenRouter (Gemini 3.5 Flash)
    ├── netlify.toml                # redirects, headers, function config
    ├── package.json                # npm scripts wired to the Netlify CLI
    ├── deploy.ps1                  # one-shot PowerShell deploy helper
    ├── .env.example                # local env template (no real key)
    └── README.md                   # deployment instructions for the site
```

---

## What was done overnight — summary

### 1. The marketing website (multi-page, Netlify-hosted)

Six pages × two languages (Turkish default at root, English at `/en/`). Dark-navy + sky-blue + gold theme, modern typography (Inter / Space Grotesk / JetBrains Mono), responsive down to mobile.

- **Landing (`/` and `/en/`)** — centered hero ("Press a button. Talk to your factory."), problem framing, pitch with animated ring visual, six-button preview grid, supervisor side, soak-test numbers, team strip, CTA.
- **How to Use (`/how-to-use`)** — A-to-Z shift walkthrough. Nine moments from 8 AM to 5 PM, each with scenario, what the worker says, what happens behind the scenes, and the benefit on the floor. Designed for someone who has never heard of VisionLink to understand it in one page. *This is the primary CTA from the hero.*
- **The Six Buttons (`/the-six-buttons`)** — deep dive on B1–B6 with the full flow of each press: GPIO interrupt → debounce → handler → Supabase write → realtime dashboard update.
- **Hardware (`/hardware`)** — every component, GPIO pin map, wiring philosophy, enclosure iterations, full BOM in TRY (prototype + 1K-MOQ scale).
- **Software & AI (`/software-and-ai`)** — full stack table, three-process Pi architecture, three AI providers (Gemini Live / OpenAI Realtime / Gemini 3.5 Flash on the chatbot), the six AI tools, database schema, 11 ops-dashboard panels, measured latency numbers.
- **Team (`/team`)** — four roles (Alaa Abo Jeesh + Ali Salih Yıldırım on software; Alaa Ali + Fatma Defne Dolaz on hardware + testing), how the team worked, SDG mapping.

URLs are clean — `.html` extensions stripped, `index.html` redirects to root, `/index.html#anchor` URLs from old shares 301-redirect to the clean equivalent.

Old `/tr/*` URLs from before the Turkish-default swap 301-redirect to `/*` so any previously-shared link or printed QR keeps working.

### 2. The AI chatbot (Gemini 3.5 Flash via OpenRouter)

A floating chat bubble on every page that answers project questions. Architecture:

- **Frontend (`website/assets/chatbot.js`):** floating FAB → opens a 380px panel → POST to `/.netlify/functions/chat`. Maintains conversation history in memory per page load. Renders bot replies with a tiny Markdown subset (bold, inline code, line breaks). No auto-greeting — the chat opens empty until the visitor types or taps a suggestion chip.
- **Backend (`website/netlify/functions/chat.js`):** Netlify Function (Node 20 runtime, no dependencies, uses built-in `fetch`). Reads `OPENROUTER_API_KEY` from Netlify's encrypted env store (scoped to production / deploy-preview / branch-deploy contexts only, never local dev, never logs). POSTs to `https://openrouter.ai/api/v1/chat/completions` with `model: google/gemini-3.5-flash` by default — swap models any time via the `OPENROUTER_MODEL` env var.
- **System prompt:** ~22 sections, ~7000 words. Covers identity + audience-adapting rules, every button (gestures, GPIO pin, handler name, flow, table interactions, design rationale), the six AI tools (signatures + table impact), all three AI providers + model IDs, software architecture (three Pi processes, every library), the 11 ops-dashboard panels, every database table, the full SOS flow, measured performance, BOM + recurring cloud cost, demo storyline, standards & compliance, SDGs, open punch list, and worked tone examples for technical / non-technical / mixed audiences.
- **Language:** English and Turkish only. The bot detects the visitor's language and matches it; switches mid-conversation if the visitor switches.
- **Tone adaptation:** the bot reads the visitor's vocabulary and matches their level — non-technical gets analogies and the human consequence, technical gets file paths and identifiers, mixed gets the human answer with an offer to go deeper.
- **Privacy:** the bot is explicitly instructed never to mention any GitHub URL or claim the project is open source.

### 3. The 5-page internal team guide (PDF)

A self-contained reference for anyone on the team who needs to speak about the whole project without re-reading the code.

- Page 1: cover + executive summary + key KPIs.
- Page 2: the six buttons compact reference card + the SOS flow narrative.
- Page 3: hardware components, GPIO pin map, BOM at prototype + 1K-MOQ scales.
- Page 4: software architecture, AI providers, the six tools, dashboard panels.
- Page 5: demo storyline (4 landings), performance numbers, team roles, open questions to lock in before demo.

Rendered from `internal-team-guide.html` to PDF via headless Chrome. To re-render after any edit:

```powershell
& 'C:\Program Files\Google\Chrome\Application\chrome.exe' --headless=new --disable-gpu --print-to-pdf-no-header --print-to-pdf="internal-team-guide.pdf" "file:///<absolute-path-to>/internal-team-guide.html"
```

### 4. The QR code (for the demo poster)

Two formats, both pointing at `https://visionlink-wearable.netlify.app`:

- **`visionlink-qr.png`** — 1000×1000, high error-correction (ECC=H), ~1.4 KB.
- **`visionlink-qr.svg`** — vector, scales cleanly to any poster size, ~22 KB.

These are **static** QR codes. The destination URL is encoded directly in the pixels — no redirect service, no expiry, no third-party dependency. Will keep working indefinitely as long as the Netlify site itself stays at `visionlink-wearable.netlify.app` (don't rename the site after printing the poster).

---

## How to redeploy the site

From `website/`:

```powershell
.\deploy.ps1                 # production deploy
.\deploy.ps1 -Preview        # draft preview URL (no prod swap)
.\deploy.ps1 -SetKey         # rotate OPENROUTER_API_KEY securely
```

The script auto-installs the Netlify CLI if missing, prompts for login if needed, and runs `netlify deploy --prod --dir=.` against the linked site. Cross-platform alternative via npm:

```bash
npm run deploy               # production
npm run deploy:preview       # draft preview
npm run env:set-key <key>    # rotate the API key
npm run logs                 # tail chat function logs
```

## How to update the chatbot's knowledge

The full system prompt lives in `website/netlify/functions/chat.js` as `SYSTEM_PROMPT`. If a project fact changes — a model ID, a GPIO pin, a panel name, a soak-test number — edit it there and redeploy. No build step.

---

## Tech choices, briefly

- **No framework.** Plain HTML + CSS + vanilla JS for the site itself. Easy to host anywhere, fast to load, no build step.
- **Netlify Function for the chatbot.** Keeps the OpenRouter key off the client. Node 20 runtime, built-in `fetch`, no dependencies.
- **OpenRouter** instead of direct Gemini API so the model can be swapped (Anthropic Claude, OpenAI GPT, other Gemini variants) without code changes — just flip the `OPENROUTER_MODEL` env var.
- **Static QR code** — encoded URL is in the pixels, not behind a redirect service. Doesn't break when third-party services expire.

---

## What's not in this folder (and why)

- **`.env`** — contains the actual `OPENROUTER_API_KEY`. Gitignored everywhere. The production key lives in Netlify's encrypted env store; for local dev, copy `.env.example` to `.env` and fill in your own.
- **`.netlify/`** — runtime state from the Netlify CLI (site ID, auth token cache). Gitignored. Will regenerate on first `netlify dev` or `netlify deploy` after `netlify link`.
- **`node_modules/`** — there are no dependencies, so no node_modules exists; if you ever add one, gitignore it.
