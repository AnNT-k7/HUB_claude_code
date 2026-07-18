const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const setText = (selector, value, root = document) => { const node = $(selector, root); if (node) node.textContent = value; };

const flowNodes = ['underwriterNode','orchestratorNode','documentNode','incomeNode','policyNode','consistencyNode','recommendationNode','humanNode','executorNode','systemsNode'];
const edgeData = new Map();
let phase = 'idle';
let runToken = 0;
let running = false;

let currentCase = {
  id: 'UV-2026-00128', company: 'Nguyễn Hoàng Minh', initials: 'NM', amount: 500,
  term: 36, file: 'Ho_so_thu_nhap_NHM.pdf', status: 'Sẵn sàng', notes: 'Chuyên viên kinh doanh · Thu nhập kê khai 32 triệu ₫/tháng'
};

const cases = [
  currentCase,
  { id:'UV-2026-00127', company:'Trần Thu Hà', initials:'TH', amount:300, term:24, file:'Sao_ke_6_thang.pdf', status:'Đang xác minh' },
  { id:'UV-2026-00126', company:'Lê Quốc Bảo', initials:'LB', amount:650, term:48, file:'Hop_dong_lao_dong.pdf', status:'Chờ chuyên viên duyệt' },
  { id:'UV-2026-00125', company:'Phạm Minh Anh', initials:'PA', amount:420, term:36, file:'Ho_so_thu_nhap.zip', status:'Đã xác minh' }
];

const evidenceLibrary = {
  document: {
    title:'Bộ hồ sơ thu nhập đã trích xuất', doc:'Checklist hồ sơ tín chấp cá nhân', page:'Mục 2.1 · Trang 6',
    quote:'Hồ sơ xác minh gồm hợp đồng lao động, chứng từ lương gần nhất và sao kê tài khoản nhận lương tối thiểu 6 tháng.'
  },
  income: {
    title:'Thu nhập khớp nguồn trả lương', doc:'Quy trình xác minh thu nhập', page:'Bước 3.2 · Trang 11',
    quote:'Thu nhập ròng được xác định theo trung bình dòng tiền lương hợp lệ, sau khi loại trừ khoản chuyển nội bộ và thu nhập bất thường.'
  },
  policy: {
    title:'Điều kiện DTI tín chấp', doc:'Quy định cấp tín dụng tín chấp cá nhân 2026', page:'Điều 4.3 · Trang 18',
    quote:'Tổng nghĩa vụ trả nợ hằng tháng không vượt quá 50% thu nhập ròng đã được xác minh.'
  }
};

function formatMoney(value) {
  return `${Number(value).toLocaleString('vi-VN', { maximumFractionDigits: 1 })} triệu ₫`;
}

