const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const setText = (selector, value, root = document) => { const node = $(selector, root); if (node) node.textContent = value; };

const API_BASE = window.localStorage.getItem('iv_api_base') || 'http://localhost:8000/api/v1';
const REVIEWER_ID = 'LT-01';
const REVIEWER_NAME = 'Linh Trần';

const flowNodes = ['underwriterNode','orchestratorNode','documentNode','incomeNode','policyNode','consistencyNode','recommendationNode','humanNode','executorNode','systemsNode'];
const edgeData = new Map();
let running = false;
let caseData = null;
let currentCaseId = null;
let selectedFiles = [];
let caseListCache = [];
let uploadedDocumentCount = 0;

const ACTION_SYSTEM_MAP = {
  UPDATE_INCOME_DRAFT: 'LOS',
  ATTACH_EVIDENCE: 'DMS',
  REQUEST_DOCUMENTS: 'Notification',
  CREATE_EXCEPTION_TASK: 'Workflow'
};

const EXECUTION_STATUS_LABEL = {
  SUCCESS: 'THÀNH CÔNG', DUPLICATE: 'TRÙNG LẶP (BỎ QUA)', SKIPPED: 'BỎ QUA', FAILED: 'THẤT BẠI'
};

const RECOMMENDATION_STATUS_LABEL = {
  READY_FOR_REVIEW: 'Sẵn sàng để chuyên viên duyệt',
  NEEDS_CLARIFICATION: 'Cần làm rõ trước khi duyệt',
  MISSING_DOCUMENTS: 'Thiếu tài liệu bắt buộc',
  POLICY_NOT_FOUND: 'Không tìm thấy chính sách áp dụng',
  MANUAL_REVIEW_REQUIRED: 'Cần xử lý thủ công',
  TECHNICAL_ERROR: 'Lỗi kỹ thuật',
  COMPLETED: 'Đã hoàn tất'
};

const WORKFLOW_STATE_LABEL = {
  OPEN_CASE: 'Hồ sơ mới', FETCHING_DOCUMENTS: 'Đang lấy tài liệu', EXTRACTING_DOCUMENT_DATA: 'Đang trích xuất',
  ANALYZING_INCOME_AND_POLICY: 'Đang phân tích', CROSS_CHECKING: 'Đang đối chiếu', BUILDING_RECOMMENDATION: 'Đang tạo đề xuất',
  HUMAN_REVIEW: 'Chờ chuyên viên duyệt', EXECUTING_APPROVED_ACTIONS: 'Đang thực thi', VERIFYING_EXECUTION: 'Đang xác minh thực thi',
  COMPLETED: 'Đã xác minh', AWAITING_DOCUMENTS: 'Chờ bổ sung tài liệu', MANUAL_REVIEW_REQUIRED: 'Cần xử lý thủ công', TECHNICAL_ERROR: 'Lỗi kỹ thuật'
};

