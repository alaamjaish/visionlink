# VisionLink — one-shot Netlify deploy.
#
# Usage (from the website/ folder):
#   .\deploy.ps1                # production deploy
#   .\deploy.ps1 -Preview       # draft preview deploy (no prod URL)
#   .\deploy.ps1 -SetKey        # prompt for OPENROUTER_API_KEY and set it in Netlify
#
# Requires Netlify CLI (auto-installs if missing) and a one-time `netlify login`.

param(
    [switch]$Preview,
    [switch]$SetKey
)

$ErrorActionPreference = 'Stop'

# 1. Make sure Netlify CLI is on PATH
if (-not (Get-Command netlify -ErrorAction SilentlyContinue)) {
    Write-Host '[deploy] Netlify CLI not found. Installing globally with npm...' -ForegroundColor Yellow
    npm install -g netlify-cli
}

# 2. Make sure we're logged in (no-op if already)
$status = netlify status 2>&1 | Out-String
if ($status -match 'Not logged in' -or $status -match 'You are not logged in') {
    Write-Host '[deploy] Not logged in. Running `netlify login`...' -ForegroundColor Yellow
    netlify login
}

# 3. Make sure the site folder is linked
if (-not (Test-Path '.netlify\state.json')) {
    Write-Host '[deploy] This folder is not linked to a Netlify site yet.' -ForegroundColor Yellow
    Write-Host '          Running `netlify init` — choose "Create & configure a new site".' -ForegroundColor Yellow
    Write-Host '          Build command: (leave blank)  Publish directory: .' -ForegroundColor DarkGray
    netlify init
}

# 4. Optionally set/refresh OPENROUTER_API_KEY
if ($SetKey) {
    $secure = Read-Host 'Paste your OpenRouter API key (sk-or-v1-..., input hidden)' -AsSecureString
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $plain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

    Write-Host '[deploy] Setting OPENROUTER_API_KEY in Netlify (all contexts)...' -ForegroundColor Cyan
    netlify env:set OPENROUTER_API_KEY $plain --secret
    Write-Host '[deploy] Done.' -ForegroundColor Green
}

# 5. Deploy
if ($Preview) {
    Write-Host '[deploy] Pushing a draft preview...' -ForegroundColor Cyan
    netlify deploy --dir=.
} else {
    Write-Host '[deploy] Pushing to PRODUCTION...' -ForegroundColor Cyan
    netlify deploy --prod --dir=. --message="VisionLink site update $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
}

Write-Host '[deploy] Finished.' -ForegroundColor Green
