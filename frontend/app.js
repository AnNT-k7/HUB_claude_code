const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const setText = (selector, value, root = document) => { const node = $(selector, root); if (node) node.textContent = value; };

const DEFAULT_API_BASE = window.location.port === '3100'
  ? 'http://127.0.0.1:8100/api/v1'
  : 'http://localhost:8000/api/v1';
const API_BASE = window.localStorage.getItem('iv_api_base') || DEFAULT_API_BASE;
const REVIEWER_ID = 'LT-01';
const REVIEWER_NAME = 'Linh Trần';

const flowNodes = ['underwriterNode','orchestratorNode','documentNode','incomeNode','policyNode','consistencyNode','recommendationNode','humanNode','executorNode','systemsNode'];
const pipelineSequence = [['recommendationNode', 'humanNode'], ['humanNode', 'executorNode']];
const edgeData = new Map();
let phase = 'idle';
let runToken = 0;
let running = false;
let caseData = null;
let selectedCase = null;
let caseList = [];

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

async function apiFetch(path, options = {}) {
  const isMultipart = options.body instanceof FormData;
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(isMultipart ? {} : { 'Content-Type': 'application/json' }),
      'X-Role': 'UNDERWRITER',
      'X-Reviewer-Id': REVIEWER_ID,
      ...(options.headers || {})
    }
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = Array.isArray(body.detail) ? body.detail.map(item => item.msg).join('; ') : (body.detail || detail);
    } catch (_) { /* no body */ }
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

function timeNow() {
  return new Date().toLocaleTimeString('vi-VN', { hour12:false });
}

function toast(title, detail) {
  const item = document.createElement('div'); item.className = 'toast';
  const strong = document.createElement('strong'); strong.textContent = title;
  const small = document.createElement('small'); small.textContent = detail;
  item.append(strong, small); $('#toastStack').append(item);
  setTimeout(() => item.remove(), 3600);
}

function addLog(source, message, tag = 'INFO', tone = '', evidenceKey = '') {
  const stream = $('#logStream');
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
  node.classList.toggle('is-revealed', ['ready','active','complete'].includes(mode));
  node.classList.toggle('is-ready', mode === 'ready');
  node.classList.toggle('is-active', mode === 'active');
  node.classList.toggle('is-complete', mode === 'complete');
  schedulePipelineConnections();
}

function renderPipelineConnections() { drawEdges(); }
function schedulePipelineConnections() { requestAnimationFrame(renderPipelineConnections); }

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

function sendPacket(fromId, toId, tone = '', duration = 800) {
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
  runToken += 1; running = false; phase = 'idle';
  flowNodes.forEach(id => setNodeMode(id));
  setNodeMode('underwriterNode','ready');
  setAgentState('underwriterNode','idle','SẴN SÀNG','Mở hồ sơ và xác nhận dữ liệu đầu vào');
  setAgentState('orchestratorNode','locked','CHỜ','Điều phối state · task · retry · routing, không ghi dữ liệu');
  setAgentState('documentNode','locked','CHỜ','Đọc và trích xuất tài liệu');
  setAgentState('incomeNode','locked','CHỜ','Phân tích tiền lương và dòng tiền');
  setAgentState('policyNode','locked','CHỜ','Tra cứu quy định tín chấp ngân hàng');
  setAgentState('consistencyNode','locked','CHỜ','Đối chiếu chéo, phát hiện thiếu và bất thường');
  setAgentState('recommendationNode','locked','CHỜ','Tạo kết quả xác minh và hành động đề xuất');
  setAgentState('humanNode','locked','CHỜ');
  setAgentState('executorNode','locked','KHÓA','Chờ quyết định của chuyên viên');
  $('#verifyBtn').disabled = true; $('#verifyBtn').textContent = 'Mở kiểm duyệt';
  $('#runBtn').disabled = !selectedCase; $('#runBtn').innerHTML = '<span>✦</span> Chạy pipeline';
  setText('#stagePill','Sẵn sàng'); setText('#heroStatus','SẴN SÀNG');
  resetEdgeData(); $('#edgePopover').hidden = true; drawEdges();
  if (!silent) {
    $('#logStream').innerHTML = '';
    addLog('Hệ thống','Luồng xử lý đã sẵn sàng cho hồ sơ xác minh thu nhập.','SẴN SÀNG');
  }
}