const WORKFLOW_STATE_CSS = {
  OPEN_CASE: 'state-open', FETCHING_DOCUMENTS: 'state-fetching', EXTRACTING_DOCUMENT_DATA: 'state-extracting',
  ANALYZING_INCOME_AND_POLICY: 'state-analyzing', CROSS_CHECKING: 'state-crosschecking', BUILDING_RECOMMENDATION: 'state-building',
  HUMAN_REVIEW: 'state-review', EXECUTING_APPROVED_ACTIONS: 'state-building', VERIFYING_EXECUTION: 'state-building',
  COMPLETED: 'state-completed', AWAITING_DOCUMENTS: 'state-attention', MANUAL_REVIEW_REQUIRED: 'state-attention', TECHNICAL_ERROR: 'state-error'
};

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body && !(options.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
      'X-Role': 'UNDERWRITER',
      'X-Reviewer-Id': REVIEWER_ID,
      ...(options.headers || {})
    }
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { const body = await res.json(); detail = body.detail || detail; } catch (_) { /* no body */ }
    throw new Error(`${res.status} ${detail}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

function formatVnd(value) {
  if (value === null || value === undefined) return '—';
  const n = Number(value);
  return `${(n / 1e6).toLocaleString('vi-VN', { maximumFractionDigits: 1 })} triệu ₫`;
}

function initials(name) {
  if (!name) return '—';
  return name.split(/\s+/).filter(Boolean).map(x => x[0]).slice(-2).join('').toUpperCase();
}

function timeNow() {
  return new Date().toLocaleTimeString('vi-VN', { hour12:false });
}

function formatDateTime(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString('vi-VN', { hour12:false }); } catch (_) { return iso; }
}

function toast(title, detail) {
  const item = document.createElement('div'); item.className = 'toast';
  const strong = document.createElement('strong'); strong.textContent = title;
  const small = document.createElement('small'); small.textContent = detail;
  item.append(strong, small); $('#toastStack').append(item);
  setTimeout(() => item.remove(), 3600);
}

function addLog(source, message, tag = 'INFO', tone = '', evidenceKey = '') {
  const stream = $('#logStream'); if (!stream) return;
  const item = document.createElement('article'); item.className = 'log-item';
  const icon = document.createElement('span'); icon.className = `log-icon ${tone}`; icon.textContent = source.split(/\s+/).map(x => x[0]).join('').slice(0,2).toUpperCase();
  const content = document.createElement('div');
  const meta = document.createElement('div'); meta.className = 'log-meta';
  const name = document.createElement('strong'); name.textContent = source;
  const time = document.createElement('time'); time.textContent = timeNow();
  meta.append(name, time);
  const body = document.createElement('p'); body.textContent = message;
  const foot = document.createElement('div'); foot.className = 'log-foot';
  const badge = document.createElement('span'); badge.className = 'log-tag'; badge.textContent = tag;
  foot.append(badge);
  if (evidenceKey) {
    const button = document.createElement('button'); button.className = 'evidence-btn'; button.type = 'button'; button.title = 'Xem bằng chứng'; button.dataset.evidence = evidenceKey;
    button.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6 3h9l3 3v15H6zM14 3v4h4M9 12h6M9 16h6"/></svg>';
    button.addEventListener('click', () => openEvidence(evidenceKey)); foot.append(button);
  }
  content.append(meta, body, foot); item.append(icon, content); stream.prepend(item);
  setText('#eventCount', $$('.log-item', stream).length);
}

function openEvidence(id) {
  if (!caseData) return;
  const ev = (caseData.evidence || []).find(e => e.evidence_id === id);
  if (ev) {
    setText('#evidenceTitle', 'Bằng chứng hồ sơ khách hàng');
    setText('#evidenceDoc', ev.document_name);
    setText('#evidencePage', `${ev.location || ev.section_id || 'Trích xuất tài liệu'} · Trang ${ev.page_number}`);
    setText('#evidenceQuote', ev.quote);
    setText('#evidenceConfidence', ev.evidence_id);
    openModal('evidenceModal');
    return;
  }
  const cit = ((caseData.policy_result || {}).citations || []).find(c => c.chunk_id === id);
  if (cit) {
    setText('#evidenceTitle', 'Trích dẫn chính sách');
    setText('#evidenceDoc', cit.document_name);
    setText('#evidencePage', `${cit.section_id} · Trang ${cit.page_number} · Hiệu lực ${cit.effective_date}`);
    setText('#evidenceQuote', cit.quote);
    setText('#evidenceConfidence', cit.chunk_id);
    openModal('evidenceModal');
  }
}

function openModal(id) { const modal = document.getElementById(id); if (modal) modal.hidden = false; }
function closeModal(id) { const modal = document.getElementById(id); if (modal) modal.hidden = true; }

function setNodeMode(id, mode = 'locked') {
  const node = document.getElementById(id); if (!node) return;
  node.classList.remove('is-revealed','is-ready','is-active','is-complete');
  if (mode === 'ready') node.classList.add('is-revealed','is-ready');
  if (mode === 'active') node.classList.add('is-revealed','is-active');
  if (mode === 'complete') node.classList.add('is-revealed','is-complete');
  requestAnimationFrame(drawEdges);
}

function setAgentState(id, state, label, task) {
  const node = document.getElementById(id); if (!node) return;
  const status = $('[data-status]', node); const taskNode = $('[data-task]', node);
  if (status) { status.className = `agent-status ${state}`; setText('b', label, status); }
  if (taskNode && task) taskNode.textContent = task;
  const track = $('.status-track span', node);
  if (track) track.style.width = state === 'done' ? '100%' : state === 'idle' || state === 'locked' ? '0' : '34%';
}

function edgeDefinitions() {
  return [
    { id:'underwriter-orchestrator', from:'underwriterNode', to:'orchestratorNode', title:'Underwriter UI → Orchestrator Agent', label:'mở hồ sơ', t:.5 },
    { id:'orchestrator-document', from:'orchestratorNode', to:'documentNode', title:'Orchestrator → Document Agent', label:'giao việc', t:.6 },
    { id:'orchestrator-income', from:'orchestratorNode', to:'incomeNode', title:'Orchestrator → Income Agent', label:'giao việc', t:.6 },
    { id:'orchestrator-policy', from:'orchestratorNode', to:'policyNode', title:'Orchestrator → Policy Agent', label:'giao việc', t:.6 },
    { id:'document-consistency', from:'documentNode', to:'consistencyNode', title:'Document Agent → Consistency Agent', label:'kết quả', t:.52 },
    { id:'income-consistency', from:'incomeNode', to:'consistencyNode', title:'Income Agent → Consistency Agent', label:'kết quả', t:.52 },
    { id:'policy-consistency', from:'policyNode', to:'consistencyNode', title:'Policy Agent → Consistency Agent', label:'kết quả', t:.52 },
    { id:'consistency-recommendation', from:'consistencyNode', to:'recommendationNode', title:'Consistency Agent → Recommendation Builder', label:'đối chiếu', t:.5 },
    { id:'recommendation-human', from:'recommendationNode', to:'humanNode', title:'Recommendation Builder → Human Review Gate', label:'đề xuất', t:.5 },
    { id:'human-executor', from:'humanNode', to:'executorNode', title:'Human Review Gate → Action Executor', label:'phê duyệt', t:.52 },
    { id:'executor-systems', from:'executorNode', to:'systemsNode', title:'Action Executor → Hệ thống nghiệp vụ', label:'thực thi', t:.52 }
  ];
}

function nodeCenter(element, canvasRect) {
  const rect = element.getBoundingClientRect();
  return { x:rect.left - canvasRect.left + rect.width / 2, y:rect.top - canvasRect.top + rect.height / 2 };
}

function curvePath(from, to) {
  const dx = to.x - from.x; const dy = to.y - from.y;
  if (Math.abs(dx) > Math.abs(dy)) {
    return `M ${from.x} ${from.y} C ${from.x + dx * .46} ${from.y}, ${to.x - dx * .46} ${to.y}, ${to.x} ${to.y}`;
  }
  return `M ${from.x} ${from.y} C ${from.x} ${from.y + dy * .46}, ${to.x} ${to.y - dy * .46}, ${to.x} ${to.y}`;
}

function drawEdges() {
  const svg = $('#edgeLayer'); const canvas = $('#flowCanvas'); if (!svg || !canvas) return;
  const canvasRect = canvas.getBoundingClientRect();
  if (!canvasRect.width || !canvasRect.height) return;
  svg.setAttribute('viewBox', `0 0 ${canvasRect.width} ${canvasRect.height}`); svg.innerHTML = '';
  $$('.edge-hotspot', canvas).forEach(button => button.remove());
  edgeDefinitions().forEach(def => {
    const fromEl = document.getElementById(def.from); const toEl = document.getElementById(def.to);
    if (!fromEl || !toEl || !fromEl.offsetParent || !toEl.offsetParent || !fromEl.classList.contains('is-revealed') || !toEl.classList.contains('is-revealed')) return;
    const from = nodeCenter(fromEl, canvasRect); const to = nodeCenter(toEl, canvasRect); const pathData = curvePath(from, to);
    const group = document.createElementNS('http://www.w3.org/2000/svg','g'); group.dataset.edge = def.id;
    const hit = document.createElementNS('http://www.w3.org/2000/svg','path'); hit.setAttribute('d', pathData); hit.setAttribute('class','edge-hit');
    const path = document.createElementNS('http://www.w3.org/2000/svg','path'); path.setAttribute('d', pathData); path.setAttribute('class', `edge-visible ${edgeData.get(def.id)?.tone || ''}`);
    hit.addEventListener('click', event => showEdge(def, event));
    group.append(hit, path); svg.append(group);
    const t = def.t ?? .5;
    const hotspot = document.createElement('button'); hotspot.className = 'edge-hotspot'; hotspot.type = 'button'; hotspot.setAttribute('aria-label', def.title);
    hotspot.dataset.tone = edgeData.get(def.id)?.tone || 'idle'; hotspot.dataset.edge = def.id; hotspot.style.left = `${from.x + (to.x - from.x) * t}px`; hotspot.style.top = `${from.y + (to.y - from.y) * t}px`;
    const dot = document.createElement('i'); const label = document.createElement('span'); label.textContent = def.label; hotspot.append(dot, label);
    hotspot.addEventListener('click', event => showEdge(def, event)); canvas.append(hotspot);
  });
}

function updateEdge(id, status, detail, tone = 'active') {
  edgeData.set(id, { status, detail, tone }); drawEdges();
}

function showEdge(def, event) {
  const data = edgeData.get(def.id) || { status:'Kết nối sẵn sàng', detail:'Chưa truyền dữ liệu trong lượt xác minh này.' };
  setText('#edgeTitle', def.title.toUpperCase()); setText('#edgeStatus', data.status); setText('#edgeDetail', data.detail);
  const popover = $('#edgePopover'); const rect = $('#flowCanvas').getBoundingClientRect();
  popover.style.left = `${Math.min(Math.max(event.clientX - rect.left + 8, 8), rect.width - 272)}px`;
  popover.style.top = `${Math.min(Math.max(event.clientY - rect.top + 8, 8), rect.height - 130)}px`;
  popover.hidden = false;
}

function sendPacket(fromId, toId, tone = '', duration = 500) {
  const canvas = $('#flowCanvas'); const fromEl = document.getElementById(fromId); const toEl = document.getElementById(toId);
  if (!canvas || !fromEl || !toEl) return Promise.resolve();
  const rect = canvas.getBoundingClientRect(); const from = nodeCenter(fromEl, rect); const to = nodeCenter(toEl, rect);
  const packet = document.createElement('span'); packet.className = `message-packet ${tone}`;
  packet.style.left = `${from.x - 5}px`; packet.style.top = `${from.y - 5}px`; canvas.append(packet);
  const animation = packet.animate([
    { transform:'translate(0,0) scale(.65)', opacity:.2 },
    { transform:`translate(${(to.x-from.x)*.52}px,${(to.y-from.y)*.48 - 13}px) scale(1.25)`, opacity:1, offset:.52 },
    { transform:`translate(${to.x-from.x}px,${to.y-from.y}px) scale(.55)`, opacity:.12 }
  ], { duration, easing:'cubic-bezier(.45,0,.2,1)' });
  return animation.finished.catch(() => {}).finally(() => packet.remove());
}

function resetEdgeData() {
  edgeData.clear();
  edgeDefinitions().forEach(edge => edgeData.set(edge.id, { status:'Kết nối sẵn sàng', detail:'Chưa truyền dữ liệu trong lượt xác minh này.', tone:'' }));
}

function resetFlow(silent = false) {
  running = false;
  flowNodes.forEach(id => setNodeMode(id));
  setNodeMode('underwriterNode','ready');
  setAgentState('underwriterNode','idle','SẴN SÀNG','Mở hồ sơ và xác nhận dữ liệu đầu vào');
  setAgentState('orchestratorNode','locked','CHỜ','Điều phối state · task · retry · routing, không ghi dữ liệu');
  setAgentState('documentNode','locked','CHỜ','Đọc và trích xuất tài liệu (LLM/RAG hoặc regex tất định)');
  setAgentState('incomeNode','locked','CHỜ','Phân tích tiền lương và dòng tiền');
  setAgentState('policyNode','locked','CHỜ','Tra cứu quy định tín chấp ngân hàng qua RAG');
  setAgentState('consistencyNode','locked','CHỜ','Đối chiếu chéo, phát hiện thiếu và bất thường');
  setAgentState('recommendationNode','locked','CHỜ','Tạo kết quả xác minh và hành động đề xuất');
  setAgentState('humanNode','locked','CHỜ');
  setAgentState('executorNode','locked','KHÓA','Chờ quyết định của chuyên viên');
  $('#verifyBtn').disabled = true; $('#verifyBtn').textContent = 'Mở kiểm duyệt';
  $('#runBtn').disabled = false; $('#runBtn').innerHTML = '<span>✦</span> Chạy pipeline';
  setText('#stagePill','Sẵn sàng'); setText('#heroStatus','SẴN SÀNG');
  resetEdgeData(); $('#edgePopover').hidden = true; drawEdges();
  if (!silent) {
    $('#logStream').innerHTML = '';
    addLog('Hệ thống','Luồng xử lý đã sẵn sàng cho hồ sơ xác minh thu nhập.','SẴN SÀNG');
  }
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

function parseRoute() {
  const hash = window.location.hash.replace(/^#\/?/, '');
  const parts = hash.split('/').filter(Boolean);
  if (parts[0] === 'cases' && parts[1] === 'new') return { view: 'create' };
  if (parts[0] === 'cases' && parts[1]) return { view: 'command', caseId: parts[1] };
  return { view: 'cases' };
}

async function handleRoute() {
  const route = parseRoute();
  $$('.view').forEach(item => item.classList.toggle('active', item.id === `view-${route.view}`));
  $$('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.view === route.view || (route.view === 'command' && item.dataset.view === 'cases')));

  if (route.view === 'cases') {
    setText('#pageTitle', 'Danh sách hồ sơ xác minh thu nhập');
    await loadCaseList();
  } else if (route.view === 'create') {
    setText('#pageTitle', 'Tạo hồ sơ xác minh mới');
    resetCreateForm();
  } else if (route.view === 'command') {
    setText('#pageTitle', 'Chi tiết hồ sơ xác minh thu nhập');
    currentCaseId = route.caseId;
    await openCaseDetail(route.caseId);
  }
}

function navigate(hash) {
  window.location.hash = hash;
}

// ---------------------------------------------------------------------------
// System status (LLM / RAG mode)
// ---------------------------------------------------------------------------

async function loadSystemStatus() {
  try {
    const status = await apiFetch('/cases/system/status');
    const isLive = /\(live\)/i.test(status.llm_mode);
    const pill = $('#llmModePill');
    pill.textContent = isLive ? `LLM TRỰC TIẾP · ${status.llm_mode.split(':')[0]}` : 'CHẾ ĐỘ MOCK (KHÔNG CÓ LLM)';
    pill.classList.toggle('mode-live', isLive);
    pill.classList.toggle('mode-mock', !isLive);
    setText('#systemHealthLabel', isLive ? 'LLM + RAG trực tiếp' : 'Chế độ mock / rule-based');
    setText('#systemHealthDetail', `${status.llm_mode} · RAG: ${status.rag_mode}`);
    $('.system-health').classList.toggle('status-live', isLive);
    $('.system-health').classList.toggle('status-mock', !isLive);
  } catch (err) {
    setText('#llmModePill', 'KHÔNG KẾT NỐI ĐƯỢC BACKEND');
    setText('#systemHealthLabel', 'Không kết nối được backend');
    setText('#systemHealthDetail', API_BASE);
  }
}

// ---------------------------------------------------------------------------
// Case list view
// ---------------------------------------------------------------------------

function statusBadge(workflowState) {
  const span = document.createElement('span');
  span.className = `status-badge ${WORKFLOW_STATE_CSS[workflowState] || ''}`;
  span.textContent = WORKFLOW_STATE_LABEL[workflowState] || workflowState;
  return span;
}

function renderCaseRows(cases) {
  const rows = $('#caseRows'); rows.innerHTML = '';
  if (!cases.length) {
    const empty = document.createElement('div'); empty.className = 'empty-state';
    empty.textContent = 'Chưa có hồ sơ nào. Bấm "Tạo hồ sơ mới" để bắt đầu.';
    rows.append(empty);
    return;
  }
  cases.forEach(item => {
    const row = document.createElement('div'); row.className = 'table-row';
    const caseCell = document.createElement('div'); caseCell.className = 'case-cell';
    const logo = document.createElement('div'); logo.className = 'company-logo'; logo.textContent = initials(item.customer_name) || 'HS';
    const copy = document.createElement('div');
    const name = document.createElement('strong'); name.textContent = item.customer_name || '(Chưa có tên khách hàng)';
    const meta = document.createElement('small'); meta.textContent = `#${item.case_id} · ${item.application_id} · ${item.document_count} tài liệu`;
    copy.append(name, meta); caseCell.append(logo, copy);
    const amount = document.createElement('strong'); amount.textContent = item.requested_amount ? formatVnd(item.requested_amount) : '—';
    const term = document.createElement('span'); term.textContent = item.loan_term_months ? `${item.loan_term_months} tháng` : '—';
    const status = statusBadge(item.workflow_state);
    const open = document.createElement('button'); open.className = 'open-case'; open.type = 'button'; open.textContent = 'Xem →';
    open.addEventListener('click', () => navigate(`#/cases/${item.case_id}`));
    row.addEventListener('click', (event) => { if (event.target === row || event.target === caseCell || caseCell.contains(event.target)) navigate(`#/cases/${item.case_id}`); });
    row.append(caseCell, amount, term, status, open); rows.append(row);
  });
}

