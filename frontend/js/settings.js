// MultiAI 对话系统 - 设置页面 JavaScript

const API_BASE = 'http://localhost:8000';

// DOM 元素
const elements = {
    modelsTableBody: document.getElementById('modelsTableBody'),
    addModelBtn: document.getElementById('addModelBtn'),
    importModelsBtn: document.getElementById('importModelsBtn'),
    exportModelsBtn: document.getElementById('exportModelsBtn'),
    saveSettingsBtn: document.getElementById('saveSettingsBtn'),
    logPath: document.getElementById('logPath'),
    maxTokens: document.getElementById('maxTokens'),

    // 模型弹窗
    modelModal: document.getElementById('modelModal'),
    modelModalTitle: document.getElementById('modelModalTitle'),
    closeModelModal: document.getElementById('closeModelModal'),
    cancelModelModal: document.getElementById('cancelModelModal'),
    saveModelBtn: document.getElementById('saveModelBtn'),
    testConnectionBtn: document.getElementById('testConnectionBtn'),
    testResult: document.getElementById('testResult'),
    modelId: document.getElementById('modelId'),
    modelAlias: document.getElementById('modelAlias'),
    modelName: document.getElementById('modelName'),
    apiType: document.getElementById('apiType'),
    baseUrl: document.getElementById('baseUrl'),
    apiKey: document.getElementById('apiKey'),
    defaultPrompt: document.getElementById('defaultPrompt'),
    modelEnabled: document.getElementById('modelEnabled'),
    modelDefault: document.getElementById('modelDefault'),

    // 导入弹窗
    importModal: document.getElementById('importModal'),
    closeImportModal: document.getElementById('closeImportModal'),
    cancelImport: document.getElementById('cancelImport'),
    confirmImport: document.getElementById('confirmImport'),
    importTextarea: document.getElementById('importTextarea'),

    // 导出弹窗
    exportModal: document.getElementById('exportModal'),
    closeExportModal: document.getElementById('closeExportModal'),
    closeExport: document.getElementById('closeExport'),
    exportTextarea: document.getElementById('exportTextarea'),
    copyExportBtn: document.getElementById('copyExportBtn')
};

// Toast 通知
function showToast(message, type = 'info') {
    let toast = document.getElementById('toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.className = 'toast';
        toast.id = 'toast';
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    setTimeout(() => {
        toast.className = 'toast';
    }, 3000);
}

// 初始化
async function init() {
    await loadModels();
    await loadSettings();
    setupEventListeners();
}

// 加载模型列表
async function loadModels() {
    try {
        const response = await fetch(`${API_BASE}/api/models`);
        const data = await response.json();
        renderModelsTable(data.models || []);
    } catch (error) {
        console.error('Failed to load models:', error);
        renderModelsTable([]);
    }
}

// 渲染模型表格
function renderModelsTable(models) {
    if (models.length === 0) {
        elements.modelsTableBody.innerHTML = `
            <tr class="empty-row">
                <td colspan="8">暂无模型配置，点击"添加模型"开始</td>
            </tr>
        `;
        return;
    }

    elements.modelsTableBody.innerHTML = models.map(model => `
        <tr data-model-id="${model.id}">
            <td>${escapeHtml(model.alias)}</td>
            <td>${escapeHtml(model.model_name)}</td>
            <td>${escapeHtml(model.api_type)}</td>
            <td>${escapeHtml(model.base_url)}</td>
            <td>${maskApiKey(model.api_key)}</td>
            <td>${escapeHtml(model.default_prompt || '-')}</td>
            <td>${model.enabled ? '✅' : '❌'}</td>
            <td>
                <div class="action-btns">
                    <button class="btn btn-secondary edit-btn" data-model-id="${model.id}">编辑</button>
                    <button class="btn btn-danger delete-btn" data-model-id="${model.id}">删除</button>
                </div>
            </td>
        </tr>
    `).join('');

    // 绑定编辑按钮
    document.querySelectorAll('.edit-btn').forEach(btn => {
        btn.addEventListener('click', () => editModel(btn.dataset.modelId));
    });

    // 绑定删除按钮
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', () => deleteModel(btn.dataset.modelId));
    });
}

