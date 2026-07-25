/**
 * Hana Travel AI – Frontend Chat & Interactive Workspace Logic (Phase 4)
 * Pure vanilla JS, no dependencies.
 */

const API_BASE = '/api';

// ── State ─────────────────────────────────────────────────
let sessionId = null;
let conversationHistory = [];
let isLoading = false;
let currentPlan = null;
let currentDecision = null;

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

// Workspace refs (Phase 4 HITL)
const workspacePanel   = $('workspacePanel');
const planStatusBadge  = $('planStatusBadge');
const tripForm         = $('tripForm');
const tripOrigin       = $('tripOrigin');
const tripDestination  = $('tripDestination');
const tripDeparture    = $('tripDeparture');
const tripDays         = $('tripDays');
const tripTravelers    = $('tripTravelers');
const tripComfort      = $('tripComfort');
const tripBudget       = $('tripBudget');

const costSection      = $('costSection');
const costTotal        = $('costTotal');
const costPerPerson    = $('costPerPerson');
const costBreakdownList= $('costBreakdownList');
const costGap          = $('costGap');

const riskSection      = $('riskSection');
const riskList          = $('riskList');
const confirmTripBtn   = $('confirmTripBtn');

// ── Init ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  bindEvents();
  bindWorkspaceEvents();
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

function bindWorkspaceEvents() {
  // Form inputs change (HITL Patch)
  const inputs = [tripOrigin, tripDestination, tripDeparture, tripDays, tripTravelers, tripComfort, tripBudget];
  inputs.forEach((input) => {
    input.addEventListener('change', patchTripPlan);
  });

  // Button confirm click (HITL Confirm)
  confirmTripBtn.addEventListener('click', confirmTripPlan);
}

