"""Pydantic 数据模型"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class APIType(str, Enum):
    OPENAI = "OpenAI"
    CLAUDE = "Claude"
    OLLAMA = "Ollama"
    QWEN = "Qwen"
    CUSTOM = "Custom"


class StopConditionType(str, Enum):
    ROUNDS = "rounds"
    DURATION = "duration"
    TOKENS = "tokens"


class ModelConfig(BaseModel):
    id: Optional[str] = None
    alias: str
    model_name: str
    api_type: APIType
    base_url: str
    api_key: str = ""
    default_prompt: str = ""
    enabled: bool = True
    is_default: bool = False


class ModelsConfig(BaseModel):
    models: List[ModelConfig] = []
    settings: dict = {}


class Message(BaseModel):
    id: Optional[int] = None
    session_id: str
    role: str  # user, assistant, system
    content: str
    model_alias: Optional[str] = None
    model_name: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    tokens: Optional[int] = None


class Session(BaseModel):
    id: str
    name: str
    topic: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    status: str = "idle"  # idle, running, paused, stopped
    current_round: int = 0


class TopicFile(BaseModel):
    session_id: str
    topic: str
    topic_summary: str
    file_path: str


class StopCondition(BaseModel):
    type: StopConditionType = StopConditionType.ROUNDS
    value: int = 5


class ChatRequest(BaseModel):
    session_id: str
    topic_summary: Optional[str] = None
    topic: str
    stop_condition: StopCondition = Field(default_factory=StopCondition())
    custom_prompt: Optional[str] = None


class QuestionRequest(BaseModel):
    session_id: str
    question: str


class CreateSessionRequest(BaseModel):
    topic: str


class TestConnectionRequest(BaseModel):
    config: ModelConfig
