"""FastAPI 后端服务"""
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from contextlib import asynccontextmanager
import uuid
from datetime import datetime
from typing import Optional, List
import json
import asyncio
from pathlib import Path
import os

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

from models import (
    ModelConfig, ModelsConfig, Session, Message, ChatRequest,
    QuestionRequest, TestConnectionRequest, StopCondition, APIType,
    CreateSessionRequest
)
from config import config_manager
from database import database
from file_storage import file_storage
from api_handler import api_handler


# 存储当前运行状态
running_sessions = {}  # session_id -> running flag
session_locks = {}     # session_id -> asyncio.Lock
current_model = {}     # session_id -> 当前正在调用的模型别名

# SSE 事件订阅者
sse_subscribers = {}  # session_id -> list of asyncio.Queue


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    print("MultiAI 对话系统启动...")
    yield
    # 关闭时清理
    print("MultiAI 对话系统关闭...")


app = FastAPI(title="MultiAI Dialogue System", lifespan=lifespan)

# 挂载静态文件目录
frontend_dir = BASE_DIR / "frontend"
app.mount("/css", StaticFiles(directory=str(frontend_dir / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(frontend_dir / "js")), name="js")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 静态文件服务 ====================

@app.get("/")
async def root():
    return FileResponse(str(frontend_dir / "index.html"))


@app.get("/settings")
async def settings_page():
    return FileResponse(str(frontend_dir / "settings.html"))


# ==================== 会话管理 API ====================

@app.get("/api/sessions")
async def list_sessions():
    """获取所有会话列表"""
    topics = file_storage.list_topics()
    return {"sessions": topics}


@app.post("/api/sessions")
async def create_session(request: CreateSessionRequest):
    """创建新会话"""
    topic = request.topic
    topic_summary = file_storage.get_or_create_topic_summary(topic)
    session_id = str(uuid.uuid4())
    session = Session(
        id=session_id,
        name=topic[:30] + "..." if len(topic) > 30 else topic,
        topic=topic,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        status="idle",
        current_round=0
    )

    database.init_db(topic_summary)
    database.save_session(topic_summary, session)
    session_locks[session_id] = None

    return {"session_id": session_id, "topic_summary": topic_summary}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str, topic_summary: str):
    """获取会话详情"""
    session = database.get_session(topic_summary, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str, topic_summary: str):
    """删除会话"""
    # 清理运行状态
    if session_id in running_sessions:
        running_sessions[session_id] = False
    if session_id in session_locks:
        del session_locks[session_id]

    # 删除文件
    topic_dir = file_storage.get_topic_dir(topic_summary)
    import shutil
    if topic_dir.exists():
        shutil.rmtree(topic_dir)

    return {"success": True}


# ==================== 消息 API ====================

@app.get("/api/messages/{topic_summary}/{session_id}")
async def get_messages(topic_summary: str, session_id: str):
    """获取会话的所有消息"""
    messages = database.get_messages(topic_summary, session_id)
    return {"messages": [m.model_dump() for m in messages]}


# ==================== 模型配置 API ====================

@app.get("/api/models")
async def list_models():
    """获取所有模型配置"""
    config = config_manager.load_models_config()
    return {"models": config.models, "settings": config.settings}


@app.post("/api/models")
async def add_model(model: ModelConfig):
    """添加模型"""
    if not model.id:
        model.id = str(uuid.uuid4())

    if config_manager.add_model(model):
        return {"success": True, "model": model}
    raise HTTPException(status_code=400, detail="Model ID already exists")


@app.put("/api/models/{model_id}")
async def update_model(model_id: str, model: ModelConfig):
    """更新模型"""
    model.id = model_id
    if config_manager.update_model(model):
        return {"success": True, "model": model}
    raise HTTPException(status_code=404, detail="Model not found")


@app.delete("/api/models/{model_id}")
async def delete_model(model_id: str):
    """删除模型"""
    if config_manager.delete_model(model_id):
        return {"success": True}
    raise HTTPException(status_code=404, detail="Model not found")


