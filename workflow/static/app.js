/* 数学建模智能体 — 多项目前端逻辑 */
let currentProject = null;
let currentStage = null;
let pollingTimer = null;
let workflowRunning = false;
let selectedAgent = 'claude';
const stages = window.STAGES || [];
const stageCount = stages.length;

// ── Init ──
document.addEventListener('DOMContentLoaded', async () => {
  await initAgentSelector();
  await loadProjectList();
  setupUpload();
  setupReplaceUpload();
});

// ── Project management ──
async function loadProjectList() {
  var res = await fetch('/api/projects');
  var projects = await res.json();
  var container = document.getElementById('project-list');
  var empty = document.getElementById('empty-projects');

  if (!projects.length) {
    container.innerHTML = '';
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');
  container.innerHTML = projects.map(function(p) {
    var pct = p.total_stages > 0 ? Math.round((p.completed_stages / p.total_stages) * 100) : 0;
    var statusLabel = p.has_problem ? (p.completed_stages + '/' + p.total_stages + ' 阶段') : '未上传题目';
    var statusClass = p.completed_stages === p.total_stages ? 'done' : (p.completed_stages > 0 ? 'partial' : 'empty');
    return '<div class="project-card" onclick="openProject(\'' + escapeHtml(p.name) + '\')">' +
      '<div class="project-card-header">' +
        '<svg class="project-card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="22" height="22"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>' +
        '<div class="project-card-actions">' +
          '<button class="project-menu-btn" onclick="event.stopPropagation();deleteProjectPrompt(\'' + escapeHtml(p.name) + '\')" title="删除项目">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>' +
          '</button>' +
        '</div>' +
      '</div>' +
      '<div class="project-card-name">' + escapeHtml(p.name) + '</div>' +
      '<div class="project-card-footer">' +
        '<span class="project-status ' + statusClass + '">' + statusLabel + '</span>' +
        (p.created_at ? '<span class="project-date">' + p.created_at.slice(0, 10) + '</span>' : '') +
      '</div>' +
    '</div>';
  }).join('');
}

function openProject(name) {
  currentProject = name;
  document.getElementById('sidebar').classList.remove('hidden');
  document.getElementById('sidebar-project-name').textContent = name;
  document.getElementById('home-view').classList.add('hidden');
  document.getElementById('project-view').classList.remove('hidden');
  document.getElementById('upload-project-title').textContent = name;

  // Check project state
  refreshProjectStatus();
}

async function refreshProjectStatus() {
  var res = await fetch('/api/status?project=' + encodeURIComponent(currentProject));
  var data = await res.json();
  workflowRunning = data.running;

  if (data.has_problem) {
    document.getElementById('upload-view').classList.add('hidden');
    document.getElementById('control-view').classList.remove('hidden');
    document.getElementById('upload-label').textContent = '已加载题目（点击更换）';

    // Get problem file name
    try {
      var projRes = await fetch('/api/projects');
      var projects = await projRes.json();
      var proj = projects.find(function(p) { return p.name === currentProject; });
      if (proj) {
        document.getElementById('problem-badge').innerHTML =
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">' +
          '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg> 题目已加载';
      }
    } catch(e) {}

    buildSidebar();
    updateProgress(data.state);
    updateSidebarState(data.state);

    if (data.running) {
      showRunningState();
      document.getElementById('progress-bar-wrap').classList.remove('hidden');
      startPolling();
    } else {
      showIdleState();
    }
  } else {
    document.getElementById('upload-view').classList.remove('hidden');
    document.getElementById('control-view').classList.add('hidden');
    buildSidebar();
  }
}

function goHome() {
  stopPolling();
  currentProject = null;
  document.getElementById('sidebar').classList.add('hidden');
  document.getElementById('home-view').classList.remove('hidden');
  document.getElementById('project-view').classList.add('hidden');
  document.getElementById('stage-view').classList.add('hidden');
  document.getElementById('feedback-panel').classList.add('hidden');
  document.getElementById('upload-view').classList.remove('hidden');
  document.getElementById('control-view').classList.add('hidden');
  loadProjectList();
}

// ── New project dialog ──
function showNewProjectDialog() {
  document.getElementById('new-project-dialog').classList.remove('hidden');
  document.getElementById('new-project-name').focus();
}

function hideNewProjectDialog() {
  document.getElementById('new-project-dialog').classList.add('hidden');
  document.getElementById('new-project-name').value = '';
}

async function createProject() {
  var name = document.getElementById('new-project-name').value.trim();
  if (!name) { alert('请输入项目名称'); return; }
  var res = await fetch('/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name })
  });
  var data = await res.json();
  if (!data.ok) { alert(data.error); return; }
  hideNewProjectDialog();
  await loadProjectList();
  openProject(name);
}

