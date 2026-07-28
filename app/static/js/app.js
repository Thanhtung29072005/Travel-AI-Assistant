/**
 * Travel AI Assistant – Frontend Logic (Light Mode Redesign)
 * Vanilla JS, no dependencies.
 */

const API_BASE = '/api';

// ── State ──────────────────────────────────────────────────
let sessionId     = null;
let conversationHistory = [];
let isLoading     = false;
let currentPlan   = null;
let currentDecision = null;
let currentItinerary = null;
let chatHistory   = []; // [{id, title, sessionId, time}]
let activeHistoryId = null;

// ── DOM refs ───────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

const msgInput        = $('msgInput');
const chatForm        = $('chatForm');
const sendBtn         = $('sendBtn');
const messageArea     = $('messageArea');
const typingIndicator = $('typingIndicator');
const welcomeState    = $('welcomeState');
const sidebar         = $('sidebar');
const sidebarToggle   = $('sidebarToggle');
const headerSub       = $('headerSub');
const headerName      = $('headerName');
const historyList     = $('historyList');
const newChatBtn      = $('newChatBtn');

// Workspace refs
const workspacePanel  = $('workspacePanel');
const wsTripTitle     = $('wsTripTitle');
const wsTripMeta      = $('wsTripMeta');
const wsTags          = $('wsTags');
const planInfoSection = $('planInfoSection');
const editPlanBtn     = $('editPlanBtn');
const tripEditForm    = $('tripEditForm');
const formSaveBtn     = $('formSaveBtn');

// KV fields
const kvOrigin        = $('kvOrigin');
const kvDestination   = $('kvDestination');
const kvDates         = $('kvDates');
const kvTravelers     = $('kvTravelers');
const kvPreferences   = $('kvPreferences');
const kvComfort       = $('kvComfort');

// Form fields
const tripOrigin      = $('tripOrigin');
const tripDestination = $('tripDestination');
const tripDeparture   = $('tripDeparture');
const tripDays        = $('tripDays');
const tripTravelers   = $('tripTravelers');
const tripComfort     = $('tripComfort');
const tripBudget      = $('tripBudget');

// Cost/Risk
const costSection       = $('costSection');
const costTotal         = $('costTotal');
const costPerPerson     = $('costPerPerson');
const costBreakdownList = $('costBreakdownList');
const costGap           = $('costGap');
const riskSection       = $('riskSection');
const riskList          = $('riskList');
const itinerarySection  = $('itinerarySection');
const itineraryList     = $('itineraryList');

const reasonSection   = $('reasonSection');
const reasonBox       = $('reasonBox');
const reasonText      = $('reasonText');
const confirmTripBtn  = $('confirmTripBtn');
const exportMdBtn     = $('exportMdBtn');
const exportPdfBtn    = $('exportPdfBtn');

// ── Init ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  loadHistoryFromStorage();
  bindEvents();
});

// ── Health check ───────────────────────────────────────────
async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error('Server returned ' + res.status);
    const data = await res.json();
    headerSub.textContent = `Trợ lý du lịch AI · ${data.model ?? ''}`;
  } catch {
    headerSub.textContent = 'Server offline';
  }
}

// ── Event bindings ─────────────────────────────────────────
function bindEvents() {
  chatForm.addEventListener('submit', (e) => { e.preventDefault(); handleSend(); });

  msgInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  });

  msgInput.addEventListener('input', () => {
    autoResize();
    sendBtn.disabled = msgInput.value.trim().length === 0 || isLoading;
  });

  // Welcome chips
  document.querySelectorAll('.welcome-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const msg = chip.dataset.msg;
      if (msg && !isLoading) {
        msgInput.value = msg;
        autoResize();
        sendBtn.disabled = false;
        handleSend();
      }
    });
  });

  // New chat button
  newChatBtn.addEventListener('click', startNewChat);

  // Sidebar toggle (mobile)
  sidebarToggle.addEventListener('click', toggleSidebar);

  // Edit plan toggle
  editPlanBtn.addEventListener('click', () => {
    tripEditForm.classList.toggle('visible');
    editPlanBtn.textContent = tripEditForm.classList.contains('visible') ? 'Đóng' : 'Chỉnh sửa';
  });

  // Save form changes
  formSaveBtn.addEventListener('click', patchTripPlan);

  // Confirm trip
  confirmTripBtn.addEventListener('click', confirmTripPlan);

  // Export buttons
  exportMdBtn.addEventListener('click', exportMarkdown);
  exportPdfBtn.addEventListener('click', printWorkspace);

  // Settings / Help (placeholder)
  $('settingsBtn').addEventListener('click', () => alert('Cài đặt – sắp ra mắt!'));
  $('helpBtn').addEventListener('click', () => alert('Trợ giúp – sắp ra mắt!'));

  // More button (header)
  $('moreHeaderBtn').addEventListener('click', () => alert('Thêm tùy chọn – sắp ra mắt!'));
}

