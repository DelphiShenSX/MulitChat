// MultiAI 对话系统 - 主页面 JavaScript

const API_BASE = 'http://localhost:8000';

// 状态管理
let currentSession = null;
let currentTopicSummary = null;
let chatStatus = null;
let statusPollInterval = null;
let eventSource = null;

// DOM 元素
const elements = {
    sessionList: document.getElementById('sessionList'),
    newSessionBtn: document.getElementById('newSessionBtn'),
    settingsBtn: document.getElementById('settingsBtn'),
    currentSessionTitle: document.getElementById('currentSessionTitle'),
    statusIndicator: document.getElementById('statusIndicator'),
    roundIndicator: document.getElementById('roundIndicator'),
    timeIndicator: document.getElementById('timeIndicator'),
    tokenIndicator: document.getElementById('tokenIndicator'),
    topicInput: document.getElementById('topicInput'),
    stopConditionType: document.getElementById('stopConditionType'),
    stopConditionValue: document.getElementById('stopConditionValue'),
    customPrompt: document.getElementById('customPrompt'),
    chatMessages: document.getElementById('chatMessages'),
    chatContainer: document.getElementById('chatContainer'),
    startBtn: document.getElementById('startBtn'),
    pauseBtn: document.getElementById('pauseBtn'),
    summarizeBtn: document.getElementById('summarizeBtn'),
    exportBtn: document.getElementById('exportBtn'),
    questionInput: document.getElementById('questionInput'),
    sendQuestionBtn: document.getElementById('sendQuestionBtn'),
    newSessionModal: document.getElementById('newSessionModal'),
    newTopicInput: document.getElementById('newTopicInput'),
    closeNewSessionModal: document.getElementById('closeNewSessionModal'),
    cancelNewSession: document.getElementById('cancelNewSession'),
    confirmNewSession: document.getElementById('confirmNewSession'),
    deleteSessionModal: document.getElementById('deleteSessionModal'),
    closeDeleteModal: document.getElementById('closeDeleteModal'),
    cancelDelete: document.getElementById('cancelDelete'),
    confirmDelete: document.getElementById('confirmDelete')
};

// Toast 通知
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast') || createToast();
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    setTimeout(() => {
        toast.className = 'toast';
    }, 3000);
}

function createToast() {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.id = 'toast';
    document.body.appendChild(toast);
    return toast;
}

// 自定义Prompt自动保存/恢复（持久化到 userprompt.md 文件）
const CUSTOM_PROMPT_KEY = 'multichat_custom_prompt';
let savePromptTimer = null;

function saveCustomPrompt() {
    const value = elements.customPrompt.value;
    localStorage.setItem(CUSTOM_PROMPT_KEY, value);
    // 防抖：停止输入500ms后保存到服务端
    clearTimeout(savePromptTimer);
    savePromptTimer = setTimeout(async () => {
        try {
            await fetch(`${API_BASE}/api/custom-prompt`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: value })
            });
        } catch (error) {
            console.error('Failed to save custom prompt to server:', error);
        }
    }, 500);
}

async function restoreCustomPrompt() {
    // 优先从服务端加载，降级到 localStorage
    try {
        const response = await fetch(`${API_BASE}/api/custom-prompt`);
        const data = await response.json();
        if (data.content) {
            elements.customPrompt.value = data.content;
            localStorage.setItem(CUSTOM_PROMPT_KEY, data.content);
            return;
        }
    } catch (error) {
        console.error('Failed to load custom prompt from server:', error);
    }
    // 降级：从 localStorage 恢复
    const saved = localStorage.getItem(CUSTOM_PROMPT_KEY);
    if (saved) {
        elements.customPrompt.value = saved;
    }
}

// 初始化
async function init() {
    console.log('Initializing app...');
    console.log('sessionList element:', elements.sessionList);
    console.log('newSessionBtn element:', elements.newSessionBtn);
    
    await loadSessions();
    setupEventListeners();
    setupKeyboardShortcuts();
    restoreCustomPrompt();

    // 恢复上次的会话状态（从设置页返回时）
    await restoreSessionState();
    
    console.log('App initialized successfully');
}

// 保存当前会话状态到 sessionStorage
function saveSessionState() {
    if (currentSession && currentTopicSummary) {
        sessionStorage.setItem('multichat_session_id', currentSession.id);
        sessionStorage.setItem('multichat_topic_summary', currentTopicSummary);
    } else {
        sessionStorage.removeItem('multichat_session_id');
        sessionStorage.removeItem('multichat_topic_summary');
    }
}

