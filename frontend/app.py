"""对话界面"""

import os
import uuid
import json
from datetime import datetime
import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(
    page_title="留 言",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- 样式 ----
st.markdown("""
<style>
    header[data-testid="stHeader"] { display: none; }
    .main [data-testid="stVerticalBlock"] { gap: 0; }
    section[data-testid="stSidebar"] > div { padding-top: 0; }

    /* 侧边栏 */
    [data-testid="stSidebar"] {
        background: #1a1d23;
        border-right: 1px solid #2a2d35;
    }
    [data-testid="stSidebar"] .stMarkdown h2 {
        color: #e8e8e8;
        font-size: 1rem;
        font-weight: 700;
        margin: 0;
        padding: 0.5rem 0 0 0.25rem;
    }
    [data-testid="stSidebar"] .stCaption {
        color: #888;
        font-size: 0.75rem;
        padding-left: 0.25rem;
    }
    [data-testid="stSidebar"] hr {
        margin: 0.5rem 0;
        border-color: #2a2d35;
    }
    [data-testid="stSidebar"] button {
        border: 1px solid #33363e;
        border-radius: 8px;
        font-size: 0.85rem;
        background: #22252b;
        color: #ccc;
        font-weight: 500;
    }
    [data-testid="stSidebar"] button:hover {
        border-color: #2563eb;
        background: #1e2a3a;
        color: #60a5fa;
    }

    /* 会话列表 */
    .session-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin: 2px 0;
    }
    .session-label {
        flex: 1;
        padding: 0.4rem 0.6rem;
        border-radius: 6px;
        font-size: 0.82rem;
        color: #999;
        cursor: pointer;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .session-label:hover { background: #252830; color: #ddd; }
    .session-label.active { background: #2a2e38; color: #fff; font-weight: 600; }

    /* 主区域 */
    .chat-container { max-width: 720px; margin: 0 auto; padding: 0 1.5rem; }

    /* 消息 */
    .stChatMessage { padding: 0.3rem 0; background: transparent; }
    [data-testid="stChatMessage"] { background: transparent; border: none; }

    /* 助手 — 白色文字 */
    [data-testid="stChatMessage"][aria-label*="assistant"] .stMarkdown p {
        color: #e0e0e0;
        line-height: 1.8;
        font-size: 0.95rem;
    }

    /* 用户 — 深蓝底气泡 */
    [data-testid="stChatMessage"][aria-label*="user"] .stMarkdown {
        background: #1e3a5f;
        border-radius: 14px;
        padding: 0.5rem 0.9rem;
        display: inline-block;
        max-width: 85%;
    }
    [data-testid="stChatMessage"][aria-label*="user"] .stMarkdown p {
        color: #e0e8f0;
        margin: 0;
        font-size: 0.95rem;
    }

    /* 时间 */
    .msg-time { font-size: 0.7rem; color: #555; margin-top: 2px; padding-left: 4px; }

    /* 欢迎 */
    .welcome { text-align: center; padding: 5rem 1rem; }
    .welcome .icon { font-size: 3rem; margin-bottom: 1.2rem; }
    .welcome .title { font-size: 1.2rem; color: #ddd; font-weight: 600; margin-bottom: 0.3rem; }
    .welcome .subtitle { font-size: 0.85rem; color: #777; line-height: 1.7; }

    /* 输入框 */
    [data-testid="stChatInput"] textarea {
        border: 1px solid #33363e !important;
        border-radius: 16px;
        background: #1a1d23 !important;
        font-size: 0.95rem;
        padding: 0.7rem 1rem;
        color: #e0e0e0 !important;
        box-shadow: none !important;
    }
    [data-testid="stChatInput"] textarea::placeholder { color: #666; }
    [data-testid="stChatInput"] textarea:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 3px rgba(37,99,235,0.15) !important;
    }

    /* 底部 */
    .footer { text-align: center; padding: 1rem; color: #3a3d45; font-size: 0.7rem; }

    /* 滚动条 */
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }
</style>
""", unsafe_allow_html=True)

# ---- 初始化 ----
if "sessions" not in st.session_state:
    st.session_state.sessions = {}
if "current_session" not in st.session_state:
    sid = str(uuid.uuid4())
    st.session_state.current_session = sid
    st.session_state.sessions[sid] = {"title": "新对话", "messages": []}


def cur():
    return st.session_state.sessions[st.session_state.current_session]


def new_chat():
    sid = str(uuid.uuid4())
    st.session_state.current_session = sid
    st.session_state.sessions[sid] = {"title": "新对话", "messages": []}


def del_session(sid):
    if sid in st.session_state.sessions:
        del st.session_state.sessions[sid]
    if sid == st.session_state.current_session:
        keys = list(st.session_state.sessions.keys())
        st.session_state.current_session = keys[-1] if keys else str(uuid.uuid4())
        if not keys:
            st.session_state.sessions[st.session_state.current_session] = {"title": "新对话", "messages": []}


# ---- 侧边栏 ----
with st.sidebar:
    st.markdown("## 留 言")
    st.caption("简洁对话")

    if st.button("＋ 新对话", use_container_width=True):
        new_chat()
        st.rerun()

    st.divider()

    for sid, sdata in reversed(list(st.session_state.sessions.items())):
        title = sdata.get("title", "新对话")

        c1, c2 = st.columns([9, 1])
        with c1:
            if st.button(title, key=f"s_{sid}", use_container_width=True,
                         help="切换到此对话"):
                st.session_state.current_session = sid
                st.rerun()
        with c2:
            if st.button("×", key=f"d_{sid}"):
                del_session(sid)
                st.rerun()

# ---- 主区域 ----
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

msgs = cur()["messages"]

if not msgs:
    st.markdown("""
    <div class="welcome">
        <div class="icon">💬</div>
        <div class="title">有什么我可以帮忙的？</div>
        <div class="subtitle">
            写作 · 翻译 · 编程 · 分析<br>
            随便聊聊吧
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    for msg in msgs:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            st.markdown(
                f'<div class="msg-time">{msg.get("time", "")}</div>',
                unsafe_allow_html=True,
            )

# 输入
if prompt := st.chat_input("发送消息..."):
    now = datetime.now().strftime("%H:%M")

    if cur()["title"] == "新对话":
        cur()["title"] = prompt[:18] + ("..." if len(prompt) > 18 else "")

    msgs.append({"role": "user", "content": prompt, "time": now})

    with st.chat_message("assistant"):
        resp = requests.post(
            f"{BACKEND_URL}/chat/stream",
            json={
                "message": prompt,
                "session_id": st.session_state.current_session,
                "success_criteria": "给出清晰、准确、有帮助的回答",
            },
            stream=True,
            timeout=120,
        )

        ph = st.empty()
        text = ""

        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8")
            if not line.startswith("data: "):
                continue
            evt = json.loads(line[6:])
            if evt["type"] == "content":
                text += evt["content"]
                ph.markdown(text + "▌")
            elif evt["type"] == "error":
                st.error(evt["content"])

        ph.markdown(text)
        st.markdown(f'<div class="msg-time">{now}</div>', unsafe_allow_html=True)
        msgs.append({"role": "assistant", "content": text, "time": now})

st.markdown("</div>", unsafe_allow_html=True)
st.markdown('<div class="footer">留 言 · 简洁对话</div>', unsafe_allow_html=True)
