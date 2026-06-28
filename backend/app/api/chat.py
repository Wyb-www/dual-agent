"""聊天 API — Agent 对话与 SSE 流式"""

import json
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.graph import MultiAgentGraph
from app.core.models import ChatRequest, ChatResponse, ChatMessage, SessionInfo
from app.db.store import ConversationStore
from app.core.logger import logger

router = APIRouter(prefix="/chat", tags=["chat"])

# 由 main.py 注入
agent_graph: Optional[MultiAgentGraph] = None
store: Optional[ConversationStore] = None


def get_graph() -> MultiAgentGraph:
    if agent_graph is None:
        raise HTTPException(500, "Agent 未初始化")
    return agent_graph


def get_store() -> ConversationStore:
    if store is None:
        raise HTTPException(500, "数据库未初始化")
    return store


class SSEMessage(BaseModel):
    type: str
    content: str = ""
    session_id: Optional[str] = None


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """发送消息给 Agent（非流式）"""
    graph = get_graph()
    db = get_store()

    session_id = request.session_id or str(uuid.uuid4())

    # 确保 session 存在
    if db.get_session(session_id) is None:
        db.create_session(session_id)

    # 保存用户消息
    user_msg = ChatMessage(role="user", content=request.message)
    db.add_message(session_id, user_msg)

    # 运行 Agent
    criteria = request.success_criteria or "给出清晰、准确、有帮助的回答"
    result = await graph.arun(
        message=request.message,
        success_criteria=criteria,
        session_id=session_id,
    )

    # 保存 Assistant 回复
    assistant_msg = ChatMessage(
        role="assistant",
        content=result["content"],
    )
    db.add_message(session_id, assistant_msg)

    logger.info(
        f"对话完成 | session={session_id[:8]} | "
        f"迭代={result['iterations']} | 达标={result['success_criteria_met']}"
    )

    return ChatResponse(
        message=assistant_msg,
        session_id=session_id,
        iterations=result["iterations"],
        success_criteria_met=result["success_criteria_met"],
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """发送消息给 Agent（SSE 流式输出）"""
    graph = get_graph()
    db = get_store()

    session_id = request.session_id or str(uuid.uuid4())

    if db.get_session(session_id) is None:
        db.create_session(session_id)

    db.add_message(session_id, ChatMessage(role="user", content=request.message))

    criteria = request.success_criteria or "给出清晰、准确、有帮助的回答"

    async def event_generator():
        full_response = []
        try:
            async for event in graph.astream(
                message=request.message,
                success_criteria=criteria,
                session_id=session_id,
            ):
                event_json = json.dumps(event, ensure_ascii=False)
                yield f"data: {event_json}\n\n"

                if event["type"] == "content":
                    full_response.append(event["content"])

            # 保存完整回复
            db.add_message(session_id, ChatMessage(
                role="assistant",
                content="".join(full_response),
            ))
        except Exception as e:
            logger.error(f"流式输出异常: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话详情（含历史消息）"""
    db = get_store()
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "会话不存在")

    messages = db.get_messages(session_id)
    return {
        "session": session.model_dump(mode="json"),
        "messages": [m.model_dump(mode="json") for m in messages],
    }


@router.get("/sessions")
async def list_sessions(limit: int = Query(20, ge=1, le=100)):
    """列出最近会话"""
    db = get_store()
    sessions = db.list_sessions(limit)
    return {"sessions": [s.model_dump(mode="json") for s in sessions]}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    db = get_store()
    ok = db.delete_session(session_id)
    if not ok:
        raise HTTPException(404, "会话不存在")
    return {"status": "deleted", "session_id": session_id}