// 从 sessionStorage 恢复会话状态
async function restoreSessionState() {
    const savedSessionId = sessionStorage.getItem('multichat_session_id');
    const savedTopicSummary = sessionStorage.getItem('multichat_topic_summary');

    if (savedSessionId && savedTopicSummary) {
        // 恢复会话
        await selectSession(savedSessionId, savedTopicSummary);
    }
}

// 恢复会话的UI状态（标题、按钮等）
async function restoreSessionUI() {
    if (!currentSession || !currentTopicSummary) return;

    try {
        const response = await fetch(`${API_BASE}/api/chat/status/${currentSession.id}?topic_summary=${currentTopicSummary}`);
        const data = await response.json();

        if (data.is_running) {
            // 后端仍在运行，恢复运行中状态
            updateStatus('running', data.current_round || 0, 0, data.total_tokens || 0, data.current_model || null);
            enableControls(false, true, true);
        } else {
            // 已停止
            updateStatus(data.status || 'stopped', data.current_round || 0, 0, data.total_tokens || 0);
            enableControls(true, false, true);
        }

        // 加载消息
        await loadMessages(currentSession.id, currentTopicSummary);

        // 更新标题
        const sessionResp = await fetch(`${API_BASE}/api/sessions/${currentSession.id}?topic_summary=${currentTopicSummary}`);
        if (sessionResp.ok) {
            const sessionData = await sessionResp.json();
            if (sessionData.topic) {
                elements.topicInput.value = sessionData.topic;
                elements.currentSessionTitle.textContent = sessionData.topic.substring(0, 30) + (sessionData.topic.length > 30 ? '...' : '');
            }
        }
    } catch (error) {
        console.error('Failed to restore session UI:', error);
    }
}

// 加载会话列表
async function loadSessions() {
    try {
        const response = await fetch(`${API_BASE}/api/sessions`);
        const data = await response.json();
        renderSessionList(data.sessions || []);
    } catch (error) {
        console.error('Failed to load sessions:', error);
        // 如果后端未启动，显示本地存储的会话
        renderSessionList([]);
    }
}

// 渲染会话列表
function renderSessionList(sessions) {
    if (sessions.length === 0) {
        elements.sessionList.innerHTML = '<div class="empty-state">暂无会话</div>';
        return;
    }

    elements.sessionList.innerHTML = sessions.map(session => `
        <div class="session-item ${currentSession?.id === session.id ? 'active' : ''}" 
             data-session-id="${session.id}" 
             data-topic-summary="${session.summary}">
            <div class="session-name">${escapeHtml(session.topic)}</div>
            <div class="session-meta">${formatDate(session.updated_at)}</div>
            <button class="delete-btn" data-session-id="${session.id}" data-topic-summary="${session.summary}">×</button>
        </div>
    `).join('');

    // 绑定点击事件
    document.querySelectorAll('.session-item').forEach(item => {
        item.addEventListener('click', (e) => {
            if (!e.target.classList.contains('delete-btn')) {
                selectSession(item.dataset.sessionId, item.dataset.topicSummary);
            }
        });
    });

    // 绑定删除按钮事件
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            showDeleteConfirmation(btn.dataset.sessionId, btn.dataset.topicSummary);
        });
    });
}

// 选择会话
async function selectSession(sessionId, topicSummary) {
    currentSession = { id: sessionId };
    currentTopicSummary = topicSummary;
    saveSessionState();

    // 更新UI
    document.querySelectorAll('.session-item').forEach(item => {
        item.classList.toggle('active', item.dataset.sessionId === sessionId);
    });

    // 检查后端运行状态并恢复UI（包含加载消息和更新标题）
    await restoreSessionUI();

    // 开始轮询状态
    startStatusPolling();
}

// 加载消息
async function loadMessages(sessionId, topicSummary) {
    try {
        const response = await fetch(`${API_BASE}/api/messages/${topicSummary}/${sessionId}`);
        const data = await response.json();
        renderMessages(data.messages || []);
    } catch (error) {
        console.error('Failed to load messages:', error);
        renderMessages([]);
    }
}

// 渲染消息
function renderMessages(messages) {
    if (messages.length === 0) {
        elements.chatMessages.innerHTML = `
            <div class="welcome-message">
                <h1>🎉 欢迎使用 MultiAI 对话系统</h1>
                <p>选择左侧会话或新建会话开始多模型协同对话</p>
                <div class="features">
                    <div class="feature-item">🎯 牵引主题聚焦</div>
                    <div class="feature-item">🤖 多模型协同</div>
                    <div class="feature-item">📝 Markdown 归档</div>
                </div>
            </div>
        `;
        return;
    }

    elements.chatMessages.innerHTML = messages.map(msg => `
        <div class="message">
            <div class="message-header">
                <span class="message-role ${msg.role}">
                    ${msg.role === 'user' ? '用户' : msg.model_alias || 'AI'}
                </span>
                <span class="message-time">${formatTime(msg.timestamp)}</span>
            </div>
            <div class="message-content">${escapeHtml(msg.content)}</div>
        </div>
    `).join('');

    // 滚动到底部
    elements.chatContainer.scrollTop = elements.chatContainer.scrollHeight;
}