// ── Chat History (localStorage) ───────────────────────────
function loadHistoryFromStorage() {
  try {
    const stored = localStorage.getItem('travelAI_history');
    chatHistory = stored ? JSON.parse(stored) : [];
  } catch { chatHistory = []; }
  renderHistoryList();
}

function saveHistoryToStorage() {
  localStorage.setItem('travelAI_history', JSON.stringify(chatHistory.slice(0, 20)));
}

function renderHistoryList() {
  historyList.innerHTML = '';
  if (chatHistory.length === 0) {
    historyList.innerHTML = '<div style="padding:12px 10px;font-size:12px;color:var(--text-muted);text-align:center">Chưa có cuộc trò chuyện</div>';
    return;
  }
  chatHistory.forEach((item) => {
    const btn = document.createElement('button');
    btn.className = `history-item${item.id === activeHistoryId ? ' active' : ''}`;
    btn.dataset.id = item.id;

    const emoji = item.title.includes('Phú Quốc') ? '🏝' :
                  item.title.includes('Đà Nẵng') ? '🌊' :
                  item.title.includes('Hà Nội') ? '🏛' :
                  item.title.includes('Hội An') ? '🏮' :
                  item.title.includes('Sapa') ? '⛰' : '✈';

    btn.innerHTML = `
      <div class="history-item-icon">${emoji}</div>
      <div class="history-item-text">
        <div class="history-item-title">${escapeHtml(item.title)}</div>
        <div class="history-item-time">${item.time}</div>
      </div>
    `;
    btn.addEventListener('click', () => {
      if (item.id === activeHistoryId) return;
      activeHistoryId = item.id;
      sessionId = item.sessionId;
      headerName.textContent = item.title;
      renderHistoryList();
      loadSession(item.sessionId);
    });
    historyList.appendChild(btn);
  });
}

function addToHistory(title, sid) {
  const id = Date.now().toString();
  const now = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
  chatHistory.unshift({ id, title, sessionId: sid, time: now });
  activeHistoryId = id;
  saveHistoryToStorage();
  renderHistoryList();
}

function updateHistoryTitle(title) {
  const item = chatHistory.find((h) => h.id === activeHistoryId);
  if (item) {
    item.title = title;
    saveHistoryToStorage();
    renderHistoryList();
  }
}

async function loadSession(sid) {
  if (!sid || sid === 'pending') {
    conversationHistory = [];
    currentPlan = null;
    currentDecision = null;
    const groups = messageArea.querySelectorAll('.msg-group');
    groups.forEach((g) => g.remove());
    if (welcomeState) welcomeState.style.display = '';
    workspacePanel.style.display = 'none';
    return;
  }

  setLoading(true);

  const groups = messageArea.querySelectorAll('.msg-group');
  groups.forEach((g) => g.remove());
  if (welcomeState) welcomeState.style.display = 'none';

  try {
    const res = await fetch(`${API_BASE}/trips/${sid}`);
    if (!res.ok) throw new Error("Không thể tải thông tin cuộc trò chuyện.");
    const data = await res.json();

    // 1. Phục hồi lịch sử chat
    conversationHistory = data.history || [];
    if (conversationHistory.length > 0) {
      conversationHistory.forEach((msg) => {
        appendMessage(msg.role, msg.content);
      });
    } else {
      if (welcomeState) welcomeState.style.display = '';
    }

    // 2. Phục hồi workspace
    currentPlan = data.plan;
    currentDecision = data.decision;
    currentItinerary = data.itinerary;
    updateWorkspaceUI();

  } catch (err) {
    console.error("Lỗi khi tải session:", err);
  } finally {
    setLoading(false);
  }
}

// ── New Chat ───────────────────────────────────────────────
function startNewChat(resetHeader = true) {
  // Đừng xóa activeHistoryId của session cũ khỏi list –
  // chỉ deactivate nó trên UI, dữ liệu vẫn còn trong localStorage.
  conversationHistory = [];
  sessionId = null;
  currentPlan = null;
  currentDecision = null;
  currentItinerary = null;
  activeHistoryId = null;

  // Clear messages
  const groups = messageArea.querySelectorAll('.msg-group');
  groups.forEach((g) => g.remove());
  if (welcomeState) welcomeState.style.display = '';

  // Hide workspace
  workspacePanel.style.display = 'none';

  if (resetHeader) {
    headerName.textContent = 'Lập kế hoạch chuyến đi';
  }
  renderHistoryList();

  msgInput.value = '';
  autoResize();
  sendBtn.disabled = true;
  closeSidebar();
}

