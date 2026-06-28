# Multi-Agent Collab — 多 Agent 任务协作框架

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/LangGraph-Agent-orange?logo=langchain&logoColor=white" />
  <img src="https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" />
</p>

<p align="center">
  <b>Worker 执行 · Evaluator 检查 · 自纠正循环 · 多模型后端</b>
</p>

---

## 项目简介

Multi-Agent Collab 是一个基于 **LangGraph** 的多 Agent 任务协作系统。核心创新在于引入 **Worker↔Evaluator 自纠正循环**：

1. **Worker** 接收任务，使用工具执行，给出回复
2. **Evaluator** 检查 Worker 的输出是否满足用户定义的成功标准
3. 不达标 → 反馈回 Worker 改进 → 循环直到达标或达到最大迭代次数

这与传统单次 LLM 调用的关键区别：系统会**自我检查和修正**，不满足标准就重新来。

---

## 核心亮点

| 特性 | 说明 |
|------|------|
| **自纠正循环** | Worker↔Evaluator 迭代，不达标自动重试，上限可配置 |
| **结构化评估** | Evaluator 使用 Pydantic 结构化输出，评估结果可审计 |
| **多模型后端** | 支持 DeepSeek / OpenAI / Ollama 本地模型，YAML 配置切换 |
| **工具调用** | 内置代码执行、文件读写、时间查询；可选 Wikipedia、Web 搜索 |
| **SSE 流式输出** | 实时展示 Worker 推理、工具调用、Evaluator 评估全过程 |
| **SQLite 持久化** | 对话历史落盘，支持会话管理与回溯 |
| **类型安全** | Pydantic 全链路数据校验，杜绝运行时类型错误 |
| **Docker 部署** | Docker Compose 双容器编排，一键启动 |

---

## 技术架构

```
┌─────────────────────────────────────────────────┐
│                   Streamlit UI                    │
│              http://localhost:8501                │
└─────────────────────┬───────────────────────────┘
                      │ REST / SSE
┌─────────────────────▼───────────────────────────┐
│                 FastAPI Backend                   │
│              http://localhost:8000                │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │              LangGraph Agent                  │ │
│  │                                              │ │
│  │   START → Worker → Tools? → Evaluator        │ │
│  │              ↑         ↓          │          │ │
│  │              └─── retry ─────────┘          │ │
│  │                       END                    │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐ │
│  │ SQLite DB│  │ YAML Cfg │  │ Pydantic Models│ │
│  └──────────┘  └──────────┘  └────────────────┘ │
└─────────────────────────────────────────────────┘
```

---

## 快速开始

### 环境要求

- Python 3.11+
- DeepSeek API Key（或 OpenAI / Ollama）

### 本地开发

```bash
# 1. 进入后端
cd backend
pip install -r requirements.txt

# 2. 设置 API Key
# Windows: set DEEPSEEK_API_KEY=sk-...
# macOS/Linux: export DEEPSEEK_API_KEY=sk-...

# 3. 启动后端
python -m uvicorn app.main:app --reload --port 8000

# 4. 新终端，启动前端
cd ../frontend
pip install streamlit requests
streamlit run app.py
```

打开 http://localhost:8501 开始使用。

### Docker 一键启动

```bash
docker-compose up --build
```

---

## API 接口

### 聊天

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/chat/` | 发送消息（非流式） |
| POST | `/chat/stream` | 发送消息（SSE 流式） |
| GET | `/chat/sessions` | 列出会话 |
| GET | `/chat/sessions/{id}` | 获取会话详情 |
| DELETE | `/chat/sessions/{id}` | 删除会话 |

### 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | LLM / 服务状态 |

---

## 配置说明

编辑 `backend/config.yaml`：

```yaml
llm:
  provider: "deepseek"        # deepseek / openai / ollama
  model: "deepseek-chat"
  api_key: "${DEEPSEEK_API_KEY}"

agent:
  max_iterations: 5           # Worker↔Evaluator 最大循环次数

tools:
  enable_wikipedia: true
  enable_search: false        # 需要 SERPER_API_KEY
```

---

## 项目结构

```
multi-agent-collab/
├── backend/
│   ├── app/
│   │   ├── api/chat.py           # 聊天 API (REST + SSE)
│   │   ├── core/
│   │   │   ├── config.py         # YAML 配置管理
│   │   │   ├── models.py         # Pydantic 数据模型
│   │   │   └── logger.py         # 结构化日志
│   │   ├── agent/
│   │   │   ├── graph.py          # LangGraph StateGraph 编排
│   │   │   ├── state.py          # Agent 状态定义
│   │   │   ├── tools.py          # 内置 + 可选工具
│   │   │   └── evaluator.py      # Evaluator 评估逻辑
│   │   ├── db/store.py           # SQLite 持久化
│   │   └── main.py               # FastAPI 应用入口
│   ├── config.yaml
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── app.py                    # Streamlit 对话界面
├── docker-compose.yml
└── README.md
```

---

## License

MIT License