// 创建新会话
async function createSession(topic) {
    if (!topic.trim()) {
        showToast('请输入牵引主题', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/sessions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic })
        });

        const data = await response.json();
        currentSession = { id: data.session_id };
        currentTopicSummary = data.topic_summary;
        saveSessionState();

        // 更新UI
        elements.topicInput.value = topic;
        elements.currentSessionTitle.textContent = topic.substring(0, 30) + (topic.length > 30 ? '...' : '');
        enableControls(true);

        // 重新加载会话列表
        await loadSessions();

        // 关闭弹窗
        closeModal(elements.newSessionModal);

        // 清空消息区
        elements.chatMessages.innerHTML = '';

        // 开始轮询
        startStatusPolling();

        showToast('会话创建成功', 'success');
    } catch (error) {
        console.error('Failed to create session:', error);
        showToast('创建会话失败', 'error');
    }
}

// 开始聊天
async function startChat() {
    const topic = elements.topicInput.value.trim();
    if (!topic) {
        showToast('请输入牵引主题', 'error');
        return;
    }

    const stopConditionType = elements.stopConditionType.value;
    const stopConditionValue = parseInt(elements.stopConditionValue.value);

    try {
        const response = await fetch(`${API_BASE}/api/chat/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSession.id,
                topic_summary: currentTopicSummary,  // 使用创建会话时的topic_summary
                topic: topic,  // 当前的牵引主题（可修改）
                stop_condition: {
                    type: stopConditionType,
                    value: stopConditionValue
                },
                custom_prompt: elements.customPrompt.value
            })
        });

        const data = await response.json();
        if (data.success) {
            currentTopicSummary = data.topic_summary;
            saveSessionState();
            updateStatus('running', 0, 0, 0);
            enableControls(false, true, false);
            startStatusPolling();
            showToast('对话已启动', 'success');
        }
    } catch (error) {
        console.error('Failed to start chat:', error);
        showToast('启动对话失败', 'error');
    }
}

// 暂停聊天
async function pauseChat() {
    try {
        await fetch(`${API_BASE}/api/chat/pause`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: currentSession.id })
        });
        updateStatus('paused');
        enableControls(true, false, true);
        showToast('对话已暂停', 'info');
    } catch (error) {
        console.error('Failed to pause chat:', error);
    }
}

// 停止聊天
async function stopChat() {
    try {
        await fetch(`${API_BASE}/api/chat/stop`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSession.id,
                topic_summary: currentTopicSummary
            })
        });
        updateStatus('stopped');
        enableControls(true, false, true);

        // 重新加载消息
        await loadMessages(currentSession.id, currentTopicSummary);

        showToast('对话已终止', 'info');
    } catch (error) {
        console.error('Failed to stop chat:', error);
    }
}

// 总结对话
async function summarizeChat() {
    if (!currentSession || !currentTopicSummary) {
        showToast('请先选择会话', 'error');
        return;
    }

    elements.summarizeBtn.disabled = true;
    elements.summarizeBtn.textContent = '⏳ 总结中...';

    try {
        const response = await fetch(`${API_BASE}/api/chat/summarize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSession.id,
                topic_summary: currentTopicSummary
            })
        });

        const data = await response.json();
        if (data.success) {
            // 重新加载消息（包含总结）
            await loadMessages(currentSession.id, currentTopicSummary);
            showToast('总结已完成', 'success');
        } else {
            showToast(data.error || '总结失败', 'error');
        }
    } catch (error) {
        console.error('Failed to summarize:', error);
        showToast('总结失败', 'error');
    } finally {
        elements.summarizeBtn.disabled = false;
        elements.summarizeBtn.textContent = '📝 总结';
    }
}

// 导出对话
async function exportChat() {
    if (!currentTopicSummary) {
        showToast('请先选择会话', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/export/${currentTopicSummary}`);
        const data = await response.json();

        if (data.content) {
            // 创建下载
            const blob = new Blob([data.content], { type: 'text/markdown;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${currentTopicSummary}.md`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showToast('导出成功', 'success');
        } else {
            showToast('无内容可导出', 'error');
        }
    } catch (error) {
        console.error('Failed to export:', error);
        showToast('导出失败', 'error');
    }
}