function validRun(token) { return token === runToken; }

function updateCaseSummary() {
  setText('#totalCases', caseList.length);
  setText('#caseCount', caseList.length);
  setText('#caseWorkflowState', caseData?.workflow_state || selectedCase?.pipeline_status || '—');
  setText('#caseAuditCount', (caseData?.audit_events || []).length);
  renderCaseRows($('#caseSearch')?.value || '');
}

function initials(name = '') {
  return name.trim().split(/\s+/).slice(-2).map(part => part[0]).join('').toUpperCase() || 'IV';
}

function renderCaseRows(query = '') {
  const rows = $('#caseRows'); if (!rows) return;
  rows.innerHTML = '';
  const normalized = query.trim().toLocaleLowerCase('vi');
  const filtered = caseList.filter(item => !normalized || [item.customer_name,item.id,item.application_id,item.company].join(' ').toLocaleLowerCase('vi').includes(normalized));
  if (!filtered.length) {
    const empty = document.createElement('div'); empty.className = 'empty-cases';
    empty.textContent = caseList.length ? 'Không tìm thấy hồ sơ phù hợp.' : 'Chưa có hồ sơ. Nhấn “Tạo hồ sơ mới” để bắt đầu.';
    rows.append(empty); return;
  }
  filtered.forEach(item => {
    const row = document.createElement('div'); row.className = 'table-row';
    const caseCell = document.createElement('div'); caseCell.className = 'case-cell';
    const logo = document.createElement('div'); logo.className = 'company-logo'; logo.textContent = initials(item.customer_name);
    const copy = document.createElement('div'); const name = document.createElement('strong'); name.textContent = item.customer_name;
    const meta = document.createElement('small'); meta.textContent = `#${item.id} · ${item.application_id}`; copy.append(name,meta); caseCell.append(logo,copy);
    const amount = document.createElement('strong'); amount.textContent = formatVnd(item.requested_amount);
    const documents = document.createElement('span'); documents.textContent = `${item.document_count || 0} tài liệu`;
    const status = document.createElement('span'); status.className = `status-badge ${item.pipeline_status === 'HUMAN_REVIEW' ? 'review' : item.pipeline_status === 'OPEN_CASE' ? 'new' : ''}`; status.textContent = WORKFLOW_STATE_LABEL[item.pipeline_status] || item.pipeline_status;
    const open = document.createElement('button'); open.className = 'open-case'; open.textContent = 'Mở →';
    open.addEventListener('click', () => openCase(item.id));
    row.append(caseCell, amount, documents, status, open); rows.append(row);
  });
}

function updateHero() {
  if (!selectedCase) {
    setText('#heroCaseId','CHƯA CHỌN HỒ SƠ'); setText('#heroCompany','Tạo hoặc chọn một hồ sơ');
    setText('#heroAmount','—'); setText('#heroFile','Đính kèm tài liệu để chạy pipeline'); $('#runBtn').disabled = true; return;
  }
  setText('#heroLogo', initials(selectedCase.customer_name));
  setText('#heroCaseId', `HỒ SƠ #${selectedCase.id}`);
  setText('#heroCompany', selectedCase.customer_name);
  setText('#heroAmount', formatVnd(selectedCase.requested_amount));
  setText('#heroTerm', selectedCase.company);
  setText('#heroFile', `${selectedCase.document_count || 0} tài liệu · application ${selectedCase.application_id}`);
  setText('#heroStatus', WORKFLOW_STATE_LABEL[caseData?.workflow_state || selectedCase.pipeline_status] || selectedCase.pipeline_status);
  $('#runBtn').disabled = (selectedCase.document_count || 0) < 1;
}

async function loadCases() {
  const payload = await apiFetch('/cases');
  caseList = payload.items || [];
  setText('#caseTableStatus', `${caseList.length} hồ sơ · cập nhật trực tiếp`);
  updateCaseSummary();
  return caseList;
}

async function openCase(caseId) {
  const detail = await apiFetch(`/cases/${caseId}`);
  selectedCase = detail;
  caseData = detail.context || null;
  resetFlow(true); updateHero(); updateCaseSummary(); switchView('command');
  if (caseData) hydrateCompletedContext();
}