// ── Send message ───────────────────────────────────────────
async function handleSend(customText = null) {
  const text = customText || msgInput.value.trim();
  if (!text || isLoading) return;

  if (welcomeState) welcomeState.style.display = 'none';

  appendMessage('user', text);

  if (!customText) {
    msgInput.value = '';
    autoResize();
  }
  sendBtn.disabled = true;
  setLoading(true, false);

  const aiBubbleId = appendEmptyAiBubble();
  const bubbleDiv = $(aiBubbleId);

  conversationHistory.push({ role: 'user', content: text });

  // ── Lưu lịch sử ngay từ tin nhắn đầu tiên (không chờ plan) ──
  if (!activeHistoryId) {
    const shortTitle = text.length > 45 ? text.slice(0, 45) + '…' : text;
    addToHistory(shortTitle, null); // sessionId = null, cập nhật sau khi có 'done'
  }

  let accumulatedResponse = '';
  let firstResponse = true;

  try {
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        session_id: sessionId,
        conversation_history: conversationHistory.slice(0, -1),
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
      buffer = lines.pop();

      for (const line of lines) {
        const cleanLine = line.trim();
        if (!cleanLine.startsWith('data: ')) continue;

        try {
          const payload = JSON.parse(cleanLine.slice(6));

          if (payload.type === 'status') {
            headerSub.textContent = payload.status;
          } else if (payload.type === 'token') {
            accumulatedResponse += payload.content;
            bubbleDiv.innerHTML = renderMarkdown(accumulatedResponse);
            scrollToBottom();
          } else if (payload.type === 'plan') {
            currentPlan = payload.data;
            // Cập nhật tiêu đề lịch sử khi biết điểm đến cụ thể
            if (currentPlan && currentPlan.destination) {
              const title = buildTripTitle(currentPlan);
              updateHistoryTitle(title);
              headerName.textContent = title;
            }
            updateWorkspaceUI();
          } else if (payload.type === 'decision') {
            currentDecision = payload.data;
            updateWorkspaceUI();
          } else if (payload.type === 'itinerary') {
            currentItinerary = payload.data;
            updateWorkspaceUI();
          } else if (payload.type === 'done') {
            sessionId = payload.session_id;
            // Cập nhật sessionId thật vào history item đã lưu từ đầu
            const item = chatHistory.find((h) => h.id === activeHistoryId);
            if (item) {
              item.sessionId = sessionId || item.sessionId;
              saveHistoryToStorage();
              renderHistoryList();
            }
            if (payload.tools_used && payload.tools_used.length > 0) {
              appendToolTags(bubbleDiv, payload.tools_used);
            }
          } else if (payload.type === 'error') {
            throw new Error(payload.message);
          }
        } catch (e) {
          console.error('SSE parse error:', cleanLine, e);
        }
      }
    }

    conversationHistory.push({ role: 'assistant', content: accumulatedResponse });

  } catch (err) {
    bubbleDiv.classList.add('msg-error');
    bubbleDiv.innerHTML = `<p>Lỗi: ${escapeHtml(err.message)}</p>`;
  } finally {
    setLoading(false);
    headerSub.textContent = 'Trợ lý du lịch AI';
    sendBtn.disabled = msgInput.value.trim().length === 0;
  }
}

function buildTripTitle(plan) {
  const dest = plan.destination || '';
  const days = plan.dates?.days || '';
  const travelers = plan.travelers || '';
  if (dest && days) return `${dest} ${days} ngày${travelers ? ` · ${travelers} người` : ''}`;
  if (dest) return `Chuyến đi ${dest}`;
  return 'Kế hoạch chuyến đi';
}

// ── Append bubbles ─────────────────────────────────────────
let bubbleCounter = 0;