// 加载设置
async function loadSettings() {
    try {
        const response = await fetch(`${API_BASE}/api/settings`);
        const data = await response.json();
        elements.maxTokens.value = data.max_tokens_per_request || 4096;
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

// 添加模型
function showAddModelModal() {
    elements.modelModalTitle.textContent = '添加模型';
    elements.modelId.value = '';
    elements.modelAlias.value = '';
    elements.modelName.value = '';
    elements.apiType.value = 'OpenAI';
    elements.baseUrl.value = 'https://api.openai.com/v1';
    elements.apiKey.value = '';
    elements.defaultPrompt.value = '';
    elements.modelEnabled.checked = true;
    elements.modelDefault.checked = false;
    elements.testResult.className = 'test-result';
    elements.testResult.style.display = 'none';
    openModal(elements.modelModal);
}

// 编辑模型
async function editModel(modelId) {
    try {
        const response = await fetch(`${API_BASE}/api/models`);
        const data = await response.json();
        const model = data.models.find(m => m.id === modelId);

        if (model) {
            elements.modelModalTitle.textContent = '编辑模型';
            elements.modelId.value = model.id;
            elements.modelAlias.value = model.alias;
            elements.modelName.value = model.model_name;
            elements.apiType.value = model.api_type;
            elements.baseUrl.value = model.base_url;
            elements.apiKey.value = model.api_key;
            elements.defaultPrompt.value = model.default_prompt || '';
            elements.modelEnabled.checked = model.enabled;
            elements.modelDefault.checked = model.is_default || false;
            elements.testResult.className = 'test-result';
            elements.testResult.style.display = 'none';
            openModal(elements.modelModal);
        }
    } catch (error) {
        console.error('Failed to load model:', error);
    }
}

// 保存模型
async function saveModel() {
    const modelId = elements.modelId.value.trim();
    const model = {
        alias: elements.modelAlias.value,
        model_name: elements.modelName.value,
        api_type: elements.apiType.value,
        base_url: elements.baseUrl.value,
        api_key: elements.apiKey.value,
        default_prompt: elements.defaultPrompt.value,
        enabled: elements.modelEnabled.checked,
        is_default: elements.modelDefault.checked
    };

    if (!model.alias || !model.model_name || !model.base_url) {
        showToast('请填写必填项', 'error');
        return;
    }

    try {
        let url, method;
        if (modelId) {
            model.id = modelId;
            url = `${API_BASE}/api/models/${modelId}`;
            method = 'PUT';
        } else {
            model.id = generateId();
            url = `${API_BASE}/api/models`;
            method = 'POST';
        }

        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(model)
        });

        if (response.ok) {
            closeModal(elements.modelModal);
            await loadModels();
            showToast('保存成功', 'success');
        } else {
            showToast('保存失败', 'error');
        }
    } catch (error) {
        console.error('Failed to save model:', error);
        showToast('保存失败', 'error');
    }
}

// 删除模型
async function deleteModel(modelId) {
    if (!confirm('确定要删除这个模型吗？')) return;

    try {
        const response = await fetch(`${API_BASE}/api/models/${modelId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            await loadModels();
            showToast('删除成功', 'success');
        } else {
            showToast('删除失败', 'error');
        }
    } catch (error) {
        console.error('Failed to delete model:', error);
        showToast('删除失败', 'error');
    }
}

// 测试连接
async function testConnection() {
    const model = {
        alias: elements.modelAlias.value,
        model_name: elements.modelName.value,
        api_type: elements.apiType.value,
        base_url: elements.baseUrl.value,
        api_key: elements.apiKey.value,
        default_prompt: elements.defaultPrompt.value
    };

    if (!model.model_name || !model.base_url || !model.api_key) {
        showToast('请填写必填项', 'error');
        return;
    }

    elements.testResult.textContent = '测试中...';
    elements.testResult.className = 'test-result';
    elements.testResult.style.display = 'block';

    try {
        const response = await fetch(`${API_BASE}/api/models/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ config: model })
        });

        const data = await response.json();

        if (data.success) {
            elements.testResult.textContent = `✅ ${data.message}`;
            elements.testResult.className = 'test-result success';
        } else {
            elements.testResult.textContent = `❌ ${data.error}`;
            elements.testResult.className = 'test-result error';
        }
    } catch (error) {
        elements.testResult.textContent = `❌ 连接失败: ${error.message}`;
        elements.testResult.className = 'test-result error';
    }
}