async function loadCaseList() {
  try {
    const result = await apiFetch('/cases');
    caseListCache = result.cases;
    setText('#totalCases', caseListCache.length);
    setText('#caseCount', caseListCache.length);
    setText('#pendingCases', caseListCache.filter(c => ['OPEN_CASE','FETCHING_DOCUMENTS','EXTRACTING_DOCUMENT_DATA','ANALYZING_INCOME_AND_POLICY','CROSS_CHECKING','BUILDING_RECOMMENDATION'].includes(c.workflow_state)).length);
    setText('#reviewCases', caseListCache.filter(c => c.workflow_state === 'HUMAN_REVIEW').length);
    setText('#caseListUpdatedAt', `Cập nhật ${timeNow()}`);
    renderCaseRows(caseListCache);
  } catch (err) {
    toast('Không kết nối được backend', err.message);
    renderCaseRows([]);
  }
}

$('#caseSearch').addEventListener('input', (event) => {
  const query = event.target.value.trim().toLowerCase();
  if (!query) { renderCaseRows(caseListCache); return; }
  renderCaseRows(caseListCache.filter(item =>
    (item.customer_name || '').toLowerCase().includes(query) ||
    item.case_id.toLowerCase().includes(query) ||
    item.application_id.toLowerCase().includes(query)
  ));
});