@app.post("/api/models/test")
async def test_model_connection(request: TestConnectionRequest):
    """测试模型连接"""
    result = await api_handler.test_connection(request.config)
    return result


@app.get("/api/models/export")
async def export_models():
    """导出模型配置"""
    config_str = config_manager.export_config()
    return {"config": config_str}


@app.post("/api/models/import")
async def import_models(config_str: str):
    """导入模型配置"""
    if config_manager.import_config(config_str):
        return {"success": True}
    raise HTTPException(status_code=400, detail="Invalid config format")


# ==================== 对话控制 API ====================

@app.post("/api/chat/start")
async def start_chat(request: ChatRequest):
    """启动牵引式多模型对话"""
    import asyncio

    session_id = request.session_id
    topic = request.topic
    topic_summary_from_request = request.topic_summary
    stop_condition = request.stop_condition

    # 如果有topic_summary（创建会话时确定的），使用它；否则用topic生成新的
    if topic_summary_from_request:
        topic_summary = topic_summary_from_request
        # 如果用户修改了topic，重新写入topic文件
        file_storage.initialize_topic_file(topic_summary, topic)
    else:
        topic_summary = file_storage.get_or_create_topic_summary(topic)

    # 初始化运行状态
    running_sessions[session_id] = True
    lock = asyncio.Lock()
    session_locks[session_id] = lock

    # 获取启用的模型
    enabled_models = config_manager.get_enabled_models()
    if not enabled_models:
        running_sessions[session_id] = False
        raise HTTPException(status_code=400, detail="没有启用的模型")

    # 更新会话状态（只在session不存在时创建）
    session = database.get_session(topic_summary, session_id)
    if not session:
        # 从现有session查找
        found = False
        all_topics = file_storage.list_topics()
        for t in all_topics:
            existing_session = database.get_session(t["summary"], session_id)
            if existing_session:
                topic_summary = t["summary"]
                found = True
                break

        if not found:
            session = Session(
                id=session_id,
                name=topic[:30],
                topic=topic,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                status="running",
                current_round=0
            )
            database.save_session(topic_summary, session)

    database.update_session_status(topic_summary, session_id, "running", 0)
    database.update_session_topic(topic_summary, session_id, topic)

    # 启动后台任务
    asyncio.create_task(
        run_chat_loop(session_id, topic_summary, topic, stop_condition, enabled_models, request.custom_prompt)
    )

    return {"success": True, "topic_summary": topic_summary}


async def run_chat_loop(
    session_id: str,
    topic_summary: str,
    topic: str,
    stop_condition: StopCondition,
    enabled_models: list,
    custom_prompt: Optional[str] = None
):
    """运行对话循环"""
    import asyncio
    import time

    lock = session_locks.get(session_id)
    if not lock:
        lock = asyncio.Lock()
        session_locks[session_id] = lock

    async with lock:
        round_num = 0
        total_tokens = 0
        start_time = time.time()
        max_rounds = stop_condition.value if stop_condition.type.value == "rounds" else 999
        max_duration = stop_condition.value * 60 if stop_condition.type.value == "duration" else 999999
        max_tokens = stop_condition.value * 1000 if stop_condition.type.value == "tokens" else 99999999

        while running_sessions.get(session_id, False):
            # 检查停止条件
            if round_num >= max_rounds:
                break
            if time.time() - start_time >= max_duration:
                break
            if total_tokens >= max_tokens:
                break

            round_num += 1
            database.update_session_status(topic_summary, session_id, "running", round_num)

            # 按顺序调用每个模型（等待上一个完成后才调用下一个）
            for model_config in enabled_models:
                if not running_sessions.get(session_id, False):
                    break

                # 记录当前正在调用的模型
                current_model[session_id] = model_config.alias

                # 通知前端当前正在思考的模型
                await notify_subscribers(session_id, {
                    "type": "thinking",
                    "model_alias": model_config.alias
                })

                # 构建消息历史（每次重新构建，确保读取到最新的文件内容）
                messages, system_prompt = await build_messages(topic_summary, session_id, topic, model_config, round_num, custom_prompt)

                # 调用API
                result = await api_handler.chat(
                    model_config,
                    messages,
                    system_prompt
                )

                if result["success"]:
                    content = result["content"]
                    tokens = result["tokens"]
                    total_tokens += tokens

                    # 保存消息到数据库
                    msg = Message(
                        session_id=session_id,
                        role="assistant",
                        content=content,
                        model_alias=model_config.alias,
                        model_name=model_config.model_name,
                        timestamp=datetime.now(),
                        tokens=tokens
                    )
                    database.save_message(topic_summary, msg)

                    # 追加到Markdown文件（确保写入完成后再继续）
                    file_storage.append_ai_message(
                        topic_summary,
                        model_config.alias,
                        model_config.model_name,
                        content
                    )

                    # 通过SSE通知前端有新消息（等待前端确认收到）
                    await notify_subscribers(session_id, {
                        "type": "message",
                        "topic_summary": topic_summary,
                        "round": round_num,
                        "model_alias": model_config.alias
                    })
                    # 等待一小段时间确保文件写入和前端刷新完成
                    await asyncio.sleep(0.5)
                else:
                    print(f"API Error: {result.get('error')}")

            # 每轮间隔
            await asyncio.sleep(1)

        # 对话结束
        running_sessions[session_id] = False
        current_model.pop(session_id, None)
        database.update_session_status(topic_summary, session_id, "stopped", round_num)