// 状态轮询 - 使用SSE替代轮询
function startStatusPolling() {
    // 清除之前的轮询和SSE
    if (statusPollInterval) {
        clearInterval(statusPollInterval);
        statusPollInterval = null;
    }
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }

    if (!currentSession || !currentTopicSummary) return;

    const startTime = Date.now();

    // 建立SSE连接监听新消息
    eventSource = new EventSource(`${API_BASE}/api/chat/stream/${currentSession.id}?topic_summary=${currentTopicSummary}`);

    eventSource.onmessage = async (event) => {
        try {
            const data = JSON.parse(event.data);

            if (data.type === 'thinking') {
                // 当前模型正在思考
                updateStatus('running', 0, 0, 0, data.model_alias);
            } else if (data.type === 'message') {
                // 有新消息，刷新消息列表
                await loadMessages(currentSession.id, currentTopicSummary);
            } else if (data.type === 'stopped') {
                // 对话停止
                updateStatus('stopped');
                enableControls(true, false, true);
                await loadMessages(currentSession.id, currentTopicSummary);
            }
        } catch (error) {
            console.error('Failed to parse SSE message:', error);
        }
    };

    eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        // SSE断开时，降级到轮询
        startStatusPollingFallback(startTime);
        eventSource.close();
        eventSource = null;
    };

    // 同时启动一个轮询用于更新状态（因为SSE只负责消息更新）
    statusPollInterval = setInterval(async () => {
        if (!currentSession || !currentTopicSummary) return;

        try {
            const response = await fetch(`${API_BASE}/api/chat/status/${currentSession.id}?topic_summary=${currentTopicSummary}`);
            const data = await response.json();

            updateStatus(
                data.is_running ? 'running' : data.status,
                data.current_round || 0,
                Math.floor((Date.now() - startTime) / 1000),
                data.total_tokens || 0,
                data.current_model || null
            );

            if (data.is_running) {
                enableControls(false, true, true); // 运行中：可以暂停和停止
            }

            if (!data.is_running && data.status === 'stopped') {
                enableControls(true, false, true); // 停止后可总结
                clearInterval(statusPollInterval);
            }
        } catch (error) {
            console.error('Failed to poll status:', error);
        }
    }, 2000);
}

function startStatusPollingFallback(startTime) {
    // 降级轮询方案
    if (statusPollInterval) return;

    statusPollInterval = setInterval(async () => {
        if (!currentSession || !currentTopicSummary) return;

        try {
            const response = await fetch(`${API_BASE}/api/chat/status/${currentSession.id}?topic_summary=${currentTopicSummary}`);
            const data = await response.json();

            updateStatus(
                data.is_running ? 'running' : data.status,
                data.current_round || 0,
                Math.floor((Date.now() - startTime) / 1000),
                data.total_tokens || 0,
                data.current_model || null
            );

            if (data.is_running) {
                await loadMessages(currentSession.id, currentTopicSummary);
                enableControls(false, true, true);
            }

            if (!data.is_running && data.status === 'stopped') {
                enableControls(true, false, true);
                await loadMessages(currentSession.id, currentTopicSummary);
                clearInterval(statusPollInterval);
            }
        } catch (error) {
            console.error('Failed to poll status:', error);
        }
    }, 2000);
}

