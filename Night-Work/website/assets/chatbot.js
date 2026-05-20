// VisionLink chatbot widget — talks to /.netlify/functions/chat.
// Maintains conversation history in memory (per page load).
(function () {
  // If the page sets window.VL_CHAT_ENDPOINT, use it. Otherwise default to the Netlify function.
  const ENDPOINT = (typeof window !== 'undefined' && window.VL_CHAT_ENDPOINT) || '/.netlify/functions/chat';

  let history = []; // [{ role: 'user'|'assistant', content: string }]
  let sending = false;

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  // Tiny markdown-lite renderer: bold, inline code, line breaks, bullet lists.
  function renderMarkdown(s) {
    let html = escapeHtml(s);
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    // Numbered or bulleted line at start of line → keep as is (already has prefix)
    html = html.replace(/\n/g, '<br>');
    return html;
  }

  function appendMsg(role, text) {
    const body = document.getElementById('chatBody');
    if (!body) return null;
    const div = document.createElement('div');
    div.className = `chat-msg ${role}`;
    div.innerHTML = renderMarkdown(text);
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
    return div;
  }

  function showThinking() {
    const body = document.getElementById('chatBody');
    if (!body) return null;
    const div = document.createElement('div');
    div.className = 'chat-msg bot thinking';
    div.id = 'chatThinking';
    div.textContent = 'Thinking…';
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
    return div;
  }

  function clearThinking() {
    const t = document.getElementById('chatThinking');
    if (t) t.remove();
  }

  function hideSuggestions() {
    const s = document.getElementById('chatSuggestions');
    if (s) s.style.display = 'none';
  }

  async function send(text) {
    if (!text || sending) return;
    sending = true;
    const input = document.getElementById('chatInput');
    const sendBtn = document.getElementById('chatSend');
    if (input) input.value = '';
    if (sendBtn) sendBtn.disabled = true;

    hideSuggestions();
    appendMsg('user', text);
    history.push({ role: 'user', content: text });
    showThinking();

    try {
      const res = await fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: history }),
      });
      clearThinking();

      if (!res.ok) {
        const errText = await safeText(res);
        appendMsg(
          'bot',
          `Sorry — I couldn't reach the model just now. (${res.status})\n\nIf you're running this locally without the Netlify function, that's expected — the chatbot needs the deployed environment.`
        );
        console.warn('Chat error', res.status, errText);
        return;
      }
      const data = await res.json();
      const reply = (data && data.reply) || "I didn't get a response. Please try again.";
      appendMsg('bot', reply);
      history.push({ role: 'assistant', content: reply });
    } catch (err) {
      clearThinking();
      appendMsg(
        'bot',
        `Network error reaching the assistant. Please try again in a moment.`
      );
      console.error(err);
    } finally {
      sending = false;
      if (sendBtn) sendBtn.disabled = false;
      if (input) input.focus();
    }
  }

  async function safeText(res) {
    try { return await res.text(); } catch { return ''; }
  }

  function init() {
    const fab = document.getElementById('chatFab');
    const panel = document.getElementById('chatPanel');
    const close = document.getElementById('chatClose');
    const form = document.getElementById('chatForm');
    const input = document.getElementById('chatInput');

    if (!fab || !panel) return;

    // No auto-greeting — the chat opens empty until the visitor types or
    // taps a suggestion. The suggestion chips below the chat body act as
    // an entry point.

    fab.addEventListener('click', () => {
      panel.classList.toggle('open');
      if (panel.classList.contains('open') && input) setTimeout(() => input.focus(), 80);
    });

    if (close) close.addEventListener('click', () => panel.classList.remove('open'));

    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const v = (input && input.value || '').trim();
        if (v) send(v);
      });
    }

    document.querySelectorAll('.chat-suggestion').forEach((btn) => {
      btn.addEventListener('click', () => {
        const q = btn.getAttribute('data-q');
        if (q) send(q);
      });
    });
  }

  window.VLChat = { init, send };
})();
