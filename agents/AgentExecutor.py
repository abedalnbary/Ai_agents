# This Agent is created to solve: Assignment B — Hiring ReAct Agent
import json
import re
from dataclasses import dataclass

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_protocol import AgentResult
from pyexpat.errors import messages

from base.hiring_agent_base import HiringAgentBase
from services.llm_client import LlmClient
from services.tool_executor import ToolExecutor


@dataclass
class ReActConfig:
    max_steps: int = 6
    max_answer_length: int = 1500


def _parse_json(text: str) -> dict | None:
    cleaned = re.sub(r"'''(?:json)?\s", "", text).strip().strip("'").strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.decoder.JSONDecodeError:
        return None


def _build_system_prompt(tool_schemas: list[dict]) -> str:
    tools_section = ""
    for s in tool_schemas:
        props = s["parameters"].get("properties", {})
        required_args = s["parameters"].get("required", [])
        args_lines = ""
        for pname, pdef in props.items():
            req = " (required)" if pname in required_args else " (optional)"
            enum_hint = (
                f" - one of: {', '.join(str(v) for v in pdef['enum'])}"
                if "enum" in pdef else ""
            )
            args_lines += (
                f"\n   {pname} ({pdef['type']}{req}{enum_hint}: "
                f"{pdef.get('description', '')}"
            )
        tools_section += (
            f"\nTool: {s['name']}\n"
            f"Description: {s['description']}\n"
            f"Arguments: {args_lines}\n"
        )

    return f"""You are a helpful assistant with access to tools.

RESPONSE FORMAT — follow exactly:
- To call a tool, output ONLY this JSON (one object, no surrounding text):
  {{"action": "tool_name", "args": {{"arg_name": "value"}}}}
- To give a final answer, output ONLY this JSON:
  {{"action": "final_answer", "answer": "your answer here"}}

RULES:
1. Output ONE JSON object per response — no prose, no markdown, no code fences.
2. Use a tool when you need to compute a value or look up information.
3. After receiving a tool result, decide: call another tool or give the final_answer.
4. If a tool returns an error, include it clearly in the final_answer.
5. Never invent a tool name — use only the tools listed below.

Available tools:
{tools_section}"""


class AgentExecutor(HiringAgentBase):
    def __init__(
            self,
            llm_client: LlmClient,
            executor: ToolExecutor,
            config: ReActConfig = ReActConfig(),
    ) -> None:
        self._llm = llm_client
        self._executor = executor
        self._config = config

    def chat(self, user_input: str, cv_filename : str, jb_filename : str) -> str:
        self._executor.clear_traces()
        system = SystemMessage(content=_build_system_prompt(self._executor.tool_schemas()))
        human_msg = f"user query: {user_input}, cv_filename: {cv_filename}, jb_filename: {jb_filename}"
        messages = [system, HumanMessage(content=human_msg)]

        for step in range(1, self._config.max_steps + 1):

            self._executor.log_trace(step, "PLAN", None, "LLM deciding next action...")
            raw = self._llm.invoke(messages)
            self._executor.log_trace(step, "PLAN", None, f"LLM output -> {raw[:150]}")
            messages.append(AIMessage(content=raw))

            parsed = _parse_json(raw)

            if parsed is None:
                messages.append(HumanMessage(
                    content="Invalid format. Respond with ONLY a single JSON object - no prose, no markdown."
                ))
                repair = self._llm.invoke(messages)
                messages.append(AIMessage(content=repair))
                parsed = _parse_json(repair)
                if parsed is None:
                    return (
                        "I had trouble producing a valid response format. "
                        "Please try rephrasing your question."
                    )

            action = parsed.get("action", "")

            if action == "final_answer":
                answer = str(parsed.get("answer", ""))
                if len(answer) > self._config.max_answer_length:
                    answer = answer[:self._config.max_answer_length] + " [truncated]"
                self._executor.log_trace(
                    step, "OBSERVE", None,
                    f"FINAL ANSWER: {answer[:120]}"
                )
                return answer

            tool_name = action
            args = parsed.get("args", {})
            result = self._executor.execute(step, tool_name, args)

            if result.ok:
                observation = f"Tool: {tool_name} returned {result.value}"
            else:
                observation = (
                    f"Tool: {tool_name} failed with error: {result.error}. "
                    f"Report this error to the user in your final_answer."
                )
            self._executor.log_trace(step, "OBSERVE", None, observation[:200])
            messages.append(HumanMessage(content=observation))

        return (
            "Reached the maximum step limit without a final answer. "
            "Please try a simpler question."
        )


    def reset(self) -> None:
        self._executor.clear_traces()