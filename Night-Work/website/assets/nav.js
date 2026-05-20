// Shared nav + footer + chatbot injector — supports EN and TR.
// Each page calls: window.VL.mount({ active: 'page-id', lang: 'en' | 'tr' }).
(function () {
  const LINKS = [
    { id: 'home',     slug: 'index.html',           label: { en: 'Home',             tr: 'Ana Sayfa' } },
    { id: 'how',      slug: 'how-to-use.html',      label: { en: 'How to Use',       tr: 'Nasıl Kullanılır' } },
    { id: 'buttons',  slug: 'the-six-buttons.html', label: { en: 'The Six Buttons',  tr: 'Altı Buton' } },
    { id: 'hardware', slug: 'hardware.html',        label: { en: 'Hardware',         tr: 'Donanım' } },
    { id: 'software', slug: 'software-and-ai.html', label: { en: 'Software & AI',    tr: 'Yazılım & YZ' } },
    { id: 'team',     slug: 'team.html',            label: { en: 'Team',             tr: 'Ekip' } },
  ];

  const FOOTER_TEXT = {
    en: {
      tagline: 'VisionLink · A wearable industrial assistant on Raspberry Pi 4B',
      course:  'EEE492 · Gazi University · Spring 2026',
      rights:  '© 2026 VisionLink Team · All rights reserved',
    },
    tr: {
      tagline: 'VisionLink · Raspberry Pi 4B üzerinde giyilebilir endüstriyel asistan',
      course:  'EEE492 · Gazi Üniversitesi · Bahar 2026',
      rights:  '© 2026 VisionLink Ekibi · Tüm hakları saklıdır',
    },
  };

  const CHAT_LABELS = {
    en: { title: 'VisionLink Assistant', sub: 'Powered by Gemini 3.5 Flash', placeholder: 'Ask about the project…', send: 'Send', close: 'Close chat',
      suggestions: [
        { q: 'What is VisionLink?',                 label: 'What is VisionLink?' },
        { q: 'How does the SOS button work?',       label: 'How does SOS work?' },
        { q: 'Which AI models do you use?',         label: 'Which AI models?' },
        { q: 'What does each of the six buttons do?', label: 'The six buttons' },
      ] },
    tr: { title: 'VisionLink Asistanı', sub: 'Gemini 3.5 Flash ile çalışır', placeholder: 'Proje hakkında sor…', send: 'Gönder', close: 'Sohbeti kapat',
      suggestions: [
        { q: 'VisionLink nedir?',                          label: 'VisionLink nedir?' },
        { q: 'SOS butonu nasıl çalışır?',                  label: 'SOS nasıl çalışır?' },
        { q: 'Hangi YZ modellerini kullanıyorsunuz?',      label: 'Hangi YZ modelleri?' },
        { q: 'Altı butonun her biri ne yapıyor?',          label: 'Altı buton' },
      ] },
  };

  const LOGO_SVG = `
    <svg viewBox="0 0 64 64" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="navVlGrad" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#38bdf8"/>
          <stop offset="60%" stop-color="#0ea5e9"/>
          <stop offset="100%" stop-color="#f5c95b"/>
        </linearGradient>
      </defs>
      <circle cx="32" cy="32" r="27" stroke="url(#navVlGrad)" stroke-width="3" fill="none"/>
      <circle cx="32" cy="32" r="17" stroke="#38bdf8" stroke-width="1.5" fill="none" opacity="0.55"/>
      <circle cx="32" cy="32" r="7" fill="#38bdf8"/>
      <circle cx="32" cy="32" r="3" fill="#f5c95b"/>
    </svg>
  `;

  // Convert a page slug like 'the-six-buttons.html' to a clean URL ('the-six-buttons').
  // For the home page, return './' so the URL bar shows the bare domain (or /tr/).
  function toHref(slug) {
    if (slug === 'index.html') return './';
    return slug.replace(/\.html$/, '');
  }

  // Build a link to the OTHER language version of the page the visitor is on.
  // Derived from window.location.pathname so it works regardless of how the page was reached.
  // Default language is Turkish at the root; English lives under /en/.
  function buildSwitchHref(fromLang) {
    const path = (typeof window !== 'undefined' && window.location && window.location.pathname) || '/';
    const inEn = path === '/en' || path.startsWith('/en/');
    let bare = inEn ? path.replace(/^\/en\/?/, '') : path.replace(/^\//, '');
    bare = bare.replace(/\.html$/, '').replace(/\/$/, '');
    if (fromLang === 'en') {
      // currently inside /en/, switching back to TR (root)
      return '/' + bare;
    }
    return '/en/' + bare;
  }

  function renderNav(active, lang) {
    const switchHref = buildSwitchHref(lang);
    const switchLabel = lang === 'tr' ? 'EN' : 'TR';

    const linksHtml = LINKS.map(l =>
      `<a href="${toHref(l.slug)}" class="${l.id === active ? 'active' : ''}">${l.label[lang]}</a>`
    ).join('');

    return `
      <nav class="nav">
        <div class="nav-inner">
          <a href="./" class="nav-logo">
            ${LOGO_SVG}
            <span>Vision<span class="nl-link">Link</span></span>
          </a>
          <button class="nav-toggle" aria-label="Toggle menu" id="navToggle">☰</button>
          <div class="nav-links" id="navLinks">
            ${linksHtml}
            <a href="${switchHref}" class="lang-switch" aria-label="Switch language">${switchLabel}</a>
          </div>
        </div>
      </nav>
    `;
  }

  function renderFooter(lang) {
    const t = FOOTER_TEXT[lang] || FOOTER_TEXT.en;
    return `
      <footer>
        <div class="container foot-inner">
          <div>${t.tagline}</div>
          <div>${t.course}</div>
          <div>${t.rights}</div>
        </div>
      </footer>
    `;
  }

  function renderChatbot(lang) {
    const t = CHAT_LABELS[lang] || CHAT_LABELS.en;
    const sugs = t.suggestions.map(s =>
      `<button class="chat-suggestion" data-q="${s.q.replace(/"/g, '&quot;')}">${s.label}</button>`
    ).join('');

    return `
      <button class="chat-fab" id="chatFab" aria-label="${t.title}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
        </svg>
      </button>
      <div class="chat-panel" id="chatPanel" role="dialog" aria-label="${t.title}">
        <div class="chat-head">
          <span class="dot" aria-hidden="true"></span>
          <div>
            <div class="title">${t.title}</div>
            <div class="sub">${t.sub}</div>
          </div>
          <button class="chat-close" id="chatClose" aria-label="${t.close}">×</button>
        </div>
        <div class="chat-body" id="chatBody"></div>
        <div class="chat-suggestions" id="chatSuggestions">${sugs}</div>
        <form class="chat-input-row" id="chatForm" autocomplete="off">
          <input id="chatInput" type="text" placeholder="${t.placeholder}" maxlength="500" required />
          <button type="submit" id="chatSend">${t.send}</button>
        </form>
      </div>
    `;
  }

  function mount(opts = {}) {
    const active = opts.active || 'home';
    // Default language is Turkish; English is opt-in via lang:'en'.
    const lang = opts.lang === 'en' ? 'en' : 'tr';

    window.VL_LANG = lang;
    // Absolute root path — works the same from any depth
    window.VL_CHAT_ENDPOINT = '/.netlify/functions/chat';

    const navHost = document.createElement('div');
    navHost.innerHTML = renderNav(active, lang);
    document.body.insertBefore(navHost.firstElementChild, document.body.firstChild);

    const footHost = document.createElement('div');
    footHost.innerHTML = renderFooter(lang);
    document.body.appendChild(footHost.firstElementChild);

    const chatHost = document.createElement('div');
    chatHost.innerHTML = renderChatbot(lang);
    while (chatHost.firstElementChild) document.body.appendChild(chatHost.firstElementChild);

    const navToggle = document.getElementById('navToggle');
    const navLinks = document.getElementById('navLinks');
    if (navToggle && navLinks) {
      navToggle.addEventListener('click', () => navLinks.classList.toggle('open'));
    }

    if (window.VLChat) window.VLChat.init();
  }

  window.VL = { mount };
})();