async function deleteProjectPrompt(name) {
  if (!confirm('确定要删除项目「' + name + '」吗？\n\n所有题目文件和建模结果将被永久删除。')) return;
  var res = await fetch('/api/projects/' + encodeURIComponent(name), { method: 'DELETE' });
  var data = await res.json();
  if (!data.ok) { alert(data.error); return; }
  if (currentProject === name) goHome();
  loadProjectList();
}

// ── View switching ──
function showUploadView() {
  document.getElementById('upload-view').classList.remove('hidden');
  document.getElementById('control-view').classList.add('hidden');
  document.getElementById('stage-view').classList.add('hidden');
  document.getElementById('feedback-panel').classList.add('hidden');
}

function showControlView() {
  document.getElementById('upload-view').classList.add('hidden');
  document.getElementById('control-view').classList.remove('hidden');
  document.getElementById('stage-view').classList.add('hidden');
  document.getElementById('feedback-panel').classList.add('hidden');
}

// ── Agent selection ──
async function initAgentSelector() {
  try {
    var res = await fetch('/api/agent');
    var data = await res.json();
    selectedAgent = data.provider || 'claude';
    updateAgentUI();
  } catch (e) { selectedAgent = 'claude'; }
}

function selectAgent(agent) {
  if (selectedAgent === agent) return;
  selectedAgent = agent;
  updateAgentUI();
  fetch('/api/agent', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider: agent })
  });
}

function updateAgentUI() {
  document.querySelectorAll('.agent-option').forEach(function(el) {
    el.classList.remove('active');
    if (el.dataset.agent === selectedAgent) el.classList.add('active');
  });
}

// ── Sidebar ──
function buildSidebar() {
  var list = document.getElementById('stage-list');
  list.innerHTML = stages.map(function(s) {
    return '<li class="stage-item" data-id="' + s.id + '" onclick="loadStage(' + s.id + ')">' +
      '<span class="stage-num" id="stage-num-' + s.id + '">' + s.id + '</span>' +
      '<div class="stage-info">' +
        '<span class="stage-name">' + s.name + '</span>' +
        '<span class="stage-desc">' + s.description + '</span>' +
      '</div></li>';
  }).join('');
}

function updateSidebarState(state) {
  if (!state || !state.stages) return;
  var stageStates = state.stages;
  stages.forEach(function(s) {
    var el = document.querySelector('.stage-item[data-id="' + s.id + '"]');
    if (!el) return;
    el.classList.remove('active', 'running', 'completed');
    var ss = stageStates[s.id];
    if (ss && ss.status === 'completed') el.classList.add('completed');
    else if (ss && ss.status === 'running') el.classList.add('running');
  });
  updateSidebarLabel(state);
}

function updateSidebarLabel(state) {
  var el = document.getElementById('sidebar-status');
  var stageStates = state.stages || {};
  if (state.current_stage && workflowRunning) {
    var cs = stages.find(function(s) { return s.id === state.current_stage; });
    el.textContent = cs ? '运行中：' + cs.name : '';
    el.className = 'sidebar-status';
  } else if (!workflowRunning && Object.keys(stageStates).length > 0) {
    var allDone = Object.values(stageStates).every(function(s) { return s.status === 'completed'; });
    el.textContent = allDone ? '全部完成' : '';
    el.className = allDone ? 'sidebar-status done' : 'sidebar-status';
  }
}