function hydrateCompletedContext() {
  if (!caseData) return;
  const terminal = caseData.workflow_state === 'COMPLETED';
  ['underwriterNode','orchestratorNode','documentNode','incomeNode','policyNode','consistencyNode','recommendationNode'].forEach(id => setNodeMode(id,'complete'));
  setNodeMode('humanNode', terminal ? 'complete' : 'ready');
  setNodeMode('executorNode', terminal ? 'complete' : 'locked');
  setNodeMode('systemsNode', terminal ? 'complete' : 'locked');
  $('#verifyBtn').disabled = caseData.workflow_state !== 'HUMAN_REVIEW';
  setText('#stagePill', WORKFLOW_STATE_LABEL[caseData.workflow_state] || caseData.workflow_state);
}

async function runAssessment() {
  if (running || !selectedCase) return;
  resetFlow(true); const token = runToken; running = true; phase = 'underwriter';
  $('#logStream').innerHTML = ''; setText('#eventCount','0'); $('#runBtn').disabled = true;
  setText('#heroStatus','ĐANG XÁC MINH'); setText('#stagePill','Tiếp nhận hồ sơ');

  setNodeMode('underwriterNode','active'); setAgentState('underwriterNode','running','ĐANG MỞ','Đang kiểm tra dữ liệu đầu vào');
  addLog('Chuyên viên thẩm định', `Đã mở hồ sơ #${selectedCase.id} (application ${selectedCase.application_id}) và xác nhận bộ chứng từ đầu vào.`, 'ĐÃ MỞ');
  await sleep(500); if (!validRun(token)) return;
  setNodeMode('underwriterNode','complete'); setAgentState('underwriterNode','done','ĐÃ XÁC NHẬN');
  phase = 'orchestrating'; setText('#stagePill','Lập workflow');
  setNodeMode('orchestratorNode','active'); setAgentState('orchestratorNode','running','ĐIỀU PHỐI');
  updateEdge('underwriter-orchestrator','Đang mở workflow','Metadata hồ sơ và phạm vi xác minh được gửi tới Orchestrator.','active');
  await sendPacket('underwriterNode','orchestratorNode'); if (!validRun(token)) return;

  try {
    caseData = await apiFetch(`/cases/${selectedCase.id}/run`, { method: 'POST' });
    selectedCase = await apiFetch(`/cases/${selectedCase.id}`);
  } catch (err) {
    running = false; $('#runBtn').disabled = false;
    toast('Không kết nối được backend', err.message);
    addLog('Hệ thống', `Lỗi gọi API: ${err.message}. Kiểm tra backend đang chạy tại ${API_BASE}.`, 'LỖI', 'warn');
    return;
  }

  addLog('Orchestrator Agent', `Đã tạo workflow ${caseData.case_id}; tách 3 tác vụ chuyên môn độc lập (Document, Income, Policy).`, 'ĐIỀU PHỐI');
  await sleep(700); if (!validRun(token)) return;
  setNodeMode('orchestratorNode','complete'); setAgentState('orchestratorNode','done','ĐÃ GIAO VIỆC','Theo dõi state, retry và timeout');
  updateEdge('underwriter-orchestrator','Workflow đã tạo','Orchestrator đã nhận đủ context, không thực hiện tính toán chuyên môn.','approved');

  phase = 'parallel'; setText('#stagePill','Phân tích song song');
  const extracted = caseData.extracted_fields || {};
  const income = caseData.income_analysis || {};
  const policy = caseData.policy_result || {};
  const dispatches = [
    ['documentNode','orchestrator-document', `Trích xuất hợp đồng, bảng lương và sao kê của ${extracted.customer_name || 'khách hàng'}`],
    ['incomeNode','orchestrator-income','Tính thu nhập ròng và dòng tiền lương'],
    ['policyNode','orchestrator-policy','Tra cứu điều kiện xác minh thu nhập tín chấp']
  ];
  dispatches.forEach(([node, edge, detail]) => {
    setNodeMode(node,'active'); setAgentState(node,'running','ĐANG LÀM',detail); updateEdge(edge,'Đã giao nhiệm vụ',detail,'active');
  });
  await Promise.all(dispatches.map(([node]) => sendPacket('orchestratorNode',node))); if (!validRun(token)) return;
  await sleep(1100); if (!validRun(token)) return;

  const documentEvidenceId = (caseData.evidence[0] || {}).evidence_id || '';
  setNodeMode('documentNode','complete');
  setAgentState('documentNode','done','HOÀN TẤT', `${caseData.documents.length} tài liệu · ${(extracted.salary_transactions||[]).length} giao dịch lương trích xuất`);
  addLog('Document Agent', `Đã trích xuất hồ sơ của ${extracted.customer_name || '—'} tại ${extracted.employer || '—'}; thu nhập khai báo ${formatVnd(extracted.declared_income)}/tháng.`, 'ĐÃ TRÍCH XUẤT', '', documentEvidenceId);

  const incomeEvidenceId = (income.recognized_evidence_ids || [])[0] || '';
  setNodeMode('incomeNode','complete');
  setAgentState('incomeNode','done','HOÀN TẤT', `Thu nhập ròng xác minh: ${formatVnd(income.average_income)}/tháng`);
  addLog('Income Agent', `Thu nhập ròng trung bình ${formatVnd(income.average_income)}/tháng qua ${income.period_count || 0} kỳ lương; ${(income.anomalies||[]).length} bất thường phát hiện.`, 'ĐÃ XÁC MINH', 'done', incomeEvidenceId);

  const policyCitationId = (policy.citations || [])[0]?.chunk_id || '';
  setNodeMode('policyNode','complete');
  setAgentState('policyNode','done','HOÀN TẤT', `Thu nhập đủ điều kiện theo chính sách: ${formatVnd(policy.eligible_income)}/tháng`);
  addLog('Policy Agent', `Đã truy xuất ${(policy.citations||[]).length} trích dẫn chính sách xác minh thu nhập áp dụng cho hồ sơ.`, 'CHÍNH SÁCH', '', policyCitationId);

  phase = 'consistency'; setText('#stagePill','Đối chiếu nhất quán');
  setNodeMode('consistencyNode','active'); setAgentState('consistencyNode','reviewing','ĐANG ĐỐI CHIẾU');
  [['documentNode','document-consistency'],['incomeNode','income-consistency'],['policyNode','policy-consistency']].forEach(([node,edge]) => updateEdge(edge,'Đang chuyển kết quả','Output có cấu trúc được chuyển để đối chiếu chéo.','active'));
  await Promise.all([
    sendPacket('documentNode','consistencyNode'), sendPacket('incomeNode','consistencyNode'), sendPacket('policyNode','consistencyNode')
  ]); if (!validRun(token)) return;

  addLog('Consistency Agent', `Đang kiểm tra chéo ${(caseData.findings||[]).length} phát hiện tiềm ẩn giữa 3 bộ kết quả.`, 'ĐỐI CHIẾU', 'review');
  await sleep(900); if (!validRun(token)) return;
  setNodeMode('consistencyNode','complete');
  setAgentState('consistencyNode','done', (caseData.findings||[]).length ? 'CÓ CẢNH BÁO' : 'NHẤT QUÁN', `${(caseData.findings||[]).length} phát hiện · không phát hiện thiếu hồ sơ nghiêm trọng`);
  ['document-consistency','income-consistency','policy-consistency'].forEach(edge => updateEdge(edge,'Đã đối chiếu','Kết quả hợp lệ và có nguồn bằng chứng truy vết.','approved'));
  (caseData.findings || []).forEach(finding => {
    const tone = finding.severity === 'CRITICAL' ? 'warn' : finding.severity === 'WARNING' ? 'warn' : '';
    addLog('Consistency Agent', `[${finding.severity}] ${finding.message}`, finding.code, tone, (finding.evidence_ids||[])[0] || '');
  });

  phase = 'recommendation'; setText('#stagePill','Tạo khuyến nghị');
  setNodeMode('recommendationNode','active'); setAgentState('recommendationNode','reviewing','ĐANG TỔNG HỢP');
  updateEdge('consistency-recommendation','Đang tạo đề xuất','Kết quả đã chuẩn hóa được chuyển sang Recommendation Builder.','review');
  await sendPacket('consistencyNode','recommendationNode','review'); if (!validRun(token)) return;
  await sleep(800); if (!validRun(token)) return;

  const rec = caseData.recommendation || {};
  setNodeMode('recommendationNode','complete'); setAgentState('recommendationNode','done','ĐÃ ĐỀ XUẤT');
  addLog('Recommendation Builder', `${RECOMMENDATION_STATUS_LABEL[rec.status] || rec.status}. Thu nhập khai báo ${formatVnd(rec.declared_income)} · trung bình ${formatVnd(rec.average_income)} · đủ điều kiện ${formatVnd(rec.eligible_income)}.`, 'ĐỀ XUẤT', 'review', policyCitationId);
  phase = 'human'; setText('#stagePill','Chờ chuyên viên duyệt'); setText('#heroStatus','CHỜ KIỂM DUYỆT');
  setNodeMode('humanNode','ready'); setAgentState('humanNode','reviewing','CHỜ DUYỆT');
  updateEdge('recommendation-human','Chờ chuyên viên quyết định','Đề xuất kèm kết quả, hành động và bằng chứng đã sẵn sàng.','review');
  await sendPacket('recommendationNode','humanNode','review'); if (!validRun(token)) return;

  running = false;
  $('#verifyBtn').disabled = false; $('#verifyBtn').textContent = 'Mở kiểm duyệt';
  addLog('Cổng kiểm duyệt','Đề xuất đã khóa phiên bản và chờ chuyên viên quyết định.','KIỂM DUYỆT','review');
  updateCaseSummary();
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
  closeModal('verifyModal'); phase = 'executing'; running = true; const token = runToken;
  setNodeMode('humanNode','complete'); setAgentState('humanNode','done','ĐÃ DUYỆT'); $('#verifyBtn').disabled = true;
  setText('#stagePill','Thực thi có kiểm soát'); setNodeMode('executorNode','active');
  setAgentState('executorNode','running','ĐANG THỰC THI');
  updateEdge('human-executor','Đã phê duyệt','Quyết định có danh tính người duyệt và dấu thời gian được gửi để thực thi.','approved');
  addLog(REVIEWER_NAME, `Đã chấp thuận ${approvedActionIds.length} hành động đề xuất: "${reason}"`, 'ĐÃ DUYỆT','done');
  await sendPacket('humanNode','executorNode','approve'); if (!validRun(token)) return;
  addLog('Action Executor','Đã kiểm tra quyền và chuẩn bị cập nhật hệ thống đích.','ĐANG THỰC THI');

  try {
    await apiFetch(`/income-verifications/${caseData.case_id}/review`, {
      method: 'POST',
      body: JSON.stringify({ outcome: 'ACCEPT_ACTIONS', reason, approved_action_ids: approvedActionIds })
    });
    caseData = await apiFetch(`/income-verifications/${caseData.case_id}`);
  } catch (err) {
    running = false; toast('Lỗi thực thi', err.message);
    addLog('Hệ thống', `Lỗi gọi review API: ${err.message}`, 'LỖI', 'warn');
    return;
  }
  await sleep(600); if (!validRun(token)) return;

  setNodeMode('executorNode','complete'); setAgentState('executorNode','done','HOÀN TẤT','Đã thực thi đúng phạm vi được phê duyệt');
  setNodeMode('systemsNode','active'); updateEdge('executor-systems','Đang cập nhật','Ghi kết quả tới LOS, DMS, Workflow và Notification.','approved');
  await sendPacket('executorNode','systemsNode','approve'); if (!validRun(token)) return;

  (caseData.execution_results || []).forEach(result => {
    const action = (caseData.proposed_actions || []).find(a => a.action_id === result.action_id);
    const system = action ? (ACTION_SYSTEM_MAP[action.action_type] || 'Workflow') : 'Workflow';
    const tone = result.status === 'FAILED' ? 'warn' : 'done';
    addLog('Action Executor', `${system}: ${action ? action.description : result.action_id} → ${EXECUTION_STATUS_LABEL[result.status] || result.status}`, result.status, tone);
  });
  await sleep(400); if (!validRun(token)) return;
  setNodeMode('systemsNode','complete'); phase = 'complete'; running = false;
  setText('#stagePill','Hoàn tất'); setText('#heroStatus', caseData.workflow_state === 'COMPLETED' ? 'ĐÃ XÁC MINH' : caseData.workflow_state);
  $('#runBtn').disabled = false; $('#runBtn').innerHTML = '<span>↻</span> Chạy lại xác minh';
  addLog('Hệ thống','LOS, DMS, Workflow, Notification và Audit đã cập nhật thành công.','HOÀN TẤT','done');
  toast('Xác minh hoàn tất','Kết quả đã được ghi nhận và lưu dấu vết kiểm toán (audit_events).');
  updateCaseSummary();
}

