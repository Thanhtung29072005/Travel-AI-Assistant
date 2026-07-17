/**
 * Hana Travel AI – Frontend Chat Logic
 * Pure vanilla JS, no dependencies.
 */

const API_BASE = '/api';

// ── State ─────────────────────────────────────────────────
let sessionId = null;
let conversationHistory = [];
let isLoading = false;

// ── DOM refs ──────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

const msgInput       = $('msgInput');
const chatForm       = $('chatForm');
const sendBtn        = $('sendBtn');
const messageArea    = $('messageArea');
const typingIndicator= $('typingIndicator');
const charCount      = $('charCount');
const welcomeState   = $('welcomeState');
const clearBtn       = $('clearBtn');
const statusDot      = $('statusDot');
const statusText     = $('statusText');
const modelBadge     = $('modelBadge');
const searchBadge    = $('searchBadge');
const sidebar        = $('sidebar');
const sidebarToggle  = $('sidebarToggle');
const headerSub      = $('headerSub');

// ── Init ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  bindEvents();
});

// ── Health check ──────────────────────────────────────────
async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error('Server returned ' + res.status);
    const data = await res.json();

    statusDot.className  = 'status-dot online';
    statusText.textContent = 'Online';
    modelBadge.textContent = data.model ?? '—';

    if (data.search_enabled) {
      searchBadge.classList.add('active');
      searchBadge.title = 'Tìm kiếm web đang hoạt động';
    }
  } catch {
    statusDot.className  = 'status-dot offline';
    statusText.textContent = 'Không kết nối được';
    headerSub.textContent  = 'Server offline';
  }
}

// ── Event bindings ────────────────────────────────────────
function bindEvents() {
  // Form submit
  chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    handleSend();
  });

  // Textarea: Enter = send, Shift+Enter = newline
  msgInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  // Auto-resize textarea
  msgInput.addEventListener('input', () => {
    updateCharCount();
    autoResize();
    sendBtn.disabled = msgInput.value.trim().length === 0 || isLoading;
  });

  // Suggestion chips
  document.querySelectorAll('.suggestion-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const msg = chip.dataset.msg;
      if (msg && !isLoading) {
        msgInput.value = msg;
        updateCharCount();
        autoResize();
        sendBtn.disabled = false;
        closeSidebar();
        handleSend();
      }
    });
  });

  // Clear conversation
  clearBtn.addEventListener('click', clearConversation);

  // Sidebar toggle (mobile)
  sidebarToggle.addEventListener('click', toggleSidebar);
}

// ── Send message ──────────────────────────────────────────
async function handleSend() {
  const text = msgInput.value.trim();
  if (!text || isLoading) return;

  // Dismiss welcome state
  if (welcomeState) {
    welcomeState.style.display = 'none';
  }

  // Append user message
  appendMessage('user', text);

  // Clear input
  msgInput.value = '';
  updateCharCount();
  autoResize();
  sendBtn.disabled = true;

  // Track in history
  conversationHistory.push({ role: 'user', content: text });

  // Show typing indicator
  setLoading(true);

  try {
    const response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        session_id: sessionId,
        conversation_history: conversationHistory.slice(0, -1), // exclude current
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      // Structured error from our API
      const errMsg = data.message ?? `Server error ${response.status}`;
      appendMessage('ai', errMsg, [], true);
      return;
    }

    // Success
    sessionId = data.session_id;
    const aiText = data.response ?? '(Không có phản hồi)';

    conversationHistory.push({ role: 'assistant', content: aiText });
    appendMessage('ai', aiText, data.tools_used ?? []);

  } catch (err) {
    appendMessage('ai', `Lỗi kết nối: ${err.message}. Kiểm tra server đang chạy không?`, [], true);
  } finally {
    setLoading(false);
    sendBtn.disabled = msgInput.value.trim().length === 0;
  }
}