// ── Upload ──
function setupUpload() {
  var zone = document.getElementById('upload-zone');
  var input = document.getElementById('file-input');
  if (!zone) return;

  zone.addEventListener('click', function() { input.click(); });
  zone.addEventListener('dragover', function(e) { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', function() { zone.classList.remove('drag-over'); });
  zone.addEventListener('drop', function(e) {
    e.preventDefault();
    zone.classList.remove('drag-over');
    var file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  });
  input.addEventListener('change', function() {
    var file = input.files[0];
    if (file) uploadFile(file);
  });
}

function setupReplaceUpload() {
  var input = document.getElementById('file-input-2');
  if (!input) return;
  input.addEventListener('change', function() {
    var file = input.files[0];
    if (file) uploadFile(file);
  });
}

function triggerUpload() {
  document.getElementById('file-input-2').click();
}

async function uploadFile(file) {
  var ext = file.name.split('.').pop().toLowerCase();
  if (ext !== 'pdf' && ext !== 'txt') {
    alert('只支持 PDF / TXT 文件');
    return;
  }
  var formData = new FormData();
  formData.append('file', file);
  formData.append('project', currentProject);

  var res = await fetch('/api/upload', { method: 'POST', body: formData });
  var data = await res.json();
  if (!data.ok) { alert('上传失败: ' + (data.error || '未知错误')); return; }

  stopPolling();
  document.getElementById('upload-view').classList.add('hidden');
  document.getElementById('control-view').classList.remove('hidden');
  document.getElementById('upload-label').textContent = data.filename;
  document.getElementById('problem-badge').innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">' +
    '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg> ' + data.filename;
  buildSidebar();
  document.getElementById('progress-bar-wrap').classList.add('hidden');
  document.getElementById('progress-fill').style.width = '0%';
  document.getElementById('progress-text').textContent = '0/' + stageCount;
  document.getElementById('sidebar-status').textContent = '';
  document.getElementById('sidebar-status').className = 'sidebar-status';
  document.getElementById('btn-start').classList.remove('hidden');
  document.getElementById('btn-stop').classList.add('hidden');
}

// ── Workflow control ──
async function startWorkflow() {
  var res = await fetch('/api/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider: selectedAgent, project: currentProject })
  });
  var data = await res.json();
  if (!data.ok) { alert(data.error || '启动失败'); return; }

  workflowRunning = true;
  document.getElementById('btn-start').classList.add('hidden');
  document.getElementById('btn-stop').classList.remove('hidden');
  document.getElementById('progress-bar-wrap').classList.remove('hidden');
  document.getElementById('progress-fill').style.width = '0%';
  document.getElementById('progress-text').textContent = '0/' + stageCount;
  startPolling();
}

function startPolling() {
  stopPolling();
  pollStatus();
  pollingTimer = setInterval(pollStatus, 2000);
}

function stopPolling() {
  if (pollingTimer) { clearInterval(pollingTimer); pollingTimer = null; }
}

async function stopWorkflow() {
  stopPolling();
  await fetch('/api/stop', { method: 'POST' });
  workflowRunning = false;
  document.getElementById('btn-stop').classList.add('hidden');
  document.getElementById('btn-start').classList.remove('hidden');
  document.getElementById('progress-bar-wrap').classList.add('hidden');
  document.getElementById('progress-fill').style.width = '0%';
  document.getElementById('progress-text').textContent = '0/' + stageCount;
  updateSidebarState({ stages: {} });
}

function showRunningState() {
  document.getElementById('btn-start').classList.add('hidden');
  document.getElementById('btn-stop').classList.remove('hidden');
}

function showIdleState() {
  document.getElementById('btn-stop').classList.add('hidden');
  document.getElementById('btn-start').classList.remove('hidden');
}

async function pollStatus() {
  var res = await fetch('/api/status?project=' + encodeURIComponent(currentProject));
  var data = await res.json();
  workflowRunning = data.running;
  updateProgress(data.state);
  updateSidebarState(data.state);
  if (!data.running) { stopPolling(); showIdleState(); }
}

function updateProgress(state) {
  if (!state || !state.stages) return;
  var stageStates = Object.values(state.stages);
  var completed = stageStates.filter(function(s) { return s.status === 'completed'; }).length;
  var pct = stageCount > 0 ? Math.round((completed / stageCount) * 100) : 0;
  document.getElementById('progress-fill').style.width = pct + '%';
  document.getElementById('progress-text').textContent = completed + '/' + stageCount;
}

// ── Stage viewer ──
async function loadStage(id) {
  currentStage = id;
  document.querySelectorAll('.stage-item').forEach(function(el) { el.classList.remove('active'); });
  var item = document.querySelector('.stage-item[data-id="' + id + '"]');
  if (item) item.classList.add('active');

  document.getElementById('control-view').classList.add('hidden');
  document.getElementById('feedback-panel').classList.add('hidden');
  document.getElementById('stage-view').classList.remove('hidden');

  var res = await fetch('/api/stage/' + id + '?project=' + encodeURIComponent(currentProject));
  var data = await res.json();
  document.getElementById('stage-title').textContent = data.stage.id + '. ' + data.stage.name;
  document.getElementById('stage-content').innerHTML = renderContent(data.content, data.stage);
  hljs.highlightAll();
}

function renderContent(content, stage) {
  if (content.type === 'empty') return '<p style="color:var(--text-muted)">' + content.content + '</p>';
  if (content.type === 'markdown') return content.content;
  if (content.type === 'directory') {
    var html = '';
    var base = stage.output_file;
    if (content.figures && content.figures.length) {
      html += '<h3>图表</h3><div class="figure-grid">';
      content.figures.forEach(function(fig) {
        var src = '/api/image?path=' + encodeURIComponent(base + fig) + '&project=' + encodeURIComponent(currentProject);
        html += '<img src="' + src + '" alt="' + fig + '" onclick="showModal(this.src)">';
      });
      html += '</div>';
    }
    if (content.files && content.files.length) {
      html += '<h3>文件</h3><div class="file-list">';
      content.files.forEach(function(f) {
        var path = base + f.name;
        var size = f.size > 1024 ? (f.size / 1024).toFixed(1) + 'KB' : f.size + 'B';
        html += '<div class="file-card" onclick="openFile(\'' + path + '\')">' +
          '<div class="name">' + f.name + '</div>' +
          '<div class="meta">' + f.suffix + ' · ' + size + '</div></div>';
      });
      html += '</div>';
    }
    return html || '<p style="color:var(--text-muted)">目录为空</p>';
  }
  return '<p>未知内容类型</p>';
}

function closeStageView() {
  currentStage = null;
  document.querySelectorAll('.stage-item').forEach(function(el) { el.classList.remove('active'); });
  document.getElementById('stage-view').classList.add('hidden');
  showControlView();
}

async function openFile(path) {
  var res = await fetch('/api/file?path=' + encodeURIComponent(path) + '&project=' + encodeURIComponent(currentProject));
  var data = await res.json();
  var html = '';
  if (data.type === 'markdown') {
    html = data.html;
  } else if (data.type === 'code' || data.type === 'latex') {
    html = '<pre><code class="language-' + (data.lang || '') + '">' + escapeHtml(data.content) + '</code></pre>';
  } else {
    html = '<pre>' + escapeHtml(data.content) + '</pre>';
  }
  document.getElementById('stage-content').innerHTML =
    '<button onclick="loadStage(' + currentStage + ')" class="btn-back" style="margin-bottom:16px">' +
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">' +
    '<polyline points="15 18 9 12 15 6"/></svg> 返回</button>' + html;
  hljs.highlightAll();
}

// ── Feedback ──
function showFeedbackPanel() {
  document.getElementById('control-view').classList.add('hidden');
  document.getElementById('stage-view').classList.add('hidden');
  document.getElementById('feedback-panel').classList.remove('hidden');
  document.querySelectorAll('.stage-item').forEach(function(el) { el.classList.remove('active'); });
  loadFeedbackList();
}

function hideFeedbackPanel() {
  document.getElementById('feedback-panel').classList.add('hidden');
  showControlView();
}

async function loadFeedbackList() {
  var res = await fetch('/api/feedback?project=' + encodeURIComponent(currentProject));
  var list = await res.json();
  var container = document.getElementById('feedback-list');
  if (!list.length) { container.innerHTML = '<p style="color:var(--text-muted)">暂无修改意见</p>'; return; }
  container.innerHTML = list.map(function(item) {
    var row = '<div class="fb-item' + (item.resolved ? ' resolved' : '') + '">' +
      '<div class="fb-meta">[' + item.section + '] ' + item.created_at.slice(0, 16) + '</div>' +
      '<div class="fb-text">' + escapeHtml(item.content) + '</div>';
    if (item.resolved) {
      row += '<span style="color:var(--accent-green);font-size:12px">已解决</span>';
    } else {
      row += '<button class="btn-resolve" onclick="resolveFeedback(' + item.id + ')">标记已解决</button>';
    }
    row += '</div>';
    return row;
  }).join('');
}

async function submitFeedback() {
  var content = document.getElementById('fb-content').value.trim();
  if (!content) return;
  await fetch('/api/feedback?project=' + encodeURIComponent(currentProject), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project: currentProject,
      section: document.getElementById('fb-section').value,
      content: content
    })
  });
  document.getElementById('fb-content').value = '';
  loadFeedbackList();
}