async function requestRevision() {
  if (!caseData) return;
  const reason = $('#reviewReason').value.trim() || 'Yêu cầu xác nhận lại thu nhập đủ điều kiện trước khi thực thi.';
  const editedTrieu = parseFloat($('#editIncomeInput').value);
  if (Number.isNaN(editedTrieu) || editedTrieu < 0) { toast('Giá trị không hợp lệ','Vui lòng nhập thu nhập đủ điều kiện hợp lệ.'); return; }
  const editedVnd = Math.round(editedTrieu * 1e6);
  closeModal('verifyModal'); const token = runToken; phase = 'revision';
  setNodeMode('humanNode'); setNodeMode('recommendationNode','active');
  setAgentState('recommendationNode','reviewing','ĐANG SỬA','Áp dụng điều chỉnh thu nhập đủ điều kiện theo yêu cầu chuyên viên');
  setText('#stagePill','Đang chỉnh sửa đề xuất');
  addLog('Cổng kiểm duyệt', `Yêu cầu chỉnh sửa: "${reason}" (thu nhập đủ điều kiện → ${formatVnd(editedVnd)})`, 'CHỈNH SỬA','warn');

  try {
    await apiFetch(`/income-verifications/${caseData.case_id}/review`, {
      method: 'POST',
      body: JSON.stringify({ outcome: 'EDIT_AND_RERUN', reason, edited_eligible_income: editedVnd })
    });
    caseData = await apiFetch(`/income-verifications/${caseData.case_id}`);
  } catch (err) {
    toast('Lỗi khi chỉnh sửa', err.message);
    addLog('Hệ thống', `Lỗi gọi review API: ${err.message}`, 'LỖI', 'warn');
    return;
  }
  await sleep(700); if (!validRun(token)) return;

  const rec = caseData.recommendation || {};
  setNodeMode('recommendationNode','complete');
  setAgentState('recommendationNode','done','ĐÃ CẬP NHẬT', `Đủ điều kiện: ${formatVnd(rec.eligible_income)}/tháng`);
  setNodeMode('humanNode','ready'); setAgentState('humanNode','reviewing','CHỜ DUYỆT');
  $('#verifyBtn').disabled = false;
  setText('#stagePill','Chờ chuyên viên duyệt');
  addLog('Recommendation Builder', `Đã cập nhật thu nhập đủ điều kiện theo yêu cầu chuyên viên: ${formatVnd(rec.eligible_income)}/tháng.`, 'ĐÃ CẬP NHẬT','done');
  toast('Đề xuất đã cập nhật','Cổng kiểm duyệt đã nhận phiên bản mới.');
  updateCaseSummary();
}

