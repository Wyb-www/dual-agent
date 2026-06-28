"""Pydantic 数据模型 — 全链路类型安全"""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


# --- Request / Response ---

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    success_criteria: Optional[str] = Field(
        default=None,
        description="用户定义的成功标准，不填则使用默认值"
    )


class SourceInfo(BaseModel):
    """Agent 使用的工具/来源信息"""
    tool_name: str
    tool_input: str
    tool_output: str


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str
    sources: Optional[List[SourceInfo]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ChatResponse(BaseModel):
    message: ChatMessage
    session_id: str
    iterations: int = Field(description="Worker-Evaluator 循环次数")
    success_criteria_met: bool


class SessionInfo(BaseModel):
    session_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int


# --- Agent State (used by LangGraph) ---

class AgentState(BaseModel):
    """可序列化的 Agent 状态快照"""
    session_id: str
    messages: List[ChatMessage] = []
    feedback_on_work: Optional[str] = None
    success_criteria_met: bool = False
    user_input_needed: bool = False
    iteration_count: int = 0


# --- Evaluator structured output ---

class EvaluatorOutput(BaseModel):
    feedback: str = Field(description="对 Worker 回复的反馈意见")
    success_criteria_met: bool = Field(description="是否满足成功标准")
    user_input_needed: bool = Field(description="是否需要用户补充信息")


# --- Health ---

class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    llm_model: str
    version: str