function appendEmptyAiBubble() {
  bubbleCounter++;
  const bubbleId = `ai-bubble-${bubbleCounter}`;
  const group = document.createElement('div');
  group.className = 'msg-group ai-group';
  const timestamp = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
  group.innerHTML = `
    <div class="msg msg-ai">
      <div class="msg-avatar" aria-hidden="true">H</div>
      <div class="msg-bubble" id="${bubbleId}"><span class="streaming-cursor"></span></div>
    </div>
    <div class="msg-meta">${timestamp}</div>
  `;
  messageArea.appendChild(group);
  scrollToBottom();
  return bubbleId;
}

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
      <div class="msg-bubble${isError ? ' msg-error' : ''}">${bubbleContent}</div>
    </div>
    <div class="msg-meta">${timestamp}</div>
  `;
  messageArea.appendChild(group);
  scrollToBottom();
}

function appendToolTags(bubbleElement, tools) {
  const toolTagsDiv = document.createElement('div');
  toolTagsDiv.className = 'tool-tags';
  tools.forEach((tool) => {
    const span = document.createElement('span');
    span.className = 'tool-tag';
    span.textContent = tool;
    toolTagsDiv.appendChild(span);
  });
  bubbleElement.appendChild(toolTagsDiv);
}

// ── Update Workspace panel ─────────────────────────────────
function updateWorkspaceUI() {
  if (!currentPlan) {
    workspacePanel.style.display = 'none';
    return;
  }

  workspacePanel.style.display = 'flex';

  const dest = currentPlan.destination || '—';
  const days = currentPlan.dates?.days || '—';
  const travelers = currentPlan.travelers || 1;
  const budget = currentPlan.budget?.total;

  // Title & Meta
  wsTripTitle.textContent = dest !== '—' ? `Chuyến đi ${dest}` : 'Kế hoạch mới';

  let metaParts = [];
  if (days !== '—') metaParts.push(`${days} ngày`);
  if (travelers) metaParts.push(`${travelers} người`);
  if (budget) metaParts.push(`${Number(budget).toLocaleString('vi-VN')} VND`);
  wsTripMeta.textContent = metaParts.join(' · ') || '—';

  // Tags
  const status = currentPlan.status || 'draft';
  const riskCount = currentDecision?.risks?.length ?? 0;
  const totalCost = currentDecision?.cost_estimate?.total_all_people;
  wsTags.innerHTML = `
    ${!totalCost ? '<span class="ws-tag no-data">Không có dữ liệu</span>' : `<span class="ws-tag price">${Number(totalCost).toLocaleString('vi-VN')} VND</span>`}
    ${riskCount > 0 ? `<span class="ws-tag risk">${riskCount} cảnh báo</span>` : ''}
    <span class="ws-tag ${status === 'confirmed' ? 'confirmed' : 'draft'}">${status === 'confirmed' ? 'Đã duyệt' : 'Bản nháp'}</span>
  `;

  // KV fields
  const setKV = (el, val) => {
    if (val) {
      el.textContent = val;
      el.classList.remove('empty');
    } else {
      el.textContent = 'Chưa có';
      el.classList.add('empty');
    }
  };

  setKV(kvOrigin, currentPlan.origin || null);
  setKV(kvDestination, currentPlan.destination || null);

  const dep = currentPlan.dates?.departure;
  const daysNum = currentPlan.dates?.days;
  if (dep && daysNum) {
    try {
      const end = new Date(dep);
      end.setDate(end.getDate() + Number(daysNum) - 1);
      const fmt = (d) => `${d.getDate()}/${d.getMonth() + 1}/${d.getFullYear()}`;
      const start = new Date(dep);
      setKV(kvDates, `${fmt(start)} → ${fmt(end)}`);
    } catch { setKV(kvDates, dep); }
  } else {
    setKV(kvDates, null);
  }

  setKV(kvTravelers, travelers ? `${travelers} người` : null);
  setKV(kvPreferences, (currentPlan.preferences || []).join(', ') || null);

  const comfortMap = { budget: 'Tiết kiệm nhất', medium: 'Tầm trung', comfort: 'Thoải mái', luxury: 'Cao cấp' };
  setKV(kvComfort, comfortMap[currentPlan.comfort_level] || currentPlan.comfort_level || null);

  // Fill edit form
  tripOrigin.value      = currentPlan.origin || '';
  tripDestination.value = currentPlan.destination || '';
  tripDeparture.value   = currentPlan.dates?.departure || '';
  tripDays.value        = currentPlan.dates?.days || '';
  tripTravelers.value   = currentPlan.travelers || '1';
  tripComfort.value     = currentPlan.comfort_level || 'medium';
  tripBudget.value      = currentPlan.budget?.total || '';

  // Update Quick Links
  const quickLinksSection = $('quickLinksSection');
  const quickLinksList = $('quickLinksList');
  if (quickLinksSection && quickLinksList) {
    if (currentPlan && currentPlan.destination) {
      quickLinksSection.style.display = 'block';
      const origin = currentPlan.origin || '';
      const dest = currentPlan.destination;
      const dep = currentPlan.dates?.departure || '';
      
      let flightQuery = `vé máy bay`;
      if (origin) flightQuery += ` từ ${origin}`;
      flightQuery += ` đi ${dest}`;
      if (dep) flightQuery += ` ngày ${dep}`;
      const flightUrl = `https://www.google.com/search?q=${encodeURIComponent(flightQuery)}`;
      
      const hotelUrl = `https://www.booking.com/searchresults.vi.html?ss=${encodeURIComponent(dest)}`;
      const agodaUrl = `https://www.agoda.com/vi-vn/pages/agoda/default/DestinationSearchResult.aspx?city=${encodeURIComponent(dest)}`;
      const klookUrl = `https://www.klook.com/vi/search/result/?keyword=${encodeURIComponent(dest)}`;
      const mapsUrl = `https://www.google.com/maps/search/${encodeURIComponent(dest + ' địa điểm du lịch')}`;
      
      quickLinksList.innerHTML = `
        <a href="${flightUrl}" target="_blank" rel="noopener noreferrer" class="quick-link-item">
          <span class="quick-link-icon">✈</span>
          <span>Tìm vé máy bay trên Google</span>
        </a>
        <a href="${agodaUrl}" target="_blank" rel="noopener noreferrer" class="quick-link-item">
          <span class="quick-link-icon">🏨</span>
          <span>Tìm khách sạn trên Agoda</span>
        </a>
        <a href="${hotelUrl}" target="_blank" rel="noopener noreferrer" class="quick-link-item">
          <span class="quick-link-icon">⭐</span>
          <span>Đặt phòng trên Booking.com</span>
        </a>
        <a href="${klookUrl}" target="_blank" rel="noopener noreferrer" class="quick-link-item">
          <span class="quick-link-icon">🎟</span>
          <span>Mua vé vui chơi & tour trên Klook</span>
        </a>
        <a href="${mapsUrl}" target="_blank" rel="noopener noreferrer" class="quick-link-item">
          <span class="quick-link-icon">🗺</span>
          <span>Xem bản đồ du lịch Google Maps</span>
        </a>
      `;
    } else {
      quickLinksSection.style.display = 'none';
    }
  }

  // Confirm button
  const exportHeaderBtn = $('exportHeaderBtn');
  if (exportHeaderBtn) exportHeaderBtn.style.display = 'flex';

  if (status === 'confirmed') {
    confirmTripBtn.disabled = true;
    confirmTripBtn.textContent = '✓ Đã xác nhận & Đang tìm kiếm';
    confirmTripBtn.style.background = 'var(--success)';
    reasonSection.style.display = 'none';
  } else {
    confirmTripBtn.disabled = false;
    confirmTripBtn.textContent = 'Xác nhận kế hoạch';
    confirmTripBtn.style.background = '';

    // Reason box
    if (!totalCost) {
      reasonSection.style.display = 'block';
      reasonText.textContent = 'Không có dữ liệu chuyến bay.';
      reasonBox.className = 'reason-box';
    } else if (currentDecision?.cost_estimate?.budget_gap < 0) {
      reasonSection.style.display = 'block';
      reasonText.textContent = `Ngân sách thiếu ~${Number(Math.abs(currentDecision.cost_estimate.budget_gap)).toLocaleString('vi-VN')} VND.`;
      reasonBox.className = 'reason-box';
    } else {
      reasonSection.style.display = 'none';
    }
  }

  // Cost section
  if (currentDecision?.cost_estimate) {
    costSection.style.display = 'block';
    const est = currentDecision.cost_estimate;
    costTotal.textContent = `${Number(est.total_all_people).toLocaleString('vi-VN')} VND`;
    costPerPerson.textContent = `${Number(est.total_per_person).toLocaleString('vi-VN')} VND / người`;

    const b = est.breakdown;
    costBreakdownList.innerHTML = `
      <div class="breakdown-item"><span>Vé máy bay / người</span><span>${Number(b.flight_per_person).toLocaleString('vi-VN')} VND</span></div>
      <div class="breakdown-item"><span>Khách sạn / đêm</span><span>${Number(b.accommodation_per_night).toLocaleString('vi-VN')} VND</span></div>
      <div class="breakdown-item"><span>Ăn uống / người / ngày</span><span>${Number(b.food_per_person_per_day).toLocaleString('vi-VN')} VND</span></div>
      <div class="breakdown-item"><span>Di chuyển nội địa</span><span>${Number(b.transport_local_total).toLocaleString('vi-VN')} VND</span></div>
      <div class="breakdown-item"><span>Tham quan / giải trí</span><span>${Number(b.activities_total).toLocaleString('vi-VN')} VND</span></div>
    `;

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

  // Risk section
  if (currentDecision?.risks?.length > 0) {
    riskSection.style.display = 'block';
    riskList.innerHTML = currentDecision.risks.map((risk) => {
      const icon = risk.level === 'high' ? '🔴' : risk.level === 'medium' ? '🟡' : '🟢';
      return `
        <div class="risk-card risk-${risk.level}">
          <div class="risk-title">${icon} ${escapeHtml(risk.title)}</div>
          <div class="risk-detail">${escapeHtml(risk.detail)}</div>
          <div class="risk-suggestion">💡 ${escapeHtml(risk.suggestion)}</div>
        </div>
      `;
    }).join('');
  } else {
    riskSection.style.display = 'none';
  }

  // Itinerary section (if plan has itinerary data embedded in context)
  updateItineraryUI();
}