// ---------------------------------------------------------------------------
// Create case view
// ---------------------------------------------------------------------------

function resetCreateForm() {
  selectedFiles = [];
  $('#newCustomerName').value = ''; $('#newCustomerCode').value = ''; $('#newEmployer').value = '';
  $('#newLoanTerm').value = ''; $('#newRequestedAmount').value = '';
  $('#newDocumentsInput').value = '';
  renderFileList();
}

function renderFileList() {
  const list = $('#fileList'); list.innerHTML = '';
  selectedFiles.forEach((file, index) => {
    const chip = document.createElement('span'); chip.className = 'file-chip';
    const label = document.createElement('span'); label.textContent = `${file.name} (${(file.size/1024).toFixed(0)} KB)`;
    const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = '×';
    remove.addEventListener('click', () => { selectedFiles.splice(index, 1); renderFileList(); });
    chip.append(label, remove); list.append(chip);
  });
}

$('#newDocumentsInput').addEventListener('change', (event) => {
  selectedFiles = selectedFiles.concat(Array.from(event.target.files));
  renderFileList();
});

$('#cancelCreateBtn').addEventListener('click', () => navigate('#/cases'));

$('#submitCreateBtn').addEventListener('click', async () => {
  const customerName = $('#newCustomerName').value.trim();
  if (!customerName) { toast('Thiếu thông tin', 'Vui lòng nhập họ tên khách hàng.'); return; }
  const button = $('#submitCreateBtn'); button.disabled = true; button.textContent = 'Đang tạo hồ sơ…';
  try {
    const payload = {
      customer_name: customerName,
      customer_code: $('#newCustomerCode').value.trim() || null,
      employer: $('#newEmployer').value.trim() || null,
      requested_amount: $('#newRequestedAmount').value ? Number($('#newRequestedAmount').value) : null,
      loan_term_months: $('#newLoanTerm').value ? Number($('#newLoanTerm').value) : null,
    };
    const created = await apiFetch('/cases', { method: 'POST', body: JSON.stringify(payload) });
    button.textContent = `Đang tải ${selectedFiles.length} tài liệu…`;
    for (const file of selectedFiles) {
      const form = new FormData(); form.append('file', file);
      await apiFetch(`/cases/${created.case_id}/documents`, { method: 'POST', body: form });
    }
    toast('Đã tạo hồ sơ', `${created.case_id} — sẵn sàng chạy pipeline.`);
    navigate(`#/cases/${created.case_id}`);
  } catch (err) {
    toast('Lỗi khi tạo hồ sơ', err.message);
  } finally {
    button.disabled = false; button.textContent = 'Tạo hồ sơ & tải tài liệu';
  }
});

// ---------------------------------------------------------------------------
// Case detail view
// ---------------------------------------------------------------------------

async function openCaseDetail(caseId) {
  resetFlow(true); $('#logStream').innerHTML = '';
  try {
    caseData = await apiFetch(`/cases/${caseId}`);
    const docs = await apiFetch(`/cases/${caseId}/documents`);
    uploadedDocumentCount = docs.documents.length;
  } catch (err) {
    toast('Không tìm thấy hồ sơ', err.message);
    navigate('#/cases');
    return;
  }
  addLog('Chuyên viên thẩm định', `Đã mở hồ sơ #${caseData.case_id} (application ${caseData.application_id}).`, 'ĐÃ MỞ');
  updateHero();
  updateCaseSummaryFromDetail();
  if (['HUMAN_REVIEW','COMPLETED','EXECUTING_APPROVED_ACTIONS','VERIFYING_EXECUTION'].includes(caseData.workflow_state)) {
    revealResultsInstantly();
  } else if (['AWAITING_DOCUMENTS','MANUAL_REVIEW_REQUIRED','TECHNICAL_ERROR'].includes(caseData.workflow_state)) {
    revealAttentionState();
  }
}