// ── Append message bubble ─────────────────────────────────
function appendMessage(role, text, tools = [], isError = false) {
  const isUser = role === 'user';

  const group = document.createElement('div');
  group.className = `msg-group ${isUser ? 'user-group' : 'ai-group'}`;

  const avatarLabel = isUser ? 'U' : 'H';

  let bubbleContent = isUser
    ? escapeHtml(text)
    : renderMarkdown(text);

  let toolHtml = '';
  if (!isUser && tools.length > 0) {
    const tags = tools.map((t) => `<span class="tool-tag">${escapeHtml(t)}</span>`).join('');
    toolHtml = `<div class="tool-tags">${tags}</div>`;
  }

  const timestamp = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });

  group.innerHTML = `
    <div class="msg msg-${isUser ? 'user' : 'ai'}">
      <div class="msg-avatar" aria-hidden="true">${avatarLabel}</div>
      <div class="msg-bubble${isError ? ' msg-error' : ''}">
        ${bubbleContent}
        ${toolHtml}
      </div>
    </div>
    <div class="msg-meta">${timestamp}</div>
  `;

  messageArea.appendChild(group);
  scrollToBottom();
}

// ── Typing indicator ──────────────────────────────────────
function setLoading(loading) {
  isLoading = loading;
  typingIndicator.hidden = !loading;
  if (loading) scrollToBottom();
}

// ── Markdown renderer (lightweight, no deps) ──────────────
function renderMarkdown(raw) {
  let html = escapeHtml(raw);

  // Code blocks (``` ... ```)
  html = html.replace(/```[\w]*\n?([\s\S]*?)```/g, (_, code) =>
    `<pre style="background:var(--bg-raised);border:1px solid var(--border);border-radius:8px;padding:12px 14px;overflow-x:auto;margin:8px 0;font-family:'JetBrains Mono',monospace;font-size:12.5px;line-height:1.6">${code.trim()}</pre>`
  );

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  // Italic
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // H3
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  // H2
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  // H1
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

  // Unordered list items
  html = html.replace(/^[-*•] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>\n?)+/gs, (match) => `<ul>${match}</ul>`);

  // Ordered list items
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

  // Links (only for text that comes from markdown)
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );

  // Horizontal rule
  html = html.replace(/^---+$/gm, '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">');

  // Paragraphs (double newlines)
  html = html.replace(/\n{2,}/g, '</p><p>');
  html = `<p>${html}</p>`;

  // Single newlines → <br>
  html = html.replace(/([^>])\n([^<])/g, '$1<br>$2');

  // Clean empty tags
  html = html.replace(/<p>\s*<\/p>/g, '');

  return html;
}

// ── Helpers ───────────────────────────────────────────────
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    messageArea.scrollTop = messageArea.scrollHeight;
  });
}

function autoResize() {
  msgInput.style.height = 'auto';
  msgInput.style.height = Math.min(msgInput.scrollHeight, 160) + 'px';
}

function updateCharCount() {
  const len = msgInput.value.length;
  charCount.textContent = `${len}/2000`;
  charCount.className = 'char-count' +
    (len > 1800 ? ' max' : len > 1500 ? ' warn' : '');
}

function clearConversation() {
  conversationHistory = [];
  sessionId = null;

  // Remove all message groups
  const groups = messageArea.querySelectorAll('.msg-group, .msg-group.user-group');
  groups.forEach((g) => g.remove());

  // Show welcome state again
  if (welcomeState) welcomeState.style.display = '';
}

// ── Sidebar (mobile) ──────────────────────────────────────
function toggleSidebar() {
  const isOpen = sidebar.classList.toggle('open');
  if (isOpen) {
    // Add overlay
    const overlay = document.createElement('div');
    overlay.id = 'sidebarOverlay';
    overlay.style.display = 'block';
    overlay.addEventListener('click', closeSidebar);
    document.body.appendChild(overlay);
  } else {
    closeSidebar();
  }
}

function closeSidebar() {
  sidebar.classList.remove('open');
  const overlay = $('sidebarOverlay');
  if (overlay) overlay.remove();
}