async def build_messages(
    topic_summary: str,
    session_id: str,
    topic: str,
    model_config: ModelConfig,
    round_num: int,
    custom_prompt: Optional[str] = None
) -> tuple:
    """构建发送给API的消息列表，返回 (messages, system_prompt)"""
    messages = []

    # 读取完整的历史对话内容
    history_content = file_storage.read_full_content(topic_summary)

    # 构建消息内容
    content = f"【牵引主题】：{topic}\n\n"

    # 如果有历史对话，直接追加
    if history_content:
        content += f"【历史对话记录】：\n{history_content}"

    messages.append({
        "role": "user",
        "content": content
    })

    # 构建system_prompt
    system_prompt = model_config.default_prompt or ""
    if custom_prompt:
        if system_prompt:
            system_prompt += f"\n\n{custom_prompt}"
        else:
            system_prompt = custom_prompt

    return messages, system_prompt


@app.post("/api/chat/pause")
async def pause_chat(session_id: str):
    """暂停对话"""
    running_sessions[session_id] = False
    return {"success": True}


@app.post("/api/chat/stop")
async def stop_chat(session_id: str, topic_summary: str):
    """终止对话"""
    running_sessions[session_id] = False
    # 通知所有订阅者
    await notify_subscribers(session_id, {"type": "stopped"})
    return {"success": True}


# SSE 端点 - 订阅消息更新
@app.get("/api/chat/stream/{session_id}")
async def chat_stream(session_id: str, topic_summary: str):
    """SSE 流，用于实时推送消息更新"""
    async def event_generator():
        queue = asyncio.Queue()

        # 注册订阅者
        if session_id not in sse_subscribers:
            sse_subscribers[session_id] = []
        sse_subscribers[session_id].append(queue)

        try:
            while True:
                try:
                    # 等待消息，最多等待30秒后发送心跳
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(message)}\n\n"
                except asyncio.TimeoutError:
                    # 发送心跳
                    yield f": heartbeat\n\n"
        finally:
            # 取消订阅
            if session_id in sse_subscribers:
                sse_subscribers[session_id].remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


async def notify_subscribers(session_id: str, message: dict):
    """通知指定session的所有订阅者"""
    if session_id in sse_subscribers:
        for queue in sse_subscribers[session_id]:
            try:
                await queue.put(message)
            except Exception:
                pass