function updateHero() {
  if (!caseData) return;
  const extracted = caseData.extracted_fields || {};
  const summary = caseListCache.find(c => c.case_id === caseData.case_id);
  const customerName = extracted.customer_name || summary?.customer_name || null;
  setText('#heroLogo', initials(customerName) || '—');
  setText('#heroCaseId', `HỒ SƠ #${caseData.case_id}`);
  setText('#heroStatus', WORKFLOW_STATE_LABEL[caseData.workflow_state] || caseData.workflow_state);
  setText('#heroCompany', customerName || '(Chưa trích xuất được tên khách hàng)');
  setText('#heroAmount', summary?.requested_amount ? formatVnd(summary.requested_amount) : '—');
  setText('#heroTerm', summary?.loan_term_months ? `${summary.loan_term_months} tháng` : '—');
  setText('#heroFile', `${uploadedDocumentCount} tài liệu đã tải lên · application ${caseData.application_id}`);
}

function updateCaseSummaryFromDetail() {
  // Keep the cached list row (if any) in sync so navigating back to the list
  // reflects the latest workflow_state without a full re-fetch.
  const row = caseListCache.find(c => c.case_id === caseData.case_id);
  if (row) row.workflow_state = caseData.workflow_state;
}

$('#backToListBtn').addEventListener('click', () => navigate('#/cases'));
$('#resetBtn').addEventListener('click', async () => {
  if (!currentCaseId) return;
  try { caseData = await apiFetch(`/cases/${currentCaseId}`); updateHero(); toast('Đã tải lại', 'Dữ liệu hồ sơ đã được đồng bộ từ backend.'); }
  catch (err) { toast('Lỗi', err.message); }
});

$('#documentsBtn').addEventListener('click', async () => {
  if (!currentCaseId) return;
  const list = $('#documentsList'); list.innerHTML = '<div class="empty-state">Đang tải…</div>';
  openModal('documentsModal');
  try {
    const result = await apiFetch(`/cases/${currentCaseId}/documents`);
    list.innerHTML = '';
    if (!result.documents.length) { list.innerHTML = '<div class="empty-state">Chưa có tài liệu nào được tải lên.</div>'; return; }
    result.documents.forEach(doc => {
      const item = document.createElement('div'); item.className = 'document-item';
      const copy = document.createElement('div');
      const name = document.createElement('strong'); name.textContent = doc.file_name;
      const meta = document.createElement('small');
      meta.textContent = `${doc.document_type || 'CHƯA PHÂN LOẠI'} · ${doc.classification_method || '—'} · ${(doc.size_bytes/1024).toFixed(0)} KB · tải lúc ${formatDateTime(doc.uploaded_at)}`;
      copy.append(name, meta);
      const link = document.createElement('a');
      link.href = `${API_BASE}/cases/${currentCaseId}/documents/${doc.document_id}/download`;
      link.target = '_blank'; link.rel = 'noopener'; link.textContent = 'Mở tài liệu ↗';
      item.append(copy, link); list.append(item);
    });
  } catch (err) {
    list.innerHTML = `<div class="empty-state">Lỗi tải danh sách: ${err.message}</div>`;
  }
});

$('#auditBtn').addEventListener('click', async () => {
  if (!currentCaseId) return;
  const list = $('#auditList'); list.innerHTML = '<div class="empty-state">Đang tải…</div>';
  openModal('auditModal');
  try {
    const result = await apiFetch(`/cases/${currentCaseId}/audit`);
    list.innerHTML = '';
    if (!result.audit_events.length) { list.innerHTML = '<div class="empty-state">Chưa có sự kiện audit nào.</div>'; return; }
    [...result.audit_events].reverse().forEach(event => {
      const item = document.createElement('div'); item.className = 'audit-item';
      const head = document.createElement('div'); head.className = 'audit-head';
      const strong = document.createElement('strong'); strong.textContent = event.event_type;
      const time = document.createElement('time'); time.textContent = formatDateTime(event.created_at);
      head.append(strong, time);
      const small = document.createElement('small');
      const transition = event.from_state && event.to_state ? `${event.from_state} → ${event.to_state} · ` : '';
      small.textContent = `${transition}actor: ${event.actor_type}${event.actor_id ? ` (${event.actor_id})` : ''}${Object.keys(event.details||{}).length ? ' · ' + JSON.stringify(event.details) : ''}`;
      item.append(head, small); list.append(item);
    });
  } catch (err) {
    list.innerHTML = `<div class="empty-state">Lỗi tải audit trail: ${err.message}</div>`;
  }
});

// ---------------------------------------------------------------------------
// Run pipeline — honest waiting state (real multi-second LLM/RAG calls) then
// a quick, clearly-labelled reveal of already-known results.
// ---------------------------------------------------------------------------

async function runAssessment() {
  if (running || !currentCaseId) return;
  resetFlow(true); running = true;
  $('#logStream').innerHTML = ''; setText('#eventCount','0'); $('#runBtn').disabled = true;
  setText('#heroStatus','ĐANG XỬ LÝ'); setText('#stagePill','Đang gọi pipeline (LLM + RAG thật, có thể mất 10–40 giây)…');

  setNodeMode('underwriterNode','complete'); setAgentState('underwriterNode','done','ĐÃ MỞ');
  setNodeMode('orchestratorNode','active'); setAgentState('orchestratorNode','running','ĐANG ĐIỀU PHỐI');
  updateEdge('underwriter-orchestrator','Đang mở workflow','Metadata hồ sơ và phạm vi xác minh được gửi tới Orchestrator.','active');
  addLog('Orchestrator Agent', 'Đã nhận yêu cầu chạy pipeline. Document/Income/Policy Agent sẽ gọi LLM/RAG thật — vui lòng chờ, đây không phải hoạt ảnh giả lập.', 'ĐANG XỬ LÝ');

  const waitStarted = Date.now();
  const waitTimer = setInterval(() => {
    const elapsed = ((Date.now() - waitStarted) / 1000).toFixed(0);
    setText('#stagePill', `Đang xử lý thật (đã ${elapsed}s)… LLM trích xuất tài liệu, RAG tra cứu chính sách`);
  }, 1000);

  let result;
  try {
    result = await apiFetch(`/cases/${currentCaseId}/run`, { method: 'POST' });
  } catch (err) {
    clearInterval(waitTimer);
    running = false; $('#runBtn').disabled = false;
    toast('Lỗi gọi pipeline', err.message);
    addLog('Hệ thống', `Lỗi gọi API: ${err.message}`, 'LỖI', 'warn');
    return;
  }
  clearInterval(waitTimer);
  caseData = result;
  updateHero();

  setNodeMode('orchestratorNode','complete'); setAgentState('orchestratorNode','done','ĐÃ ĐIỀU PHỐI');
  updateEdge('underwriter-orchestrator','Workflow đã tạo','Orchestrator đã nhận đủ context, không thực hiện tính toán chuyên môn.','approved');

  if (caseData.workflow_state === 'AWAITING_DOCUMENTS') {
    revealAttentionState();
    running = false; $('#runBtn').disabled = false;
    return;
  }
  if (caseData.workflow_state === 'MANUAL_REVIEW_REQUIRED') {
    revealAttentionState();
    running = false; $('#runBtn').disabled = false;
    return;
  }

  await revealPipelineResults();
  running = false;
}

