"""Agent 工具集 — 内置 + 可选工具"""

import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Optional

from langchain_core.tools import tool

from app.core.logger import logger


# ============================================================
# 内置工具（始终可用）
# ============================================================

@tool
def get_current_time(_: str = "") -> str:
    """获取当前本地日期和时间，格式为 'YYYY-MM-DD HH:MM:SS'"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def write_file(params: str) -> str:
    """写文本文件。JSON 参数: {"path": "output.txt", "content": "内容"}
    返回写入文件的绝对路径。"""
    try:
        data = json.loads(params) if isinstance(params, str) else params
        path = data.get("path", "output.txt")
        content = data.get("content", "")
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        abs_path = os.path.abspath(path)
        logger.info(f"文件已写入: {abs_path}")
        return abs_path
    except Exception as e:
        logger.error(f"写文件失败: {e}")
        return f"[写文件错误] {e}"


@tool
def execute_python(code: str) -> str:
    """执行 Python 代码并返回 stdout/stderr。用于计算、数据处理等任务。"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        return output.strip() or "(无输出)"
    except subprocess.TimeoutExpired:
        return "[错误] 代码执行超时（30秒）"
    except Exception as e:
        return f"[错误] {e}"


@tool
def read_file(path: str) -> str:
    """读取文本文件内容。参数: 文件路径"""
    try:
        with open(path.strip(), "r", encoding="utf-8") as f:
            content = f.read(5000)  # 最多读 5000 字符
            if len(content) >= 5000:
                content += "\n...(内容过长,已截断)"
            return content
    except FileNotFoundError:
        return f"[错误] 文件不存在: {path}"
    except Exception as e:
        return f"[错误] {e}"


BUILTIN_TOOLS = [get_current_time, write_file, execute_python, read_file]


# ============================================================
# 可选工具（按需加载）
# ============================================================

def load_wikipedia_tool():
    """加载 Wikipedia 查询工具"""
    try:
        from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
        from langchain_community.utilities.wikipedia import WikipediaAPIWrapper
        wiki = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper(top_k_results=2))
        logger.info("Wikipedia 工具已加载")
        return wiki
    except Exception as e:
        logger.warning(f"Wikipedia 工具不可用: {e}")
        return None


def load_search_tool():
    """加载 Google Serper 搜索工具"""
    api_key = os.getenv("SERPER_API_KEY", "")
    if not api_key:
        logger.warning("SERPER_API_KEY 未设置，搜索工具不可用")
        return None
    try:
        from langchain_community.utilities import GoogleSerperAPIWrapper
        from langchain.agents import Tool as LCTool
        serper = GoogleSerperAPIWrapper(serper_api_key=api_key)
        logger.info("Serper 搜索工具已加载")
        return LCTool(
            name="web_search",
            func=serper.run,
            description="搜索互联网获取最新信息"
        )
    except Exception as e:
        logger.warning(f"Serper 搜索工具不可用: {e}")
        return None


def load_extended_tools(enable_search: bool = False, enable_wikipedia: bool = True) -> list:
    """加载可选扩展工具"""
    tools = []
    if enable_wikipedia:
        wiki = load_wikipedia_tool()
        if wiki:
            tools.append(wiki)
    if enable_search:
        search = load_search_tool()
        if search:
            tools.append(search)
    return tools
