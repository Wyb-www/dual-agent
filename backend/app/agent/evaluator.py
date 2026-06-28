"""Evaluator — 检查 Worker 输出是否满足成功标准"""

from typing import List, Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.core.models import EvaluatorOutput
from app.core.logger import logger


EVALUATOR_SYSTEM_PROMPT = """你是一个严格的质量评估者。你的任务是：

1. 检查 Assistant 的回复是否满足用户定义的成功标准
2. 给出具体的反馈意见
3. 判断是否需要用户补充信息

注意：
- 如果回复确实满足了标准，标记 success_criteria_met=True
- 如果回复有不足但可以通过迭代改进，给出具体反馈，标记 False
- 只有在问题模糊、信息不足、必须用户参与时，才标记 user_input_needed=True
- 反馈要具体、可执行，不要泛泛而谈"""


class Evaluator:
    """评估 Worker 输出质量"""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        self.llm_with_output = llm.with_structured_output(EvaluatorOutput)

    def _format_conversation(self, messages: List[Any]) -> str:
        """格式化对话历史"""
        lines = ["对话历史：", ""]
        for m in messages:
            if isinstance(m, HumanMessage):
                lines.append(f"👤 用户: {m.content}")
            elif isinstance(m, AIMessage):
                content = m.content or ""
                # 跳过 Evaluator 自己的反馈消息
                if content.startswith("📋 评估反馈:"):
                    lines.append(f"📋 {content}")
                elif m.tool_calls:
                    tools_used = [tc.get("name", "unknown") for tc in m.tool_calls]
                    lines.append(f"🤖 Assistant: [调用工具: {', '.join(tools_used)}]")
                else:
                    lines.append(f"🤖 Assistant: {content}")
            elif isinstance(m, SystemMessage):
                pass  # 跳过系统消息
        return "\n".join(lines)

    def evaluate(
        self,
        messages: List[Any],
        success_criteria: str,
        last_response: str,
    ) -> EvaluatorOutput:
        """评估 Worker 的最后输出"""
        conversation = self._format_conversation(messages)

        user_message = f"""{conversation}

成功标准：
{success_criteria}

Assistant 的最后回复：
{last_response}

请评估：给出反馈、是否达标、是否需要用户补充信息。"""

        try:
            result: EvaluatorOutput = self.llm_with_output.invoke([
                SystemMessage(content=EVALUATOR_SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ])
            logger.info(
                f"评估完成 | 达标={result.success_criteria_met} | "
                f"需追问={result.user_input_needed} | "
                f"反馈={result.feedback[:80]}..."
            )
            return result
        except Exception as e:
            logger.error(f"评估调用失败: {e}")
            # Fallback: 宽松通过
            return EvaluatorOutput(
                feedback=f"评估器异常，默认通过: {e}",
                success_criteria_met=True,
                user_input_needed=False,
            )
