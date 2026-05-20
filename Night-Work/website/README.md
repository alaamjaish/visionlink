# VisionLink — Marketing Site + Chatbot

The public-facing project site for VisionLink. Plain static HTML/CSS/JS plus a single Netlify Function that proxies the chatbot to Google Gemini 3.5 Flash.

## What's inside

```
website/
├── index.html                       # Landing
├── the-six-buttons.html             # Deep dive on B1–B6
├── hardware.html                    # Components, GPIO map, BOM
├── software-and-ai.html             # Stack, AI providers, tools, latency
├── team.html                        # Roles + SDGs
├── assets/
│   ├── styles.css                   # Shared dark-navy theme
│   ├── logo.svg                     # VisionLink mark
│   ├── nav.js                       # Injects nav + footer + chatbot widget on every page
│   └── chatbot.js                   # Frontend logic for the chatbot widget
├── netlify/
│   └── functions/
│       └── chat.js                  # Server-side Gemini 3.5 Flash proxy (keeps API key safe)
├── netlify.toml                     # Netlify build + redirects config
├── package.json                     # npm scripts wired to Netlify CLI
├── deploy.ps1                       # One-shot PowerShell deploy helper
├── .env.example                     # Local env template
└── README.md                        # this file
```

---

## Fast path — deploy in one command

From this folder:

```powershell
.\deploy.ps1                 # production deploy
.\deploy.ps1 -Preview        # draft preview URL (no prod swap)
.\deploy.ps1 -SetKey         # securely set/rotate GEMINI_API_KEY
```

The script will:
1. Install `netlify-cli` globally if it's missing
2. Run `netlify login` if you're not authenticated
3. Run `netlify init` (interactive) if this folder isn't linked to a site yet — pick **"Create & configure a new site"**, leave build command empty, set publish dir to `.`
4. Push the deploy

First time only: after `netlify init` finishes, set the API key:

```powershell
.\deploy.ps1 -SetKey
```

Paste your OpenRouter API key (https://openrouter.ai/keys, format `sk-or-v1-...`) when prompted. It is stored in Netlify as a secret env var named `OPENROUTER_API_KEY`. The chatbot proxies through OpenRouter so we can swap models without re-coding — Gemini 3.5 Flash is the default; flip to Claude / GPT / etc. via the `OPENROUTER_MODEL` env var.

---

## Same thing via npm scripts (cross-platform)

If you prefer npm:

```bash
npm run dev               # netlify dev — local server with the chat function
npm run deploy:preview    # draft preview URL
npm run deploy            # production
npm run env:set-key <key> # set GEMINI_API_KEY
npm run env:list          # inspect env vars
npm run open              # open the live site in your browser
npm run logs              # tail the chat function logs (debugging)
```

---

## Local dev with the chatbot

The static pages work standalone — open `index.html` directly in a browser to see the design. The chatbot will gracefully say "I couldn't reach the model" because there's no Netlify function running.

To test the chatbot end-to-end locally:

```powershell
# One-time setup
npm install -g netlify-cli
netlify login

# Run dev server (port 8888 by default)
netlify dev
```

Create a `.env` file (copy from `.env.example`) with:

```
OPENROUTER_API_KEY=sk-or-v1-your-openrouter-key
```

That key is loaded by `netlify dev` and made available to the chat function. **Do not commit `.env`** — it's gitignored at the repo root.

---

## Generating the QR code for the demo poster

Once deployed, take the Netlify URL (e.g. `https://visionlink.netlify.app`) and generate a QR code from any service — qr-code-generator.com works, or run `npx qrcode "https://your-url"` from a terminal. The QR points to the live site; the chatbot is available on every page via the bubble at the bottom-right.

---

## Notes

- **The source code is private.** No GitHub links anywhere on the public site. The chatbot's system prompt explicitly refuses to share a repo URL.
- The chatbot's full system prompt lives in `netlify/functions/chat.js`. If a project fact changes, edit it there and redeploy.
- **Routing via OpenRouter.** The chatbot defaults to `google/gemini-3.5-flash` (released 2026-05-19 at Google I/O 2026; $1.50/$9 per 1M tokens, 1M-token context, 4× faster than Gemini 3.1 Pro on agent/coding benchmarks). Swap models any time by changing the `OPENROUTER_MODEL` env var — e.g. `anthropic/claude-sonnet-4.6`, `openai/gpt-4.1`, `google/gemini-2.5-flash` — without touching code.
- **No build step.** Plain HTML + CSS + vanilla JS. Hosted as a static site with one Netlify Function. Fastest possible cold start.