// 导入配置
function showImportModal() {
    elements.importTextarea.value = '';
    openModal(elements.importModal);
}

async function importModels() {
    const configStr = elements.importTextarea.value.trim();
    if (!configStr) {
        showToast('请粘贴配置内容', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/models/import`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(configStr)
        });

        if (response.ok) {
            closeModal(elements.importModal);
            await loadModels();
            showToast('导入成功', 'success');
        } else {
            showToast('导入失败', 'error');
        }
    } catch (error) {
        console.error('Failed to import models:', error);
        showToast('导入失败', 'error');
    }
}

// 导出配置
async function showExportModal() {
    try {
        const response = await fetch(`${API_BASE}/api/models/export`);
        const data = await response.json();
        elements.exportTextarea.value = data.config;
        openModal(elements.exportModal);
    } catch (error) {
        console.error('Failed to export models:', error);
    }
}

function copyExportConfig() {
    elements.exportTextarea.select();
    document.execCommand('copy');
    showToast('已复制到剪贴板', 'success');
}

// 保存设置
async function saveSettings() {
    try {
        const response = await fetch(`${API_BASE}/api/settings`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                max_tokens_per_request: parseInt(elements.maxTokens.value) || 4096
            })
        });

        if (response.ok) {
            showToast('设置已保存', 'success');
        }
    } catch (error) {
        console.error('Failed to save settings:', error);
    }
}

// 工具函数
function openModal(modal) {
    modal.classList.add('active');
}

function closeModal(modal) {
    modal.classList.remove('active');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

function maskApiKey(key) {
    if (!key) return '-';
    if (key.length <= 8) return '••••••••';
    return key.substring(0, 4) + '••••••••' + key.substring(key.length - 4);
}

function generateId() {
    return 'model_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// 事件监听
function setupEventListeners() {
    elements.addModelBtn.addEventListener('click', showAddModelModal);
    elements.closeModelModal.addEventListener('click', () => closeModal(elements.modelModal));
    elements.cancelModelModal.addEventListener('click', () => closeModal(elements.modelModal));
    elements.saveModelBtn.addEventListener('click', saveModel);
    elements.testConnectionBtn.addEventListener('click', testConnection);

    elements.importModelsBtn.addEventListener('click', showImportModal);
    elements.closeImportModal.addEventListener('click', () => closeModal(elements.importModal));
    elements.cancelImport.addEventListener('click', () => closeModal(elements.importModal));
    elements.confirmImport.addEventListener('click', importModels);

    elements.exportModelsBtn.addEventListener('click', showExportModal);
    elements.closeExportModal.addEventListener('click', () => closeModal(elements.exportModal));
    elements.closeExport.addEventListener('click', () => closeModal(elements.exportModal));
    elements.copyExportBtn.addEventListener('click', copyExportConfig);

    elements.saveSettingsBtn.addEventListener('click', saveSettings);

    // API类型切换时更新Base URL默认值
    elements.apiType.addEventListener('change', () => {
        const type = elements.apiType.value;
        if (type === 'OpenAI') {
            elements.baseUrl.value = 'https://api.openai.com/v1';
        } else if (type === 'Claude') {
            elements.baseUrl.value = 'https://api.anthropic.com';
        } else if (type === 'Ollama') {
            elements.baseUrl.value = 'http://localhost:11434';
        } else if (type === 'Qwen') {
            elements.baseUrl.value = 'https://dashscope.aliyuncs.com/compatible-mode/v1';
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
}

// 启动
document.addEventListener('DOMContentLoaded', init);
