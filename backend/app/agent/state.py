"""LangGraph Agent 状态定义"""

from typing import Annotated, List, Any, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Agent 状态图的状态定义

    这是 LangGraph StateGraph 的核心数据流，
    每个节点读取此状态、返回部分更新。
    """
    # 对话消息（自动合并新消息）
    messages: Annotated[List[Any], add_messages]

    # 用户定义的成功标准
    success_criteria: str

    # Evaluator 给出的反馈（Worker 下次迭代时参考）
    feedback_on_work: Optional[str]

    # 是否满足成功标准
    success_criteria_met: bool

    # 是否需要向用户追问
    user_input_needed: bool

    # 当前迭代次数（防止死循环）
    iteration_count: int
