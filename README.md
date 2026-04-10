# MultiAI 对话系统

一个开源、本地优先的多大模型协同对话系统。

## 功能特性

- 🎯 牵引主题驱动多AI协同思考
- 🤖 支持 OpenAI / Claude / Ollama / Qwen 等多模型混搭
- 📝 自动沉淀为结构化 Markdown 日志
- 🔒 本地优先，API Key安全存储
- ⚡ 支持快捷键操作

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动后端服务

```bash
cd backend
python main.py
```

### 3. 打开前端

在浏览器中打开 `frontend/index.html`

## 项目结构

```
MultiChat/
├── backend/
│   ├── main.py           # FastAPI 后端入口
│   ├── config.py         # 配置管理
│   ├── models.py         # Pydantic 数据模型
│   ├── database.py       # SQLite 数据库操作
│   ├── api_handler.py    # AI API 调用处理
│   └── file_storage.py   # 文件存储管理
├── frontend/
│   ├── index.html        # 主对话页面
│   ├── settings.html     # 全局配置页面
│   ├── css/style.css     # 样式文件
│   └── js/app.js         # 前端逻辑
├── data/
│   ├── config/           # 配置文件
│   └── topics/           # 话题日志
├── requirements.txt
└── README.md
```

## 使用说明

### 添加模型配置

1. 点击右上角「设置」按钮
2. 在模型配置表格中添加 API 信息
3. 点击「测试连接」验证配置
4. 保存配置

### 开始对话

1. 在左侧新建会话
2. 输入「牵引主题」
3. 配置循环条件（轮数/时长/Token上限）
4. 点击「启动」开始多模型协同对话

### 快捷键

- `Ctrl+N` 新建会话
- `Ctrl+R` 重启循环
- `Ctrl+Q` 追问
- `Esc` 暂停

## 许可证

MIT License