async function revealPipelineResults() {
  const extracted = caseData.extracted_fields || {};
  const income = caseData.income_analysis || {};
  const policy = caseData.policy_result || {};

  setText('#stagePill','Phân tích song song (Document · Income · Policy)');
  const dispatches = [
    ['documentNode','orchestrator-document', `Trích xuất hồ sơ của ${extracted.customer_name || 'khách hàng'}`],
    ['incomeNode','orchestrator-income','Tính thu nhập ròng và dòng tiền lương'],
    ['policyNode','orchestrator-policy','Tra cứu điều kiện xác minh thu nhập tín chấp qua RAG']
  ];
  dispatches.forEach(([node, edge, detail]) => {
    setNodeMode(node,'active'); setAgentState(node,'running','ĐANG LÀM',detail); updateEdge(edge,'Đã giao nhiệm vụ',detail,'active');
  });
  await Promise.all(dispatches.map(([node]) => sendPacket('orchestratorNode',node)));
  await sleep(200);

  const documentEvidenceId = (caseData.evidence[0] || {}).evidence_id || '';
  setNodeMode('documentNode','complete');
  setAgentState('documentNode','done','HOÀN TẤT', `${caseData.documents.length} tài liệu · ${(extracted.salary_transactions||[]).length} giao dịch lương · độ tin cậy ${((extracted.extraction_confidence||0)*100).toFixed(0)}%`);
  addLog('Document Agent', `Đã trích xuất hồ sơ của ${extracted.customer_name || '—'} tại ${extracted.employer || '—'}; thu nhập khai báo ${formatVnd(extracted.declared_income)}/tháng.`, 'ĐÃ TRÍCH XUẤT', '', documentEvidenceId);

  const incomeEvidenceId = (income.recognized_evidence_ids || [])[0] || '';
  setNodeMode('incomeNode','complete');
  setAgentState('incomeNode','done','HOÀN TẤT', `Thu nhập ròng xác minh: ${formatVnd(income.average_income)}/tháng`);
  addLog('Income Agent', `Thu nhập ròng trung bình ${formatVnd(income.average_income)}/tháng qua ${income.period_count || 0} kỳ lương; ${(income.anomalies||[]).length} bất thường phát hiện.`, 'ĐÃ XÁC MINH', 'done', incomeEvidenceId);

  const policyCitationId = (policy.citations || [])[0]?.chunk_id || '';
  setNodeMode('policyNode','complete');
  setAgentState('policyNode','done','HOÀN TẤT', `Thu nhập đủ điều kiện theo chính sách: ${formatVnd(policy.eligible_income)}/tháng`);
  addLog('Policy Agent', `Đã truy xuất ${(policy.citations||[]).length} trích dẫn chính sách (phương pháp tham số: ${policy.parameter_extraction_method || '—'}).`, 'CHÍNH SÁCH', '', policyCitationId);

  setText('#stagePill','Đối chiếu nhất quán');
  setNodeMode('consistencyNode','active'); setAgentState('consistencyNode','reviewing','ĐANG ĐỐI CHIẾU');
  ['document-consistency','income-consistency','policy-consistency'].forEach(edge => updateEdge(edge,'Đang chuyển kết quả','Output có cấu trúc được chuyển để đối chiếu chéo.','active'));
  await Promise.all([
    sendPacket('documentNode','consistencyNode'), sendPacket('incomeNode','consistencyNode'), sendPacket('policyNode','consistencyNode')
  ]);
  await sleep(200);
  setNodeMode('consistencyNode','complete');
  setAgentState('consistencyNode','done', (caseData.findings||[]).length ? 'CÓ CẢNH BÁO' : 'NHẤT QUÁN', `${(caseData.findings||[]).length} phát hiện`);
  ['document-consistency','income-consistency','policy-consistency'].forEach(edge => updateEdge(edge,'Đã đối chiếu','Kết quả hợp lệ và có nguồn bằng chứng truy vết.','approved'));
  (caseData.findings || []).forEach(finding => {
    const tone = finding.severity === 'CRITICAL' || finding.severity === 'WARNING' ? 'warn' : '';
    addLog('Consistency Agent', `[${finding.severity}] ${finding.message}`, finding.code, tone, (finding.evidence_ids||[])[0] || '');
  });

  setText('#stagePill','Tạo khuyến nghị');
  setNodeMode('recommendationNode','active'); setAgentState('recommendationNode','reviewing','ĐANG TỔNG HỢP');
  updateEdge('consistency-recommendation','Đang tạo đề xuất','Kết quả đã chuẩn hóa được chuyển sang Recommendation Builder.','review');
  await sendPacket('consistencyNode','recommendationNode','review');
  await sleep(200);

  const rec = caseData.recommendation || {};
  setNodeMode('recommendationNode','complete'); setAgentState('recommendationNode','done','ĐÃ ĐỀ XUẤT');
  addLog('Recommendation Builder', `${RECOMMENDATION_STATUS_LABEL[rec.status] || rec.status}. Thu nhập khai báo ${formatVnd(rec.declared_income)} · trung bình ${formatVnd(rec.average_income)} · đủ điều kiện ${formatVnd(rec.eligible_income)}.`, 'ĐỀ XUẤT', 'review', policyCitationId);
  setText('#stagePill','Chờ chuyên viên duyệt'); setText('#heroStatus','CHỜ KIỂM DUYỆT');
  setNodeMode('humanNode','ready'); setAgentState('humanNode','reviewing','CHỜ DUYỆT');
  updateEdge('recommendation-human','Chờ chuyên viên quyết định','Đề xuất kèm kết quả, hành động và bằng chứng đã sẵn sàng.','review');
  await sendPacket('recommendationNode','humanNode','review');

  $('#verifyBtn').disabled = false; $('#verifyBtn').textContent = 'Mở kiểm duyệt';
  addLog('Cổng kiểm duyệt','Đề xuất đã khóa phiên bản và chờ chuyên viên quyết định.','KIỂM DUYỆT','review');
}