// ── Patch TripPlan (HITL) ──────────────────────────────────
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
    budget: { total: parseFloat(tripBudget.value.replace(/,/g, '')) || null },
  };

  try {
    formSaveBtn.textContent = 'Đang lưu...';
    formSaveBtn.disabled = true;

    const res = await fetch(`${API_BASE}/trips/${sessionId}/plan`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patchData),
    });

    if (!res.ok) throw new Error('Cập nhật thất bại.');
    const data = await res.json();
    currentPlan = data.plan;
    currentDecision = data.decision;
    updateWorkspaceUI();

    // Close form
    tripEditForm.classList.remove('visible');
    editPlanBtn.textContent = 'Chỉnh sửa';
  } catch (err) {
    alert(err.message);
  } finally {
    formSaveBtn.textContent = 'Lưu thay đổi';
    formSaveBtn.disabled = false;
  }
}

// ── Confirm TripPlan (HITL) ────────────────────────────────
async function confirmTripPlan() {
  if (!sessionId) return;
  try {
    confirmTripBtn.disabled = true;
    confirmTripBtn.textContent = 'Đang gửi...';

    const res = await fetch(`${API_BASE}/trips/${sessionId}/confirm`, { method: 'POST' });
    if (!res.ok) {
      const error = await res.json().catch(() => ({}));
      throw new Error(error.detail || error.message || 'Could not confirm the trip plan.');
    }
    const data = await res.json();
    currentPlan = data.plan;
    currentDecision = data.decision;
    currentItinerary = data.itinerary;
    updateWorkspaceUI();
    if (data.response) {
      appendMessage('assistant', data.response);
      conversationHistory.push({ role: 'assistant', content: data.response });
    }
  } catch (err) {
    alert(err.message);
    confirmTripBtn.disabled = false;
    confirmTripBtn.textContent = 'Xác nhận kế hoạch';
  }
}