async function rejectProposal() {
  if (!caseData) return;
  const reason = $('#reviewReason').value.trim() || 'Từ chối kết quả xác minh, chuyển xử lý thủ công.';
  closeModal('verifyModal'); phase = 'rejected'; running = false;

  try {
    await apiFetch(`/income-verifications/${caseData.case_id}/review`, {
      method: 'POST',
      body: JSON.stringify({ outcome: 'MANUAL_HANDLING', reason })
    });
    caseData = await apiFetch(`/income-verifications/${caseData.case_id}`);
  } catch (err) {
    toast('Lỗi khi từ chối', err.message);
    addLog('Hệ thống', `Lỗi gọi review API: ${err.message}`, 'LỖI', 'warn');
    return;
  }

  setNodeMode('humanNode','complete'); setAgentState('humanNode','conflict','TỪ CHỐI');
  $('#verifyBtn').disabled = true; setText('#stagePill','Đã từ chối'); setText('#heroStatus','TỪ CHỐI');
  $('#runBtn').disabled = false; $('#runBtn').innerHTML = '<span>↻</span> Chạy lại xác minh';
  addLog(REVIEWER_NAME, `Đã từ chối đề xuất: "${reason}". Action Executor không được kích hoạt.`, 'ĐÃ TỪ CHỐI','warn');
  toast('Đề xuất đã bị từ chối','Không có dữ liệu nào được ghi sang hệ thống nghiệp vụ.');
  updateCaseSummary();
}