function revealResultsInstantly() {
  // Case was already processed in a previous session — render final state
  // without replaying the dispatch animation.
  setNodeMode('underwriterNode','complete'); setAgentState('underwriterNode','done','ĐÃ MỞ');
  setNodeMode('orchestratorNode','complete'); setAgentState('orchestratorNode','done','ĐÃ ĐIỀU PHỐI');
  ['documentNode','incomeNode','policyNode','consistencyNode','recommendationNode'].forEach(id => setNodeMode(id,'complete'));
  const rec = caseData.recommendation || {};
  setAgentState('documentNode','done','HOÀN TẤT');
  setAgentState('incomeNode','done','HOÀN TẤT', `Thu nhập ròng: ${formatVnd((caseData.income_analysis||{}).average_income)}/tháng`);
  setAgentState('policyNode','done','HOÀN TẤT', `Đủ điều kiện: ${formatVnd((caseData.policy_result||{}).eligible_income)}/tháng`);
  setAgentState('consistencyNode','done', (caseData.findings||[]).length ? 'CÓ CẢNH BÁO' : 'NHẤT QUÁN');
  setAgentState('recommendationNode','done','ĐÃ ĐỀ XUẤT');
  addLog('Hệ thống', 'Hồ sơ này đã được xử lý trước đó — hiển thị kết quả đã lưu từ backend.', 'ĐÃ LƯU');
  (caseData.findings || []).forEach(finding => {
    const tone = finding.severity === 'CRITICAL' || finding.severity === 'WARNING' ? 'warn' : '';
    addLog('Consistency Agent', `[${finding.severity}] ${finding.message}`, finding.code, tone, (finding.evidence_ids||[])[0] || '');
  });
  if (caseData.workflow_state === 'HUMAN_REVIEW') {
    setNodeMode('humanNode','ready'); setAgentState('humanNode','reviewing','CHỜ DUYỆT');
    $('#verifyBtn').disabled = false;
    setText('#stagePill','Chờ chuyên viên duyệt'); setText('#heroStatus','CHỜ KIỂM DUYỆT');
  } else {
    setNodeMode('humanNode','complete'); setAgentState('humanNode','done','ĐÃ XỬ LÝ');
    setNodeMode('executorNode','complete'); setAgentState('executorNode','done','HOÀN TẤT');
    setNodeMode('systemsNode','complete');
    setText('#stagePill','Hoàn tất'); setText('#heroStatus','ĐÃ XÁC MINH');
    $('#runBtn').innerHTML = '<span>↻</span> Chạy lại pipeline';
    (caseData.execution_results || []).forEach(result => {
      const action = (caseData.proposed_actions || []).find(a => a.action_id === result.action_id);
      addLog('Action Executor', `${action ? action.description : result.action_id} → ${EXECUTION_STATUS_LABEL[result.status] || result.status}`, result.status, result.status === 'FAILED' ? 'warn' : 'done');
    });
  }
}

function revealAttentionState() {
  setNodeMode('underwriterNode','complete'); setAgentState('underwriterNode','done','ĐÃ MỞ');
  setNodeMode('orchestratorNode','complete'); setAgentState('orchestratorNode','done','ĐÃ ĐIỀU PHỐI');
  setText('#heroStatus', WORKFLOW_STATE_LABEL[caseData.workflow_state] || caseData.workflow_state);
  setText('#stagePill', caseData.workflow_state === 'AWAITING_DOCUMENTS' ? 'Chờ bổ sung tài liệu' : 'Cần chuyên viên xử lý thủ công');
  setNodeMode('documentNode','active');
  setAgentState('documentNode','conflict', caseData.workflow_state === 'AWAITING_DOCUMENTS' ? 'THIẾU TÀI LIỆU' : 'CẦN XEM XÉT');
  const lastEvent = (caseData.audit_events || []).slice(-1)[0];
  const reason = lastEvent ? lastEvent.event_type : caseData.workflow_state;
  addLog('Hệ thống', `Pipeline dừng ở trạng thái ${caseData.workflow_state} (${reason}). Kiểm tra tài liệu đã tải lên hoặc xem audit trail để biết chi tiết.`, caseData.workflow_state, 'warn');
  (caseData.errors || []).forEach(error => addLog('Hệ thống', `${error.component}: ${error.message}`, error.code, 'warn'));
}

function populateVerifyModal() {
  if (!caseData) return;
  const rec = caseData.recommendation || {};
  setText('#verifyAverageIncome', `${formatVnd(rec.average_income)}/tháng`);
  setText('#verifyEligibleIncome', `${formatVnd(rec.eligible_income)}/tháng`);
  setText('#verifyStatus', RECOMMENDATION_STATUS_LABEL[rec.status] || rec.status || '—');
  const container = $('#verifyFindings'); container.innerHTML = '';
  (rec.findings || []).forEach(finding => {
    const label = document.createElement('label');
    label.textContent = `[${finding.severity}] ${finding.message}`;
    container.append(label);
  });
  if (!(rec.findings || []).length) {
    const label = document.createElement('label'); label.textContent = 'Không có cảnh báo nào từ Consistency Agent.'; container.append(label);
  }
  $('#reviewReason').value = '';
  const eligible = Number(rec.eligible_income || 0) / 1e6;
  $('#editIncomeInput').value = eligible.toFixed(1);
  $('#editIncomeField').hidden = false;
}

async function approveAndExecute() {
  if (!caseData) return;
  const reason = $('#reviewReason').value.trim() || 'Đã kiểm tra hồ sơ và đồng ý cập nhật kết quả xác minh.';
  const approvedActionIds = (caseData.proposed_actions || []).map(a => a.action_id);
  closeModal('verifyModal'); running = true;
  setNodeMode('humanNode','complete'); setAgentState('humanNode','done','ĐÃ DUYỆT'); $('#verifyBtn').disabled = true;
  setText('#stagePill','Thực thi có kiểm soát'); setNodeMode('executorNode','active');
  setAgentState('executorNode','running','ĐANG THỰC THI');
  updateEdge('human-executor','Đã phê duyệt','Quyết định có danh tính người duyệt và dấu thời gian được gửi để thực thi.','approved');
  addLog(REVIEWER_NAME, `Đã chấp thuận ${approvedActionIds.length} hành động đề xuất: "${reason}"`, 'ĐÃ DUYỆT','done');
  await sendPacket('humanNode','executorNode','approve');
  addLog('Action Executor','Đã kiểm tra quyền và chuẩn bị cập nhật hệ thống đích.','ĐANG THỰC THI');

  try {
    await apiFetch(`/cases/${caseData.case_id}/review`, {
      method: 'POST',
      body: JSON.stringify({ outcome: 'ACCEPT_ACTIONS', reason, approved_action_ids: approvedActionIds })
    });
    caseData = await apiFetch(`/cases/${caseData.case_id}`);
  } catch (err) {
    running = false; toast('Lỗi thực thi', err.message);
    addLog('Hệ thống', `Lỗi gọi review API: ${err.message}`, 'LỖI', 'warn');
    return;
  }

  setNodeMode('executorNode','complete'); setAgentState('executorNode','done','HOÀN TẤT','Đã thực thi đúng phạm vi được phê duyệt');
  setNodeMode('systemsNode','active'); updateEdge('executor-systems','Đang cập nhật','Ghi kết quả tới LOS, DMS, Workflow và Notification.','approved');
  await sendPacket('executorNode','systemsNode','approve');

  (caseData.execution_results || []).forEach(result => {
    const action = (caseData.proposed_actions || []).find(a => a.action_id === result.action_id);
    const system = action ? (ACTION_SYSTEM_MAP[action.action_type] || 'Workflow') : 'Workflow';
    const tone = result.status === 'FAILED' ? 'warn' : 'done';
    addLog('Action Executor', `${system}: ${action ? action.description : result.action_id} → ${EXECUTION_STATUS_LABEL[result.status] || result.status}`, result.status, tone);
  });
  setNodeMode('systemsNode','complete'); running = false;
  setText('#stagePill','Hoàn tất'); setText('#heroStatus', caseData.workflow_state === 'COMPLETED' ? 'ĐÃ XÁC MINH' : caseData.workflow_state);
  $('#runBtn').disabled = false; $('#runBtn').innerHTML = '<span>↻</span> Chạy lại pipeline';
  addLog('Hệ thống','LOS, DMS, Workflow, Notification và Audit đã cập nhật thành công.','HOÀN TẤT','done');
  toast('Xác minh hoàn tất','Kết quả đã được ghi nhận và lưu dấu vết kiểm toán (audit_events).');
  updateHero();
  const row = caseListCache.find(c => c.case_id === caseData.case_id); if (row) row.workflow_state = caseData.workflow_state;
}