@app.post("/api/chat/summarize")
async def summarize_chat(body: dict):
    """对对话内容进行总结"""
    session_id = body.get("session_id")
    topic_summary = body.get("topic_summary")

    if not session_id or not topic_summary:
        raise HTTPException(status_code=400, detail="session_id and topic_summary are required")

    # 获取所有消息
    messages = database.get_messages(topic_summary, session_id)
    if not messages:
        raise HTTPException(status_code=400, detail="No messages to summarize")

    # 获取会话信息
    session = database.get_session(topic_summary, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 构建总结提示
    conversation_text = "\n".join([
        f"[{msg.role}] {msg.model_alias or 'User'}: {msg.content}"
        for msg in messages
    ])

    summarize_prompt = f"""请基于以下对话内容，生成一个结构化总结：

主题：{session.topic}

对话内容：
{conversation_text}

请生成包含以下内容的总结：
1. 讨论要点
2. 主要观点
3. 结论

请用中文回复。"""

    # 获取启用的模型（使用第一个）
    enabled_models = config_manager.get_enabled_models()
    if not enabled_models:
        raise HTTPException(status_code=400, detail="No enabled models")

    model_config = enabled_models[0]

    # 调用API生成总结
    result = await api_handler.chat(
        model_config,
        [{"role": "user", "content": summarize_prompt}],
        "你是一个专业的对话总结助手。"
    )

    if result["success"]:
        summary_content = result["content"]
        tokens = result["tokens"]

        # 保存总结消息
        msg = Message(
            session_id=session_id,
            role="assistant",
            content=f"【总结】\n{summary_content}",
            model_alias=model_config.alias,
            model_name=model_config.model_name,
            timestamp=datetime.now(),
            tokens=tokens
        )
        database.save_message(topic_summary, msg)

        # 追加到Markdown
        file_storage.append_system_message(topic_summary, f"## 总结\n\n{summary_content}")

        return {"success": True, "summary": summary_content}
    else:
        raise HTTPException(status_code=500, detail=result.get("error", "Summarize failed"))


@app.get("/api/chat/status/{session_id}")
async def get_chat_status(session_id: str, topic_summary: str):
    """获取对话状态"""
    session = database.get_session(topic_summary, session_id)
    is_running = running_sessions.get(session_id, False)
    total_tokens = database.get_total_tokens(topic_summary, session_id)

    return {
        "status": session.status if session else "unknown",
        "is_running": is_running,
        "current_round": session.current_round if session else 0,
        "total_tokens": total_tokens,
        "current_model": current_model.get(session_id, None)
    }


# ==================== 追问 API ====================

@app.post("/api/chat/question")
async def add_question(request: QuestionRequest):
    """添加追问"""
    session_id = request.session_id
    question = request.question

    # 通过 session_id 查找对应的 topic_summary
    topic_summary = database.find_topic_summary_by_session_id(session_id)
    if not topic_summary:
        raise HTTPException(status_code=404, detail="Session not found")

    # 验证 session 存在
    session = database.get_session(topic_summary, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 保存用户追问消息到数据库
    msg = Message(
        session_id=session_id,
        role="user",
        content=question,
        timestamp=datetime.now()
    )
    database.save_message(topic_summary, msg)

    # 追加用户追问到 Markdown 文件
    file_storage.append_user_message(topic_summary, question)

    return {"success": True, "message": "追问已添加"}


# ==================== 设置 API ====================

@app.get("/api/custom-prompt")
async def get_custom_prompt():
    """获取自定义Prompt"""
    prompt_path = Path("./data/userprompt.md")
    if prompt_path.exists():
        content = prompt_path.read_text(encoding="utf-8")
        return {"content": content}
    return {"content": ""}


@app.put("/api/custom-prompt")
async def save_custom_prompt(body: dict):
    """保存自定义Prompt"""
    content = body.get("content", "")
    prompt_path = Path("./data/userprompt.md")
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(content, encoding="utf-8")
    return {"success": True}


@app.get("/api/settings")
async def get_settings():
    """获取设置"""
    settings = config_manager.load_settings()
    return settings


@app.put("/api/settings")
async def update_settings(settings: dict):
    """更新设置"""
    config_manager.save_settings(settings)
    return {"success": True}


# ==================== 导出 API ====================

@app.get("/api/export/{topic_summary}")
async def export_topic(topic_summary: str, format: str = "md"):
    """导出会话"""
    if format == "md":
        content = file_storage.read_full_content(topic_summary)
        return {"content": content, "format": "markdown"}
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5678)