// ── Export Markdown ────────────────────────────────────────
function exportMarkdown() {
  if (!currentPlan) return;
  const dest = currentPlan.destination || 'Chuyến đi';
  const days = currentPlan.dates?.days || '?';
  const travelers = currentPlan.travelers || 1;
  const budget = currentPlan.budget?.total;

  let md = `# Kế hoạch chuyến đi: ${dest}\n\n`;
  md += `**Thời gian:** ${days} ngày  \n`;
  md += `**Số người:** ${travelers}  \n`;
  if (budget) md += `**Ngân sách:** ${Number(budget).toLocaleString('vi-VN')} VND  \n`;
  md += '\n';

  if (currentDecision?.cost_estimate) {
    const est = currentDecision.cost_estimate;
    md += `## Dự toán chi phí\n\n`;
    md += `- **Tổng chi phí:** ${Number(est.total_all_people).toLocaleString('vi-VN')} VND\n`;
    md += `- **Chi phí / người:** ${Number(est.total_per_person).toLocaleString('vi-VN')} VND\n\n`;
  }

  if (currentDecision?.risks?.length > 0) {
    md += `## Cảnh báo rủi ro\n\n`;
    currentDecision.risks.forEach((r) => {
      md += `- **[${r.level.toUpperCase()}] ${r.title}:** ${r.detail}  \n  💡 ${r.suggestion}\n`;
    });
    md += '\n';
  }

  // Add conversation snippets
  md += `## Lịch sử tư vấn\n\n`;
  conversationHistory.forEach((msg) => {
    const label = msg.role === 'user' ? '**Bạn**' : '**Hana**';
    md += `${label}: ${msg.content}\n\n`;
  });

  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `kehoach-${(currentPlan.destination || 'chuyen-di').toLowerCase().replace(/\s+/g, '-')}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Loading state ──────────────────────────────────────────
function setLoading(loading, showIndicator = true) {
  isLoading = loading;
  typingIndicator.hidden = !loading || !showIndicator;
  if (loading) scrollToBottom();
}

function renderTableHTML(rows) {
  if (rows.length < 2) return rows.join('\n');
  const headers = rows[0].split('|').map(s => s.trim()).filter((s, idx) => idx > 0 && idx < rows[0].split('|').length - 1);
  const alignments = rows[1].split('|').map(s => s.trim()).filter((s, idx) => idx > 0 && idx < rows[1].split('|').length - 1).map(align => {
    if (align.startsWith(':') && align.endsWith(':')) return 'center';
    if (align.endsWith(':')) return 'right';
    return 'left';
  });

  let html = '<div style="overflow-x:auto; margin: 10px 0;"><table style="width:100%; border-collapse:collapse; font-size:13px; text-align:left; border: 1px solid var(--border);">';
  html += '<thead><tr style="background-color: var(--bg-raised); border-bottom: 2px solid var(--border);">';
  headers.forEach((h, idx) => {
    const align = alignments[idx] || 'left';
    html += `<th style="padding: 8px 10px; font-weight: 600; text-align: ${align}; border-right: 1px solid var(--border);">${h}</th>`;
  });
  html += '</tr></thead>';

  html += '<tbody>';
  for (let i = 2; i < rows.length; i++) {
    const cells = rows[i].split('|').map(s => s.trim()).filter((s, idx) => idx > 0 && idx < rows[i].split('|').length - 1);
    html += '<tr style="border-bottom: 1px solid var(--border);">';
    cells.forEach((c, idx) => {
      const align = alignments[idx] || 'left';
      html += `<td style="padding: 8px 10px; text-align: ${align}; border-right: 1px solid var(--border);">${c}</td>`;
    });
    html += '</tr>';
  }
  html += '</tbody></table></div>';
  return html;
}

function parseMarkdownTables(text) {
  const lines = text.split('\n');
  let inTable = false;
  let tableRows = [];
  let output = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith('|') && line.endsWith('|')) {
      inTable = true;
      tableRows.push(line);
    } else {
      if (inTable) {
        output.push(renderTableHTML(tableRows));
        tableRows = [];
        inTable = false;
      }
      output.push(lines[i]);
    }
  }
  if (inTable && tableRows.length > 0) {
    output.push(renderTableHTML(tableRows));
  }
  return output.join('\n');
}

// ── Markdown renderer ──────────────────────────────────────
function renderMarkdown(raw) {
  let html = escapeHtml(raw);

  // Convert escaped <br> tags back to HTML
  html = html.replace(/&lt;br\s*\/?&gt;/gi, '<br>');

  // Parse Markdown tables first
  html = parseMarkdownTables(html);

  // Code blocks
  html = html.replace(/```[\w]*\n?([\s\S]*?)```/g, (_, code) =>
    `<pre style="background:var(--bg-base);border:1px solid var(--border);border-radius:8px;padding:10px 12px;overflow-x:auto;margin:8px 0;font-family:'JetBrains Mono',monospace;font-size:12px;line-height:1.6">${code.trim()}</pre>`
  );

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  // Italic
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Headings (h5 → h4 → h3 → h2 → h1, most-specific first)
  html = html.replace(/^##### (.+)$/gm, '<h5 style="font-size:13px;font-weight:700;margin:10px 0 4px;color:var(--text-primary)">$1</h5>');
  html = html.replace(/^#### (.+)$/gm, '<h4 style="font-size:14px;font-weight:700;margin:10px 0 4px;color:var(--text-primary)">$1</h4>');
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm,  '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm,   '<h1>$1</h1>');

  // Lists
  html = html.replace(/^[-*•] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>\n?)+/gs, (match) => `<ul>${match}</ul>`);
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

  // Links
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );

  // Horizontal rule
  html = html.replace(/^---+$/gm, '<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">');

  // Paragraphs
  html = html.replace(/\n{2,}/g, '</p><p>');
  html = `<p>${html}</p>`;
  html = html.replace(/([^>])\n([^<])/g, '$1<br>$2');
  html = html.replace(/<p>\s*<\/p>/g, '');

  return html;
}

// ── Helpers ────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function scrollToBottom() {
  requestAnimationFrame(() => { messageArea.scrollTop = messageArea.scrollHeight; });
}

function autoResize() {
  msgInput.style.height = 'auto';
  msgInput.style.height = Math.min(msgInput.scrollHeight, 160) + 'px';
}

// ── Sidebar (mobile) ───────────────────────────────────────
function toggleSidebar() {
  const isOpen = sidebar.classList.toggle('open');
  if (isOpen) {
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

function parseItineraryMarkdown(md) {
  if (!md) return [];
  const lines = md.split('\n');
  let days = [];
  let currentDay = null;

  lines.forEach((line) => {
    const trimmed = line.trim();
    // Accept common LLM headings: "Ngày 1", "Lịch trình ngày 1", or "Day 1".
    const dayMatch = trimmed.match(/^(?:#{1,3}\s*)?(?:(?:lịch trình)\s*)?(?:ngày|day)\s*\d+\b.*$/i);
    if (dayMatch) {
      if (currentDay) days.push(currentDay);
      currentDay = {
        title: trimmed.replace(/^#{1,3}\s*/, ''),
        items: []
      };
    } else if (trimmed.startsWith('-') || trimmed.startsWith('*') || trimmed.startsWith('•')) {
      if (currentDay) {
        const content = trimmed.substring(1).trim();
        let type = 'attraction';
        const lower = content.toLowerCase();
        
        if (lower.startsWith('sáng') || lower.startsWith('chiều')) {
          type = 'attraction';
        } else if (lower.startsWith('trưa') || lower.startsWith('tối') || lower.includes('ăn') || lower.includes('ẩm thực')) {
          type = 'food';
        } else if (lower.includes('khách sạn') || lower.includes('check-in') || lower.includes('nghỉ ngơi')) {
          type = 'hotel';
        } else if (lower.includes('bay') || lower.includes('xe') || lower.includes('di chuyển') || lower.includes('đáp')) {
          type = 'transport';
        }
        
        currentDay.items.push({
          type: type,
          content: content
        });
      }
    }
  });

  if (currentDay) days.push(currentDay);
  return days;
}

function updateItineraryUI() {
  if (!currentItinerary) {
    itinerarySection.style.display = 'none';
    return;
  }

  const days = parseItineraryMarkdown(currentItinerary);
  if (days.length === 0) {
    // Do not silently hide a valid itinerary just because its Markdown does
    // not follow the exact timeline heading convention.
    itinerarySection.style.display = 'block';
    itineraryList.innerHTML = `<div class="itinerary-raw">${renderMarkdown(currentItinerary)}</div>`;
    return;
  }

  itinerarySection.style.display = 'block';
  itineraryList.innerHTML = days.map((day) => {
    const itemsHtml = day.items.map((item) => {
      let badgeLabel = 'Tham quan';
      if (item.type === 'food') badgeLabel = 'Ăn uống';
      if (item.type === 'hotel') badgeLabel = 'Khách sạn';
      if (item.type === 'transport') badgeLabel = 'Di chuyển';
      
      return `
        <div class="place-card">
          <div class="place-card-header">
            <span class="place-type-badge ${item.type}">${badgeLabel}</span>
            <div class="place-name">${escapeHtml(item.content)}</div>
          </div>
        </div>
      `;
    }).join('');

    return `
      <div class="day-block">
        <div class="day-header">
          <span class="day-label">${escapeHtml(day.title)}</span>
        </div>
        ${itemsHtml}
      </div>
    `;
  }).join('');
}

// ── Print Workspace (PDF Export) ───────────────────────────
function printWorkspace() {
  if (!currentPlan) {
    alert('Chưa có kế hoạch nào để xuất PDF. Hãy bắt đầu một cuộc hội thoại du lịch trước nhé!');
    return;
  }

  const wsBody = document.querySelector('.workspace-body');
  if (!wsBody) return;

  // Capture fully-rendered HTML (badges, bold text, tables already rendered)
  const contentHTML = wsBody.innerHTML;

  const tripTitle = currentPlan?.destination
    ? `Kế hoạch du lịch: ${currentPlan.destination}`
    : 'Kế hoạch du lịch – Hana AI';

  // Use the actual style.css from the server so colours/fonts are identical to the UI
  const cssHref = `${window.location.origin}/static/css/style.css?v=10`;
  const fontsHref = 'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap';

  // Only override layout-level things that differ in the print popup
  const overrideCSS = `
    /* Reset page chrome */
    html, body {
      background: #fff !important;
      color: #1a1a2e !important;
      padding: 24px 28px !important;
      margin: 0 !important;
      font-family: 'Inter', sans-serif !important;
      font-size: 13px !important;
      line-height: 1.6 !important;
    }

    /* Print heading */
    h1.print-title {
      font-size: 20px;
      font-weight: 700;
      color: #E53935;
      margin-bottom: 20px;
      padding-bottom: 10px;
      border-bottom: 2px solid #E53935;
    }

    /* Hide elements that should not appear in PDF */
    .trip-edit-form,
    #quickLinksSection,
    .workspace-footer { display: none !important; }

    /* Ensure workspace body is fully visible (not clipped/scrolled) */
    .workspace-body {
      overflow: visible !important;
      max-height: none !important;
      height: auto !important;
    }

    /* Page-break hints for multi-page PDFs */
    @media print {
      body { padding: 10mm 12mm !important; }
      .day-block   { page-break-inside: avoid; }
      .risk-card   { page-break-inside: avoid; }
      .cost-section { page-break-inside: avoid; }
      .place-card  { page-break-inside: avoid; }
    }
  `;

  const popup = window.open('', '_blank', 'width=820,height=960,scrollbars=yes');
  if (!popup) {
    alert('Trình duyệt đang chặn cửa sổ popup. Vui lòng cho phép popup từ trang này và thử lại.');
    return;
  }

  popup.document.write(`
    <!DOCTYPE html>
    <html lang="vi">
    <head>
      <meta charset="UTF-8" />
      <title>${tripTitle}</title>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
      <link href="${fontsHref}" rel="stylesheet" />
      <link rel="stylesheet" href="${cssHref}" />
      <style>${overrideCSS}</style>
    </head>
    <body>
      <h1 class="print-title">✈️ ${tripTitle}</h1>
      ${contentHTML}
    </body>
    </html>
  `);
  popup.document.close();

  // Give CSS + fonts time to load before triggering print dialog
  popup.onload = () => {
    setTimeout(() => {
      popup.focus();
      popup.print();
      popup.addEventListener('afterprint', () => popup.close());
    }, 800);
  };
}