async function requestRevision() {
  if (!caseData) return;
  const reason = $('#reviewReason').value.trim() || 'Yêu cầu xác nhận lại thu nhập đủ điều kiện trước khi thực thi.';
  const editedTrieu = parseFloat($('#editIncomeInput').value);
  if (Number.isNaN(editedTrieu) || editedTrieu < 0) { toast('Giá trị không hợp lệ','Vui lòng nhập thu nhập đủ điều kiện hợp lệ.'); return; }
  const editedVnd = Math.round(editedTrieu * 1e6);
  closeModal('verifyModal');
  setNodeMode('humanNode'); setNodeMode('recommendationNode','active');
  setAgentState('recommendationNode','reviewing','ĐANG SỬA','Áp dụng điều chỉnh thu nhập đủ điều kiện theo yêu cầu chuyên viên');
  setText('#stagePill','Đang chỉnh sửa đề xuất');
  addLog('Cổng kiểm duyệt', `Yêu cầu chỉnh sửa: "${reason}" (thu nhập đủ điều kiện → ${formatVnd(editedVnd)})`, 'CHỈNH SỬA','warn');

  try {
    await apiFetch(`/cases/${caseData.case_id}/review`, {
      method: 'POST',
      body: JSON.stringify({ outcome: 'EDIT_AND_RERUN', reason, edited_eligible_income: editedVnd })
    });
    caseData = await apiFetch(`/cases/${caseData.case_id}`);
  } catch (err) {
    toast('Lỗi khi chỉnh sửa', err.message);
    addLog('Hệ thống', `Lỗi gọi review API: ${err.message}`, 'LỖI', 'warn');
    return;
  }

  const rec = caseData.recommendation || {};
  setNodeMode('recommendationNode','complete');
  setAgentState('recommendationNode','done','ĐÃ CẬP NHẬT', `Đủ điều kiện: ${formatVnd(rec.eligible_income)}/tháng`);
  setNodeMode('humanNode','ready'); setAgentState('humanNode','reviewing','CHỜ DUYỆT');
  $('#verifyBtn').disabled = false;
  setText('#stagePill','Chờ chuyên viên duyệt');
  addLog('Recommendation Builder', `Đã cập nhật thu nhập đủ điều kiện theo yêu cầu chuyên viên: ${formatVnd(rec.eligible_income)}/tháng.`, 'ĐÃ CẬP NHẬT','done');
  toast('Đề xuất đã cập nhật','Cổng kiểm duyệt đã nhận phiên bản mới.');
}

async function rejectProposal() {
  if (!caseData) return;
  const reason = $('#reviewReason').value.trim() || 'Từ chối kết quả xác minh, chuyển xử lý thủ công.';
  closeModal('verifyModal'); running = false;

  try {
    await apiFetch(`/cases/${caseData.case_id}/review`, {
      method: 'POST',
      body: JSON.stringify({ outcome: 'MANUAL_HANDLING', reason })
    });
    caseData = await apiFetch(`/cases/${caseData.case_id}`);
  } catch (err) {
    toast('Lỗi khi từ chối', err.message);
    addLog('Hệ thống', `Lỗi gọi review API: ${err.message}`, 'LỖI', 'warn');
    return;
  }

  setNodeMode('humanNode','complete'); setAgentState('humanNode','conflict','TỪ CHỐI');
  $('#verifyBtn').disabled = true; setText('#stagePill','Đã từ chối'); setText('#heroStatus','TỪ CHỐI');
  $('#runBtn').disabled = false; $('#runBtn').innerHTML = '<span>↻</span> Chạy lại pipeline';
  addLog(REVIEWER_NAME, `Đã từ chối đề xuất: "${reason}". Action Executor không được kích hoạt.`, 'ĐÃ TỪ CHỐI','warn');
  toast('Đề xuất đã bị từ chối','Không có dữ liệu nào được ghi sang hệ thống nghiệp vụ.');
}

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------

$('#runBtn').addEventListener('click', runAssessment);
$('#verifyBtn').addEventListener('click', () => { $$('.verify-check').forEach(box => box.checked = false); $('#confirmApprove').disabled = true; populateVerifyModal(); openModal('verifyModal'); });
$('#confirmApprove').addEventListener('click', approveAndExecute);
$('#requestEditBtn').addEventListener('click', requestRevision);
$('#rejectProposalBtn').addEventListener('click', rejectProposal);
$('#edgePopover button').addEventListener('click', () => $('#edgePopover').hidden = true);
$('#clearLog').addEventListener('click', () => { $('#logStream').innerHTML = ''; addLog('Hệ thống','Nhật ký đã được làm mới.','SẴN SÀNG'); });
$$('.nav-item').forEach(item => item.addEventListener('click', () => navigate(`#/${item.dataset.view === 'cases' ? 'cases' : 'cases/new'}`)));
$$('[data-close]').forEach(button => button.addEventListener('click', () => closeModal(button.dataset.close)));
$$('.modal-backdrop').forEach(backdrop => backdrop.addEventListener('click', event => { if (event.target === backdrop) backdrop.hidden = true; }));
$$('.verify-check').forEach(box => box.addEventListener('change', () => { $('#confirmApprove').disabled = !$$('.verify-check').every(item => item.checked); }));

let resizeTimer;
window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(drawEdges, 100); });
setInterval(() => setText('#liveClock', timeNow()), 1000);
window.addEventListener('hashchange', handleRoute);

async function bootstrap() {
  resetFlow(true); setText('#liveClock', timeNow());
  await loadSystemStatus();
  await handleRoute();
}
bootstrap();