function pendingCaseDocuments() {
  return $$('.file-drop[data-document-type]').flatMap(drop => {
    const file = $('input[type="file"]', drop)?.files?.[0];
    return file ? [{ documentType: drop.dataset.documentType, file }] : [];
  });
}

async function uploadPendingCaseDocuments(caseId, documents) {
  for (const document of documents) {
    const form = new FormData();
    form.append('document_type', document.documentType);
    form.append('file', document.file);
    await apiFetch(`/cases/${caseId}/documents`, { method: 'POST', body: form });
  }
}

async function createCaseFromForm(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const submit = $('#createCaseSubmit');
  const documents = pendingCaseDocuments();
  submit.disabled = true; submit.textContent = 'Đang tạo hồ sơ…';
  try {
    const values = new FormData(form);
    const created = await apiFetch('/cases', {
      method: 'POST',
      body: JSON.stringify({
        customer_name: String(values.get('customer_name') || '').trim(),
        company: String(values.get('company') || '').trim(),
        requested_amount: Number(values.get('requested_amount')),
        currency: 'VND'
      })
    });
    await uploadPendingCaseDocuments(created.id, documents);
    await loadCases();
    await openCase(created.id);
    closeModal('createCaseModal');
    form.reset();
    $$('.file-drop', form).forEach(drop => { drop.classList.remove('has-file'); setText('small','Chưa chọn file',drop); });
    toast('Đã tạo hồ sơ', `${created.id} đã nhận ${documents.length} tài liệu và sẵn sàng chạy pipeline.`);
  } catch (error) {
    toast('Không thể tạo hồ sơ', error.message);
  } finally {
    submit.disabled = false; submit.textContent = 'Tạo hồ sơ và tải tài liệu';
  }
}