// ── Send message (SSE Streaming) ──────────────────────────
async function handleSend(customText = null) {
  const text = customText || msgInput.value.trim();
  if (!text || isLoading) return;

  // Dismiss welcome state
  if (welcomeState) {
    welcomeState.style.display = 'none';
  }

  // Append user message
  appendMessage('user', text);

  // Clear input if not custom text
  if (!customText) {
    msgInput.value = '';
    updateCharCount();
    autoResize();
  }
  sendBtn.disabled = true;

  // Show typing indicator / status bar
  setLoading(true);

  // Create temporary bubble for streaming text
  const aiBubbleId = appendEmptyAiBubble();
  const bubbleDiv = $(aiBubbleId);

  // Track in history
  conversationHistory.push({ role: 'user', content: text });

  let accumulatedResponse = '';

  try {
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        session_id: sessionId,
        conversation_history: conversationHistory.slice(0, -1), // exclude current
      }),
    });

    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.message ?? `Server error ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // keep last incomplete line

      for (const line of lines) {
        const cleanLine = line.trim();
        if (!cleanLine.startsWith('data: ')) continue;

        try {
          const payload = JSON.parse(cleanLine.slice(6));

          if (payload.type === 'status') {
            // Hiển thị trạng thái hoạt động của agent
            updateStatusText(payload.status);
          } else if (payload.type === 'token') {
            // Tích lũy và cập nhật text
            accumulatedResponse += payload.content;
            bubbleDiv.innerHTML = renderMarkdown(accumulatedResponse);
            scrollToBottom();
          } else if (payload.type === 'plan') {
            // Cập nhật TripPlan lên UI
            currentPlan = payload.data;
            updateWorkspaceUI();
          } else if (payload.type === 'decision') {
            // Cập nhật Decision Report (Chi phí / rủi ro) lên UI
            currentDecision = payload.data;
            updateWorkspaceUI();
          } else if (payload.type === 'done') {
            // Kết thúc an toàn
            sessionId = payload.session_id;
            if (payload.tools_used && payload.tools_used.length > 0) {
              appendToolTags(bubbleDiv, payload.tools_used);
            }
          } else if (payload.type === 'error') {
            throw new Error(payload.message);
          }
        } catch (e) {
          console.error("Lỗi khi parse SSE line:", cleanLine, e);
        }
      }
    }

    // Save success response to history
    conversationHistory.push({ role: 'assistant', content: accumulatedResponse });

  } catch (err) {
    bubbleDiv.classList.add('msg-error');
    bubbleDiv.innerHTML = `<p>Lỗi: ${err.message}</p>`;
  } finally {
    setLoading(false);
    updateStatusText("Trợ lý du lịch AI");
    sendBtn.disabled = msgInput.value.trim().length === 0;
  }
}

// ── Append empty AI message bubble for streaming ────────
let bubbleCounter = 0;
function appendEmptyAiBubble() {
  const isUser = false;
  bubbleCounter++;
  const bubbleId = `ai-bubble-${bubbleCounter}`;

  const group = document.createElement('div');
  group.className = `msg-group ai-group`;

  const timestamp = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });

  group.innerHTML = `
    <div class="msg msg-ai">
      <div class="msg-avatar" aria-hidden="true">H</div>
      <div class="msg-bubble" id="${bubbleId}">
        <span class="streaming-cursor"></span>
      </div>
    </div>
    <div class="msg-meta">${timestamp}</div>
  `;

  messageArea.appendChild(group);
  scrollToBottom();
  return bubbleId;
}

// ── Append static message bubble (User messages) ─────────
function appendMessage(role, text, isError = false) {
  const isUser = role === 'user';

  const group = document.createElement('div');
  group.className = `msg-group ${isUser ? 'user-group' : 'ai-group'}`;

  const avatarLabel = isUser ? 'U' : 'H';
  const bubbleContent = isUser ? escapeHtml(text) : renderMarkdown(text);
  const timestamp = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });

  group.innerHTML = `
    <div class="msg msg-${isUser ? 'user' : 'ai'}">
      <div class="msg-avatar" aria-hidden="true">${avatarLabel}</div>
      <div class="msg-bubble${isError ? ' msg-error' : ''}">
        ${bubbleContent}
      </div>
    </div>
    <div class="msg-meta">${timestamp}</div>
  `;

  messageArea.appendChild(group);
  scrollToBottom();
}

function appendToolTags(bubbleElement, tools) {
  const toolTagsDiv = document.createElement('div');
  toolTagsDiv.className = 'tool-tags';
  tools.forEach(tool => {
    const span = document.createElement('span');
    span.className = 'tool-tag';
    span.textContent = tool;
    toolTagsDiv.appendChild(span);
  });
  bubbleElement.appendChild(toolTagsDiv);
}

// ── Update Workspace panel state ─────────────────────────
function updateWorkspaceUI() {
  if (!currentPlan) {
    workspacePanel.style.display = 'none';
    return;
  }

  // Show panel
  workspacePanel.style.display = 'flex';

  // Badge status
  planStatusBadge.className = `plan-status-badge ${currentPlan.status}`;
  planStatusBadge.textContent = currentPlan.status === 'draft' ? 'Nháp' : 'Đã duyệt';

  // Fill form fields
  tripOrigin.value = currentPlan.origin || '';
  tripDestination.value = currentPlan.destination || '';
  tripDeparture.value = currentPlan.dates.departure || '';
  tripDays.value = currentPlan.dates.days || '';
  tripTravelers.value = currentPlan.travelers || '1';
  tripComfort.value = currentPlan.comfort_level || 'medium';
  tripBudget.value = currentPlan.budget.total || '';

  // Confirm button label & state
  if (currentPlan.status === 'confirmed') {
    confirmTripBtn.disabled = true;
    confirmTripBtn.textContent = 'Đã xác nhận & Đang tìm';
    confirmTripBtn.style.background = '#22c55e';
  } else {
    confirmTripBtn.disabled = false;
    confirmTripBtn.textContent = 'Xác nhận & Tìm kiếm';
    confirmTripBtn.style.background = 'linear-gradient(to right, #0ea5e9, #0284c7)';
  }

  // Cost estimates
  if (currentDecision && currentDecision.cost_estimate) {
    costSection.style.display = 'flex';
    const est = currentDecision.cost_estimate;
    costTotal.textContent = `${Number(est.total_all_people).toLocaleString('vi-VN')} VND`;
    costPerPerson.textContent = `${Number(est.total_per_person).toLocaleString('vi-VN')} VND / người`;

    // Breakdown items
    const b = est.breakdown;
    costBreakdownList.innerHTML = `
      <div class="breakdown-item"><span>Vé máy bay (người):</span> <span>${Number(b.flight_per_person).toLocaleString('vi-VN')} VND</span></div>
      <div class="breakdown-item"><span>Khách sạn (đêm):</span> <span>${Number(b.accommodation_per_night).toLocaleString('vi-VN')} VND</span></div>
      <div class="breakdown-item"><span>Ăn uống (người/ngày):</span> <span>${Number(b.food_per_person_per_day).toLocaleString('vi-VN')} VND</span></div>
      <div class="breakdown-item"><span>Di chuyển nội địa (tổng):</span> <span>${Number(b.transport_local_total).toLocaleString('vi-VN')} VND</span></div>
      <div class="breakdown-item"><span>Giải trí/Tham quan (tổng):</span> <span>${Number(b.activities_total).toLocaleString('vi-VN')} VND</span></div>
    `;

    // Gap comparison
    if (est.budget_provided > 0) {
      costGap.style.display = 'block';
      if (est.budget_gap >= 0) {
        costGap.className = 'cost-gap surplus';
        costGap.textContent = `Dư dôi ~${Number(est.budget_gap).toLocaleString('vi-VN')} VND`;
      } else {
        costGap.className = 'cost-gap deficit';
        costGap.textContent = `Thiếu hụt ~${Number(Math.abs(est.budget_gap)).toLocaleString('vi-VN')} VND`;
      }
    } else {
      costGap.style.display = 'none';
    }
  } else {
    costSection.style.display = 'none';
  }

  // Risks list
  if (currentDecision && currentDecision.risks && currentDecision.risks.length > 0) {
    riskSection.style.display = 'flex';
    riskList.innerHTML = currentDecision.risks.map((risk) => {
      const riskClass = `risk-${risk.level}`;
      const icon = risk.level === 'high' ? '🔴' : risk.level === 'medium' ? '🟡' : '🟢';
      return `
        <div class="risk-card ${riskClass}">
          <div class="risk-title">${icon} ${escapeHtml(risk.title)}</div>
          <div class="risk-detail">${escapeHtml(risk.detail)}</div>
          <div class="risk-suggestion">💡 ${escapeHtml(risk.suggestion)}</div>
        </div>
      `;
    }).join('');
  } else if (currentPlan && currentPlan.status === 'confirmed') {
    // If confirmed and no risk calculated yet, keep showing or show empty
    riskSection.style.display = 'none';
  } else {
    riskSection.style.display = 'none';
  }
}

// ── Patch TripPlan (HITL) ────────────────────────────────
async function patchTripPlan() {
  if (!sessionId) return;

  const patchData = {
    origin: tripOrigin.value.trim() || null,
    destination: tripDestination.value.trim() || null,
    dates: {
      departure: tripDeparture.value.trim() || null,
      days: parseInt(tripDays.value) || null,
    },
    travelers: parseInt(tripTravelers.value) || 1,
    comfort_level: tripComfort.value,
    budget: {
      total: parseFloat(tripBudget.value.replace(/,/g, '')) || null,
    }
  };

  try {
    const res = await fetch(`${API_BASE}/trips/${sessionId}/plan`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patchData),
    });

    if (!res.ok) throw new Error("Cập nhật biểu mẫu thất bại.");
    const data = await res.json();
    
    // Update local plan & decision with new calculations
    currentPlan = data.plan;
    currentDecision = data.decision;
    updateWorkspaceUI();
    
  } catch (err) {
    console.error("Patch error:", err);
  }
}

// ── Confirm TripPlan (HITL) ──────────────────────────────
async function confirmTripPlan() {
  if (!sessionId) return;

  try {
    confirmTripBtn.disabled = true;
    confirmTripBtn.textContent = 'Đang gửi...';

    const res = await fetch(`${API_BASE}/trips/${sessionId}/confirm`, {
      method: 'POST',
    });

    if (!res.ok) throw new Error("Không thể xác nhận kế hoạch du lịch.");
    const data = await res.json();

    // Confirm success
    currentPlan = data.plan;
    updateWorkspaceUI();

    // Trigger agent search using SSE chat stream!
    handleSend(data.trigger_message);

  } catch (err) {
    alert(err.message);
    confirmTripBtn.disabled = false;
    confirmTripBtn.textContent = 'Xác nhận & Tìm kiếm';
  }
}

// ── Typing indicator / status bar helper ────────────────
function setLoading(loading) {
  isLoading = loading;
  typingIndicator.hidden = !loading;
  if (loading) scrollToBottom();
}

function updateStatusText(text) {
  headerSub.textContent = text;
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

  // Links
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
  currentPlan = null;
  currentDecision = null;

  // Remove all message groups
  const groups = messageArea.querySelectorAll('.msg-group, .msg-group.user-group');
  groups.forEach((g) => g.remove());

  // Show welcome state again
  if (welcomeState) welcomeState.style.display = '';

  // Hide workspace
  updateWorkspaceUI();
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