function updateStatus(status, round = 0, seconds = 0, tokens = 0, modelName = null) {
    let statusText;
    if (status === 'running' && modelName) {
        statusText = `🟢 ${modelName} Thinking...`;
    } else {
        const statusMap = {
            'idle': '🔴 空闲',
            'running': '🟢 运行中',
            'paused': '🟡 已暂停',
            'stopped': '🔴 已停止'
        };
        statusText = statusMap[status] || '🔴 空闲';
    }

    elements.statusIndicator.textContent = statusText;
    elements.roundIndicator.textContent = `第 ${round} 轮`;
    elements.timeIndicator.textContent = `⏱️ ${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    elements.tokenIndicator.textContent = `🔢 ${tokens.toLocaleString()} tokens`;
}

function enableControls(forStart, forPause = false, forSummarize = false) {
    elements.startBtn.disabled = !forStart;
    elements.pauseBtn.disabled = !forPause;
    elements.summarizeBtn.disabled = !forSummarize;
    // 导出按钮：有session时即可使用
    const hasSession = currentSession !== null;
    elements.exportBtn.disabled = !hasSession;
    // 追问按钮：有session时即可使用
    elements.questionInput.disabled = !hasSession;
    elements.sendQuestionBtn.disabled = !hasSession;
}

// 追问
async function sendQuestion() {
    const question = elements.questionInput.value.trim();
    if (!question) return;

    try {
        await fetch(`${API_BASE}/api/chat/question`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSession.id,
                question: question
            })
        });

        elements.questionInput.value = '';
        showToast('追问已添加', 'success');

        // 刷新消息列表
        await loadMessages(currentSession.id, currentTopicSummary);
    } catch (error) {
        console.error('Failed to send question:', error);
    }
}

// 删除会话
let sessionToDelete = null;

function showDeleteConfirmation(sessionId, topicSummary) {
    sessionToDelete = { sessionId, topicSummary };
    elements.deleteSessionModal.classList.add('active');
}

async function confirmDeleteSession() {
    if (!sessionToDelete) return;

    try {
        await fetch(`${API_BASE}/api/sessions/${sessionToDelete.sessionId}?topic_summary=${sessionToDelete.topicSummary}`, {
            method: 'DELETE'
        });

        if (currentSession?.id === sessionToDelete.sessionId) {
            currentSession = null;
            currentTopicSummary = null;
            saveSessionState();
            elements.currentSessionTitle.textContent = '选择或新建会话';
            elements.chatMessages.innerHTML = `
                <div class="welcome-message">
                    <h1>🎉 欢迎使用 MultiAI 对话系统</h1>
                    <p>选择左侧会话或新建会话开始多模型协同对话</p>
                </div>
            `;
            enableControls(true, false, false);
        }

        await loadSessions();
        closeModal(elements.deleteSessionModal);
        showToast('会话已删除', 'success');
    } catch (error) {
        console.error('Failed to delete session:', error);
    }
}

// 模态框
function openModal(modal) {
    modal.classList.add('active');
}

function closeModal(modal) {
    modal.classList.remove('active');
}

// 工具函数
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatTime(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

// 事件监听
function setupEventListeners() {
    // 新建会话
    elements.newSessionBtn.addEventListener('click', () => {
        elements.newTopicInput.value = '';
        openModal(elements.newSessionModal);
        elements.newTopicInput.focus();
    });

    elements.closeNewSessionModal.addEventListener('click', () => closeModal(elements.newSessionModal));
    elements.cancelNewSession.addEventListener('click', () => closeModal(elements.newSessionModal));
    elements.confirmNewSession.addEventListener('click', () => createSession(elements.newTopicInput.value));

    elements.newTopicInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            createSession(elements.newTopicInput.value);
        }
    });

    // 删除会话
    elements.closeDeleteModal.addEventListener('click', () => closeModal(elements.deleteSessionModal));
    elements.cancelDelete.addEventListener('click', () => closeModal(elements.deleteSessionModal));
    elements.confirmDelete.addEventListener('click', confirmDeleteSession);

    // 设置按钮
    elements.settingsBtn.addEventListener('click', () => {
        window.location.href = '/settings';
    });

    // 控制按钮
    elements.startBtn.addEventListener('click', startChat);
    elements.pauseBtn.addEventListener('click', pauseChat);
    elements.summarizeBtn.addEventListener('click', summarizeChat);
    elements.exportBtn.addEventListener('click', exportChat);

    // 追问
    elements.sendQuestionBtn.addEventListener('click', sendQuestion);
    elements.questionInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendQuestion();
        }
    });

    // 模态框点击外部关闭
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal(modal);
            }
        });
    });

    // 主题输入
    elements.topicInput.addEventListener('input', () => {
        if (currentSession) {
            enableControls(true, false, false);
        }
    });

    // 自定义Prompt自动保存
    elements.customPrompt.addEventListener('input', saveCustomPrompt);
}

// 快捷键
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl+N: 新建会话
        if (e.ctrlKey && e.key === 'n') {
            e.preventDefault();
            elements.newSessionBtn.click();
        }

        // Ctrl+R: 重启循环
        if (e.ctrlKey && e.key === 'r') {
            e.preventDefault();
            if (currentSession) {
                stopChat();
                setTimeout(startChat, 500);
            }
        }

        // Ctrl+Q: 追问
        if (e.ctrlKey && e.key === 'q') {
            e.preventDefault();
            if (!elements.questionInput.disabled) {
                elements.questionInput.focus();
            }
        }

        // Esc: 暂停
        if (e.key === 'Escape') {
            if (!elements.pauseBtn.disabled) {
                pauseChat();
            }
        }
    });
}

// 启动
document.addEventListener('DOMContentLoaded', init);