const SYSTEM_OUTPUTS = {
  los: { title: 'Kết quả cập nhật LOS', summary: 'Draft thu nhập đã được ghi qua mock Loan Origination System.', action: 'UPDATE_INCOME_DRAFT' },
  dms: { title: 'Kết quả lưu DMS', summary: 'Bằng chứng hồ sơ đã được gắn vào mock Document Management System.', action: 'ATTACH_EVIDENCE' },
  workflow: { title: 'Kết quả Workflow', summary: 'Tác vụ ngoại lệ được quản lý trong mock Workflow.', action: 'CREATE_EXCEPTION_TASK' },
  notification: { title: 'Kết quả Notification', summary: 'Yêu cầu bổ sung tài liệu được tạo trong mock Notification.', action: 'REQUEST_DOCUMENTS' },
  audit: { title: 'Nhật ký kiểm toán', summary: 'Toàn bộ chuyển trạng thái, quyết định và thực thi được ghi append-only.', action: null }
};

function openSystemOutput(system) {
  const config = SYSTEM_OUTPUTS[system]; if (!config) return;
  setText('#systemOutputKicker', `${system.toUpperCase()} · MOCK INTEGRATION OUTPUT`);
  setText('#systemOutputTitle', config.title);
  setText('#systemOutputSummary', config.summary);
  const body = $('#systemOutputBody'); body.innerHTML = '';
  const summary = document.createElement('div'); summary.className = 'output-summary-grid';
  const summaryValues = [
    ['Case', caseData?.case_id || selectedCase?.id || '—'],
    ['Workflow', caseData?.workflow_state || selectedCase?.pipeline_status || '—'],
    ['Chế độ', 'MOCK ONLY']
  ];
  summaryValues.forEach(([label,value]) => { const card=document.createElement('div'); card.className='output-card'; const span=document.createElement('span'); span.textContent=label; const strong=document.createElement('strong'); strong.textContent=value; card.append(span,strong); summary.append(card); });
  const detail = document.createElement('div'); detail.className = 'output-detail';
  const heading = document.createElement('h3');
  const action = config.action ? (caseData?.proposed_actions || []).find(item => item.action_type === config.action) : null;
  const execution = action ? (caseData?.execution_results || []).find(item => item.action_id === action.action_id) : null;
  heading.textContent = action?.description || (system === 'audit' ? `${(caseData?.audit_events || []).length} sự kiện đã ghi nhận` : 'Không phát sinh hành động cho hồ sơ này');
  const dl = document.createElement('dl');
  const fields = system === 'audit'
    ? [['Sự kiện', (caseData?.audit_events || []).length],['State version', caseData?.state_version || 0],['Actor cuối', (caseData?.audit_events || []).at(-1)?.actor_type || '—'],['Event cuối', (caseData?.audit_events || []).at(-1)?.event_type || '—']]
    : [['Action type', config.action],['Permission', action?.permission || '—'],['Status', execution?.status || (action ? 'CHỜ HUMAN REVIEW' : 'KHÔNG PHÁT SINH')],['Verified', execution?.verified ? 'Có' : 'Chưa'],['Result reference', execution?.result_reference || '—'],['Evidence count', action?.evidence_ids?.length || 0]];
  fields.forEach(([label,value]) => { const row=document.createElement('div'); const dt=document.createElement('dt'); const dd=document.createElement('dd'); dt.textContent=label; dd.textContent=String(value); row.append(dt,dd); dl.append(row); });
  detail.append(heading,dl); body.append(summary,detail); openModal('systemOutputModal');
}