async function resolveFeedback(id) {
  await fetch('/api/feedback/' + id + '/resolve?project=' + encodeURIComponent(currentProject), { method: 'POST' });
  loadFeedbackList();
}

// ── Utilities ──
function showModal(src) {
  var overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.onclick = function() { overlay.remove(); };
  overlay.innerHTML = '<img src="' + src + '">';
  document.body.appendChild(overlay);
}

function escapeHtml(text) {
  var div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}

async function resetAll() {
  var deleteProblem = confirm('要同时删除题目文件吗？\n\n"确定" = 删除题目 + 清空结果\n"取消" = 仅清空运行结果，保留题目');
  stopPolling();
  await fetch('/api/reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project: currentProject, delete_problem: deleteProblem })
  });
  document.getElementById('btn-stop').classList.add('hidden');
  document.getElementById('btn-start').classList.remove('hidden');
  document.getElementById('progress-bar-wrap').classList.add('hidden');
  document.getElementById('progress-fill').style.width = '0%';
  document.getElementById('progress-text').textContent = '0/' + stageCount;
  document.getElementById('sidebar-status').textContent = '';
  document.getElementById('sidebar-status').className = 'sidebar-status';
  document.getElementById('stage-list').innerHTML = '';
  document.getElementById('stage-view').classList.add('hidden');
  if (deleteProblem) {
    showUploadView();
  } else {
    buildSidebar();
    showControlView();
  }
}