function initials(name) {
  return name.trim().split(/\s+/).slice(-2).map(part => part[0] || '').join('').toUpperCase();
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

function openEvidence(key) {
  const evidence = evidenceLibrary[key]; if (!evidence) return;
  setText('#evidenceTitle', evidence.title); setText('#evidenceDoc', evidence.doc);
  setText('#evidencePage', evidence.page); setText('#evidenceQuote', evidence.quote);
  openModal('evidenceModal');
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
  $('#runBtn').disabled = false; $('#runBtn').innerHTML = '<span>✦</span> Bắt đầu xác minh';
  setText('#stagePill','Sẵn sàng'); setText('#heroStatus','SẴN SÀNG');
  resetEdgeData(); $('#edgePopover').hidden = true; drawEdges();
  if (!silent) {
    $('#logStream').innerHTML = '';
    addLog('Hệ thống','Luồng xử lý đã sẵn sàng cho hồ sơ xác minh thu nhập.','SẴN SÀNG');
  }
}

function validRun(token) { return token === runToken; }

async function runAssessment() {
  if (running) return;
  resetFlow(true); const token = runToken; running = true; phase = 'underwriter';
  $('#logStream').innerHTML = ''; setText('#eventCount','0'); $('#runBtn').disabled = true;
  setText('#heroStatus','ĐANG XÁC MINH'); setText('#stagePill','Tiếp nhận hồ sơ');

  setNodeMode('underwriterNode','active'); setAgentState('underwriterNode','running','ĐANG MỞ','Đang kiểm tra dữ liệu đầu vào');
  addLog('Chuyên viên thẩm định','Đã mở hồ sơ và xác nhận bộ chứng từ đầu vào.','ĐÃ MỞ');
  await sleep(700); if (!validRun(token)) return;
  setNodeMode('underwriterNode','complete'); setAgentState('underwriterNode','done','ĐÃ XÁC NHẬN');
  phase = 'orchestrating'; setText('#stagePill','Lập workflow');
  setNodeMode('orchestratorNode','active'); setAgentState('orchestratorNode','running','ĐIỀU PHỐI');
  updateEdge('underwriter-orchestrator','Đang mở workflow','Metadata hồ sơ và phạm vi xác minh được gửi tới Orchestrator.','active');
  await sendPacket('underwriterNode','orchestratorNode'); if (!validRun(token)) return;

  addLog('Orchestrator Agent','Đã tạo luồng xử lý; tách 3 tác vụ chuyên môn độc lập.','ĐIỀU PHỐI');
  await sleep(900); if (!validRun(token)) return;
  setNodeMode('orchestratorNode','complete'); setAgentState('orchestratorNode','done','ĐÃ GIAO VIỆC','Theo dõi state, retry và timeout');
  updateEdge('underwriter-orchestrator','Workflow đã tạo','Orchestrator đã nhận đủ context, không thực hiện tính toán chuyên môn.','approved');

  phase = 'parallel'; setText('#stagePill','Phân tích song song');
  const dispatches = [
    ['documentNode','orchestrator-document','Trích xuất hợp đồng, bảng lương và sao kê'],
    ['incomeNode','orchestrator-income','Tính thu nhập ròng và dòng tiền lương'],
    ['policyNode','orchestrator-policy','Tra cứu điều kiện DTI và thời gian công tác']
  ];
  dispatches.forEach(([node, edge, detail]) => {
    setNodeMode(node,'active'); setAgentState(node,'running','ĐANG LÀM',detail); updateEdge(edge,'Đã giao nhiệm vụ',detail,'active');
  });
  await Promise.all(dispatches.map(([node]) => sendPacket('orchestratorNode',node))); if (!validRun(token)) return;
  await sleep(1250); if (!validRun(token)) return;

  setNodeMode('documentNode','complete'); setAgentState('documentNode','done','HOÀN TẤT','Đã trích xuất 12 trường từ 4 tài liệu');
  setNodeMode('incomeNode','complete'); setAgentState('incomeNode','done','HOÀN TẤT','Thu nhập ròng xác minh: 31,2 triệu/tháng');
  setNodeMode('policyNode','complete'); setAgentState('policyNode','done','HOÀN TẤT','DTI tối đa 50% · công tác tối thiểu 12 tháng');
  addLog('Document Agent','Đã trích xuất hợp đồng, bảng lương và sao kê 6 tháng.','ĐÃ TRÍCH XUẤT','', 'document');
  addLog('Income Agent','Lương ròng xác minh 31,2 triệu/tháng; lệch 0,6 triệu trong ngưỡng.','ĐÃ XÁC MINH','done','income');
  addLog('Policy Agent','Đã truy xuất điều kiện DTI 50% và thâm niên công tác.','CHÍNH SÁCH','', 'policy');
  phase = 'consistency'; setText('#stagePill','Đối chiếu nhất quán');
  setNodeMode('consistencyNode','active'); setAgentState('consistencyNode','reviewing','ĐANG ĐỐI CHIẾU');
  [['documentNode','document-consistency'],['incomeNode','income-consistency'],['policyNode','policy-consistency']].forEach(([node,edge]) => updateEdge(edge,'Đang chuyển kết quả','Output có cấu trúc được chuyển để đối chiếu chéo.','active'));
  await Promise.all([
    sendPacket('documentNode','consistencyNode'), sendPacket('incomeNode','consistencyNode'), sendPacket('policyNode','consistencyNode')
  ]); if (!validRun(token)) return;

  addLog('Consistency Agent','Đang kiểm tra chéo 3 bộ kết quả và các trường còn thiếu.','ĐỐI CHIẾU','review');
  await sleep(1100); if (!validRun(token)) return;
  setNodeMode('consistencyNode','complete'); setAgentState('consistencyNode','done','NHẤT QUÁN','Không thiếu hồ sơ; sai lệch thu nhập nằm trong ngưỡng');
  ['document-consistency','income-consistency','policy-consistency'].forEach(edge => updateEdge(edge,'Đã đối chiếu','Kết quả hợp lệ và có nguồn bằng chứng truy vết.','approved'));
  addLog('Consistency Agent','Không phát hiện thiếu hồ sơ; sai lệch 0,6 triệu được chấp nhận.','NHẤT QUÁN','done');
  phase = 'recommendation'; setText('#stagePill','Tạo khuyến nghị');
  setNodeMode('recommendationNode','active'); setAgentState('recommendationNode','reviewing','ĐANG TỔNG HỢP');
  updateEdge('consistency-recommendation','Đang tạo đề xuất','Kết quả đã chuẩn hóa được chuyển sang Recommendation Builder.','review');
  await sendPacket('consistencyNode','recommendationNode','review'); if (!validRun(token)) return;

  await sleep(950); if (!validRun(token)) return;
  setNodeMode('recommendationNode','complete'); setAgentState('recommendationNode','done','ĐÃ ĐỀ XUẤT');
  addLog('Recommendation Builder','Đề xuất hạn mức 450 triệu/36 tháng; xác nhận lại nơi công tác.','ĐỀ XUẤT','review','policy');
  phase = 'human'; setText('#stagePill','Chờ chuyên viên duyệt'); setText('#heroStatus','CHỜ KIỂM DUYỆT');
  setNodeMode('humanNode','ready'); setAgentState('humanNode','reviewing','CHỜ DUYỆT');
  updateEdge('recommendation-human','Chờ chuyên viên quyết định','Đề xuất kèm kết quả, hành động và bằng chứng đã sẵn sàng.','review');
  await sendPacket('recommendationNode','humanNode','review'); if (!validRun(token)) return;

  running = false;
  $('#verifyBtn').disabled = false; $('#verifyBtn').textContent = 'Mở kiểm duyệt';
  addLog('Cổng kiểm duyệt','Đề xuất đã khóa phiên bản và chờ chuyên viên quyết định.','KIỂM DUYỆT','review');
}

async function approveAndExecute() {
  closeModal('verifyModal'); phase = 'executing'; running = true; const token = runToken;
  setNodeMode('humanNode','complete'); setAgentState('humanNode','done','ĐÃ DUYỆT'); $('#verifyBtn').disabled = true;
  setText('#stagePill','Thực thi có kiểm soát'); setNodeMode('executorNode','active');
  setAgentState('executorNode','running','ĐANG THỰC THI');
  updateEdge('human-executor','Đã phê duyệt','Quyết định có danh tính người duyệt và dấu thời gian được gửi để thực thi.','approved');
  addLog('Linh Trần','Đã chấp thuận đề xuất xác minh và phạm vi cập nhật.','ĐÃ DUYỆT','done');
  await sendPacket('humanNode','executorNode','approve'); if (!validRun(token)) return;
  addLog('Action Executor','Đã kiểm tra quyền và chuẩn bị cập nhật hệ thống đích.','ĐANG THỰC THI');
  await sleep(1200); if (!validRun(token)) return;
  setNodeMode('executorNode','complete'); setAgentState('executorNode','done','HOÀN TẤT','Đã thực thi đúng phạm vi được phê duyệt');
  setNodeMode('systemsNode','active'); updateEdge('executor-systems','Đang cập nhật','Ghi kết quả tới LOS, DMS, Workflow, Notification và Audit.','approved');
  await sendPacket('executorNode','systemsNode','approve'); if (!validRun(token)) return;
  await sleep(600); if (!validRun(token)) return;
  setNodeMode('systemsNode','complete'); phase = 'complete'; running = false;
  setText('#stagePill','Hoàn tất'); setText('#heroStatus','ĐÃ XÁC MINH');
  currentCase.status = 'Đã xác minh'; renderCases();
  $('#runBtn').disabled = false; $('#runBtn').innerHTML = '<span>↻</span> Chạy lại xác minh';
  addLog('Hệ thống','LOS, DMS, Workflow, Notification và Audit đã cập nhật thành công.','HOÀN TẤT','done');
  toast('Xác minh hoàn tất','Kết quả đã được ghi nhận và lưu dấu vết kiểm toán.');
}

async function requestRevision() {
  closeModal('verifyModal'); const token = runToken; phase = 'revision';
  setNodeMode('humanNode'); setNodeMode('recommendationNode','active');
  setAgentState('recommendationNode','reviewing','ĐANG SỬA','Bổ sung bước xác nhận đơn vị công tác');
  setText('#stagePill','Đang chỉnh sửa đề xuất');
  addLog('Cổng kiểm duyệt','Yêu cầu bổ sung bước gọi xác nhận đơn vị công tác.','CHỈNH SỬA','warn');
  await sleep(1200); if (!validRun(token)) return;
  setNodeMode('recommendationNode','complete'); setAgentState('recommendationNode','done','ĐÃ CẬP NHẬT','Đã thêm điều kiện xác nhận nơi công tác');
  setNodeMode('humanNode','ready'); setAgentState('humanNode','reviewing','CHỜ DUYỆT');
  setText('#stagePill','Chờ chuyên viên duyệt'); addLog('Recommendation Builder','Đã cập nhật hành động đề xuất theo yêu cầu chuyên viên.','ĐÃ CẬP NHẬT','done');
  toast('Đề xuất đã cập nhật','Cổng kiểm duyệt đã nhận phiên bản mới.');
}

function rejectProposal() {
  closeModal('verifyModal'); phase = 'rejected'; running = false;
  setNodeMode('humanNode','complete'); setAgentState('humanNode','conflict','TỪ CHỐI');
  $('#verifyBtn').disabled = true; setText('#stagePill','Đã từ chối'); setText('#heroStatus','TỪ CHỐI');
  $('#runBtn').disabled = false; $('#runBtn').innerHTML = '<span>↻</span> Chạy lại xác minh';
  addLog('Linh Trần','Đã từ chối đề xuất; Action Executor không được kích hoạt.','ĐÃ TỪ CHỐI','warn');
  toast('Đề xuất đã bị từ chối','Không có dữ liệu nào được ghi sang hệ thống nghiệp vụ.');
}

function renderCases(filter = '') {
  const query = filter.trim().toLowerCase(); const rows = $('#caseRows'); rows.innerHTML = '';
  cases.filter(item => `${item.company} ${item.id}`.toLowerCase().includes(query)).forEach(item => {
    const row = document.createElement('div'); row.className = 'table-row';
    const caseCell = document.createElement('div'); caseCell.className = 'case-cell';
    const logo = document.createElement('div'); logo.className = 'company-logo'; logo.textContent = item.initials;
    const copy = document.createElement('div'); const name = document.createElement('strong'); name.textContent = item.company;
    const meta = document.createElement('small'); meta.textContent = `#${item.id} · ${item.file}`; copy.append(name,meta); caseCell.append(logo,copy);
    const amount = document.createElement('strong'); amount.textContent = formatMoney(item.amount);
    const term = document.createElement('span'); term.textContent = `${item.term} tháng`;
    const status = document.createElement('span'); status.className = `status-badge ${item.status.includes('chuyên viên') ? 'review' : item.status === 'Hồ sơ mới' ? 'new' : ''}`; status.textContent = item.status;
    const open = document.createElement('button'); open.className = 'open-case'; open.dataset.case = item.id; open.textContent = 'Mở →';
    row.append(caseCell, amount, term, status, open); rows.append(row);
  });
  setText('#totalCases', cases.length); setText('#caseCount', cases.length);
}

function switchView(view) {
  $$('.view').forEach(item => item.classList.toggle('active', item.id === `view-${view}`));
  $$('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.view === view));
  setText('#pageTitle','Trợ lý xác minh thu nhập tín chấp');
  if (view === 'command') requestAnimationFrame(drawEdges);
}

function loadCase(id) {
  const found = cases.find(item => item.id === id); if (!found) return;
  currentCase = found; setText('#heroCaseId',`HỒ SƠ #${found.id}`); setText('#heroCompany',found.company); setText('#heroLogo',found.initials);
  setText('#heroAmount',formatMoney(found.amount)); setText('#heroTerm',`${found.term} tháng`); setText('#heroFile',found.file);
  switchView('command'); resetFlow(); toast('Đã mở hồ sơ',`${found.company} sẵn sàng để xác minh thu nhập.`);
}

$('#runBtn').addEventListener('click', runAssessment);
$('#resetBtn').addEventListener('click', () => { resetFlow(); toast('Đã đặt lại','Luồng xử lý trở về trạng thái sẵn sàng.'); });
$('#verifyBtn').addEventListener('click', () => { $$('.verify-check').forEach(box => box.checked = false); $('#confirmApprove').disabled = true; openModal('verifyModal'); });
$('#confirmApprove').addEventListener('click', approveAndExecute);
$('#requestEditBtn').addEventListener('click', requestRevision);
$('#rejectProposalBtn').addEventListener('click', rejectProposal);
$('#edgePopover button').addEventListener('click', () => $('#edgePopover').hidden = true);
$('#clearLog').addEventListener('click', () => { $('#logStream').innerHTML = ''; addLog('Hệ thống','Nhật ký đã được làm mới.','SẴN SÀNG'); });
$('#createCaseBtn').addEventListener('click', () => openModal('caseModal'));
$('#caseSearch').addEventListener('input', event => renderCases(event.target.value));
$('#caseRows').addEventListener('click', event => { const button = event.target.closest('[data-case]'); if (button) loadCase(button.dataset.case); });
$$('.nav-item').forEach(item => item.addEventListener('click', () => switchView(item.dataset.view)));
$$('[data-close]').forEach(button => button.addEventListener('click', () => closeModal(button.dataset.close)));
$$('.modal-backdrop').forEach(backdrop => backdrop.addEventListener('click', event => { if (event.target === backdrop) backdrop.hidden = true; }));
$$('.verify-check').forEach(box => box.addEventListener('change', () => { $('#confirmApprove').disabled = !$$('.verify-check').every(item => item.checked); }));

$('#documentInput').addEventListener('change', event => {
  const file = event.target.files[0]; if (!file) return;
  if (file.size > 25 * 1024 * 1024) { event.target.value = ''; toast('File quá lớn','Vui lòng chọn file dưới 25 MB.'); return; }
  setText('#fileName', file.name); $('#fileDrop').classList.add('has-file');
});

$('#caseForm').addEventListener('submit', event => {
  event.preventDefault(); const data = new FormData(event.currentTarget); const name = String(data.get('company')).trim(); const file = data.get('document');
  const item = { id:`UV-2026-${String(129 + cases.length).padStart(5,'0')}`, company:name, initials:initials(name), amount:Number(data.get('amount')), term:Number(data.get('term')), file:file.name, status:'Hồ sơ mới', notes:String(data.get('notes')) };
  cases.unshift(item); renderCases(); closeModal('caseModal'); event.currentTarget.reset(); setText('#fileName','Tải file thông tin liên quan'); $('#fileDrop').classList.remove('has-file');
  loadCase(item.id); addLog('Orchestrator Agent','Hồ sơ mới đã vào hàng đợi xác minh thu nhập.','HỒ SƠ MỚI');
});

let resizeTimer;
window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(drawEdges, 100); });
setInterval(() => setText('#liveClock', timeNow()), 1000);
setText('#onlineCount','6'); renderCases(); resetFlow(); setText('#liveClock', timeNow());