function switchView(view) {
  $$('.view').forEach(item => item.classList.toggle('active', item.id === `view-${view}`));
  $$('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.view === view));
  setText('#pageTitle','Trợ lý xác minh thu nhập tín chấp');
  if (view === 'command') requestAnimationFrame(drawEdges);
}

$('#runBtn').addEventListener('click', runAssessment);
$('#resetBtn').addEventListener('click', async () => {
  if (!selectedCase) return;
  const detail = await apiFetch(`/cases/${selectedCase.id}`);
  caseData = detail.context || null; resetFlow(); updateHero();
  if (caseData) hydrateCompletedContext();
  toast('Đã làm mới','Đã tải lại trạng thái mới nhất từ backend.');
});
$('#verifyBtn').addEventListener('click', () => { $$('.verify-check').forEach(box => box.checked = false); $('#confirmApprove').disabled = true; populateVerifyModal(); openModal('verifyModal'); });
$('#confirmApprove').addEventListener('click', approveAndExecute);
$('#requestEditBtn').addEventListener('click', requestRevision);
$('#rejectProposalBtn').addEventListener('click', rejectProposal);
$('#edgePopover button').addEventListener('click', () => $('#edgePopover').hidden = true);
$('#clearLog').addEventListener('click', () => { $('#logStream').innerHTML = ''; addLog('Hệ thống','Nhật ký đã được làm mới.','SẴN SÀNG'); });
$$('.nav-item').forEach(item => item.addEventListener('click', () => switchView(item.dataset.view)));
$$('[data-close]').forEach(button => button.addEventListener('click', () => closeModal(button.dataset.close)));
$$('.modal-backdrop').forEach(backdrop => backdrop.addEventListener('click', event => { if (event.target === backdrop) backdrop.hidden = true; }));
$$('.verify-check').forEach(box => box.addEventListener('change', () => { $('#confirmApprove').disabled = !$$('.verify-check').every(item => item.checked); }));
$('#newCaseBtn').addEventListener('click', () => openModal('createCaseModal'));
$('#addDocsBtn').addEventListener('click', () => { switchView('cases'); openModal('createCaseModal'); });
$('#createCaseForm').addEventListener('submit', createCaseFromForm);
$('#caseSearch').addEventListener('input', event => renderCaseRows(event.target.value));
$$('[data-system-output]').forEach(button => button.addEventListener('click', () => openSystemOutput(button.dataset.systemOutput)));
$$('.file-drop input[type="file"]').forEach(input => input.addEventListener('change', () => {
  const drop = input.closest('.file-drop'); const file = input.files?.[0];
  drop.classList.toggle('has-file', Boolean(file)); setText('small', file ? `1 file · ${file.name}` : 'Chưa chọn file', drop);
  const count = pendingCaseDocuments().length;
  setText('#pendingDocumentCount', count ? `Đã chọn ${count} tài liệu. Tất cả sẽ được gán đúng loại và tải lên sau khi tạo hồ sơ.` : 'Chưa chọn tài liệu. Bạn vẫn có thể tạo hồ sơ và bổ sung sau.');
}));

let resizeTimer;
window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(drawEdges, 100); });
setInterval(() => setText('#liveClock', timeNow()), 1000);

async function bootstrap() {
  setText('#onlineCount','8'); resetFlow(); setText('#liveClock', timeNow());
  try {
    await loadCases();
    if (caseList.length) await openCase(caseList[0].id);
    else { updateHero(); switchView('cases'); }
  } catch (error) {
    toast('Không kết nối được backend', `${error.message}. Backend hiện được cấu hình tại ${API_BASE}.`);
    updateHero(); switchView('cases');
  }
}
bootstrap();
