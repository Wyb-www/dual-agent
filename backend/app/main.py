"""FastAPI 应用入口"""

import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from langchain_openai import ChatOpenAI

from app.core.config import get_config
from app.core.logger import logger
from app.core.models import HealthResponse
from app.agent.graph import MultiAgentGraph
from app.db.store import ConversationStore
from app.api import chat


# ---- 生命周期 ----

@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化 Agent 和数据库，关闭时清理"""
    config = get_config()
    logger.info(f"启动 {config.app.name} v{config.app.version}")

    # 初始化 LLM
    if config.llm.provider == "ollama":
        llm = ChatOpenAI(
            model=config.ollama.model,
            base_url=f"{config.ollama.api_base}/v1",
            api_key="ollama",  # Ollama 不需要真实 key
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
        )
        logger.info(f"LLM: Ollama/{config.ollama.model}")
    else:
        llm = ChatOpenAI(
            model=config.llm.model,
            base_url=config.llm.api_base,
            api_key=config.llm.api_key,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
        )
        logger.info(f"LLM: {config.llm.provider}/{config.llm.model}")

    # 初始化 Agent 图
    agent = MultiAgentGraph(
        llm=llm,
        enable_search=config.tools.enable_search,
        enable_wikipedia=config.tools.enable_wikipedia,
        max_iterations=config.agent.max_iterations,
    )

    # 初始化数据库
    db = ConversationStore(db_path=config.database.path)

    # 注入到 API 模块
    chat.agent_graph = agent
    chat.store = db

    logger.info("所有组件初始化完成")
    yield

    # 关闭
    logger.info("服务关闭")


# ---- 应用 ----

app = FastAPI(
    title="Dual Agent",
    description="Worker + Evaluator 多 Agent 协作系统，基于 LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(chat.router)


@app.get("/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    config = get_config()
    return HealthResponse(
        status="ok",
        llm_provider=config.llm.provider,
        llm_model=config.llm.model,
        version=config.app.version,
    )


if __name__ == "__main__":
    import uvicorn
    config = get_config()
    uvicorn.run(
        "app.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.app.debug,
    )
