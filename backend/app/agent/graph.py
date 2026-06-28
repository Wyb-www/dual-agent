"""LangGraph StateGraph — Worker↔Evaluator 自纠正循环"""

from typing import Dict, Any, List, Optional, AsyncIterator
import uuid

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from app.agent.state import AgentState
from app.agent.tools import BUILTIN_TOOLS, load_extended_tools
from app.agent.evaluator import Evaluator
from app.core.models import EvaluatorOutput
from app.core.logger import logger


WORKER_SYSTEM_PROMPT = """你是一个能力全面的 AI 助手，名为 Multi-Agent Collab。

你的工作流程：
1. 理解用户任务和成功标准
2. 使用可用工具完成任务（需要时）
3. 给出完整、准确的回答
4. 由评估者检查你的工作——如果不达标，你会收到反馈并改进

约束：
- 每次只调用一个工具（如果需要）
- 工具调用后仔细分析结果再回复
- 如果无法完成，诚实说明原因
- 回复使用中文（除非用户要求其他语言）

{feedback_section}
成功标准：
{success_criteria}"""


class MultiAgentGraph:
    """Worker + Evaluator 多 Agent 协作图

    流程: START → Worker → (tools?) → Evaluator → (loop/END)
    """

    def __init__(
        self,
        llm: BaseChatModel,
        enable_search: bool = False,
        enable_wikipedia: bool = True,
        max_iterations: int = 5,
    ):
        self.llm = llm
        self.max_iterations = max_iterations
        self.evaluator = Evaluator(llm)

        # 组装工具集
        self.tools = list(BUILTIN_TOOLS)
        ext_tools = load_extended_tools(enable_search, enable_wikipedia)
        self.tools.extend(ext_tools)

        # Worker LLM（绑定工具）
        self.worker_llm = llm.bind_tools(self.tools)

        # 编译图
        self.memory = MemorySaver()
        self.graph: CompiledStateGraph = self._build_graph()
        logger.info(f"Agent 图已编译 | 工具数={len(self.tools)} | 最大迭代={max_iterations}")

    # ---- 节点 ----

    def _worker_node(self, state: AgentState) -> Dict[str, Any]:
        """Worker: 执行任务 + 调用工具"""
        iteration = state.get("iteration_count", 0) + 1
        if iteration > self.max_iterations:
            return {
                "messages": [AIMessage(content="已达到最大迭代次数，以下是当前最佳回答。")],
                "success_criteria_met": True,
            }

        # 构建 System prompt
        feedback = state.get("feedback_on_work", "")
        feedback_section = ""
        if feedback:
            feedback_section = f"\n⚠️ 上次评估未通过，请根据以下反馈改进：\n{feedback}\n"

        system_msg = WORKER_SYSTEM_PROMPT.format(
            feedback_section=feedback_section,
            success_criteria=state["success_criteria"],
        )

        messages = state["messages"]
        has_system = any(isinstance(m, SystemMessage) for m in messages)
        if has_system:
            # 更新已有的 system message
            for m in messages:
                if isinstance(m, SystemMessage):
                    m.content = system_msg
            msgs_to_send = messages
        else:
            msgs_to_send = [SystemMessage(content=system_msg)] + messages

        logger.info(f"Worker 第 {iteration} 轮推理开始")
        response = self.worker_llm.invoke(msgs_to_send)
        return {
            "messages": [response],
            "iteration_count": iteration,
        }

    def _router(self, state: AgentState) -> str:
        """Worker 输出后：走工具还是走评估？"""
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            logger.info(f"→ 路由到工具节点 ({len(last.tool_calls)} 个调用)")
            return "tools"
        logger.info("→ 路由到评估节点")
        return "evaluator"

    def _evaluator_node(self, state: AgentState) -> Dict[str, Any]:
        """Evaluator: 检查 Worker 输出"""
        messages = state["messages"]
        last_text = getattr(messages[-1], "content", "") or ""

        result: EvaluatorOutput = self.evaluator.evaluate(
            messages=messages,
            success_criteria=state["success_criteria"],
            last_response=last_text,
        )

        feedback_msg = AIMessage(content=f"📋 评估反馈: {result.feedback}")
        return {
            "messages": [feedback_msg],
            "feedback_on_work": result.feedback,
            "success_criteria_met": result.success_criteria_met,
            "user_input_needed": result.user_input_needed,
        }

    def _post_eval_router(self, state: AgentState) -> str:
        """评估后：结束 or 回 Worker 重试？"""
        if state["success_criteria_met"] or state["user_input_needed"]:
            logger.info(f"→ 结束 | 达标={state['success_criteria_met']} | 需追问={state['user_input_needed']}")
            return END
        if state.get("iteration_count", 0) >= self.max_iterations:
            logger.info("→ 达到最大迭代次数，强制结束")
            return END
        logger.info("→ 返回 Worker 重试")
        return "worker"

    # ---- 构建图 ----

    def _build_graph(self) -> CompiledStateGraph:
        gb = StateGraph(AgentState)

        gb.add_node("worker", self._worker_node)
        gb.add_node("tools", ToolNode(tools=self.tools))
        gb.add_node("evaluator", self._evaluator_node)

        gb.add_conditional_edges("worker", self._router, {
            "tools": "tools",
            "evaluator": "evaluator",
        })
        gb.add_edge("tools", "worker")
        gb.add_conditional_edges("evaluator", self._post_eval_router, {
            "worker": "worker",
            END: END,
        })
        gb.add_edge(START, "worker")

        return gb.compile(checkpointer=self.memory)

    # ---- 对外接口 ----

    async def arun(
        self,
        message: str,
        success_criteria: str = "给出清晰、准确、有帮助的回答",
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """异步运行 Agent，返回完整结果"""
        if session_id is None:
            session_id = str(uuid.uuid4())

        config = {"configurable": {"thread_id": session_id}}

        initial_state: AgentState = {
            "messages": [HumanMessage(content=message)],
            "success_criteria": success_criteria,
            "feedback_on_work": None,
            "success_criteria_met": False,
            "user_input_needed": False,
            "iteration_count": 0,
        }

        result = await self.graph.ainvoke(initial_state, config=config)

        # 提取最终回复（去掉反馈消息）
        final_messages = []
        for m in result["messages"]:
            if isinstance(m, AIMessage):
                content = m.content or ""
                if not content.startswith("📋 评估反馈:"):
                    final_messages.append(m)

        last_ai = final_messages[-1] if final_messages else result["messages"][-1]

        return {
            "content": last_ai.content if hasattr(last_ai, "content") else str(last_ai),
            "session_id": session_id,
            "iterations": result.get("iteration_count", 0),
            "success_criteria_met": result["success_criteria_met"],
            "user_input_needed": result["user_input_needed"],
            "feedback": result.get("feedback_on_work", ""),
        }

    async def astream(
        self,
        message: str,
        success_criteria: str = "给出清晰、准确、有帮助的回答",
        session_id: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式运行 Agent，逐步 yield 事件"""
        if session_id is None:
            session_id = str(uuid.uuid4())

        config = {"configurable": {"thread_id": session_id}}

        initial_state: AgentState = {
            "messages": [HumanMessage(content=message)],
            "success_criteria": success_criteria,
            "feedback_on_work": None,
            "success_criteria_met": False,
            "user_input_needed": False,
            "iteration_count": 0,
        }

        async for event in self.graph.astream(initial_state, config=config):
            # event: {node_name: state_update}
            for node_name, update in event.items():
                if node_name == "worker":
                    msgs = update.get("messages", [])
                    for m in msgs:
                        if hasattr(m, "tool_calls") and m.tool_calls:
                            for tc in m.tool_calls:
                                yield {
                                    "type": "tool_call",
                                    "tool": tc.get("name", "unknown"),
                                    "args": tc.get("args", {}),
                                }
                        elif hasattr(m, "content") and m.content:
                            content = m.content
                            if not content.startswith("📋 评估反馈:"):
                                yield {"type": "content", "content": content}
                elif node_name == "evaluator":
                    yield {"type": "evaluating", "content": "正在评估回复质量..."}
                elif node_name == "tools":
                    yield {"type": "tool_result", "content": "工具执行完成"}

        yield {"type": "done", "session_id": session_id}
