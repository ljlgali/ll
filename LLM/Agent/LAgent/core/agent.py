# core/agent.py —— 会话编排层（v2：带会话统计、工具耗时、reset 与 cancel 机制）
# Agent 类：维护对话历史、发起流式请求、执行工具调用循环
# 对外暴露 chat_stream(user_input) 生成器，产出统一事件流，
# 任何前端（tui / web / desktop / mobile）只需消费事件即可，无需关心 LLM 细节
import json
import time
import uuid

from core.config import create_client
from core.functions import dispatch
from core.tools import SYSTEM_PROMPT, TOOLS


class Agent:
    """会话级 Agent：内部持有 messages，多轮对话历史自动累积"""

    def __init__(self):
        self.client, self.model = create_client()
        self.base_url = self.client.base_url
        self.cancel_flag = False          # 供 UI 层设置，Esc 中断生成用
        self._reset_stats()
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # ===== 会话统计（TUI 右侧栏直接读） =====
    def _reset_stats(self):
        self.session_id = uuid.uuid4().hex[:8]
        self.round_count = 0
        self.total_tool_calls = 0
        self.start_time = time.time()

    @property
    def elapsed_s(self) -> float:
        return time.time() - self.start_time

    @property
    def message_count(self) -> int:
        # messages 中去除 system 消息
        return len(self.messages) - 1

    @property
    def registered_tools(self) -> list:
        return TOOLS

    # ===== 会话控制 =====
    def reset(self):
        """/new 命令：重建会话，保留同一个 Agent 实例"""
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.cancel_flag = False
        self._reset_stats()

    # ===== 主入口 =====
    def chat_stream(self, user_input: str):
        """处理一轮用户输入，yield 事件字典：
        {"type": "token", "content": str}
        {"type": "tool",  "name": str, "args": dict, "result": str, "elapsed_ms": float}
        {"type": "done",  "reply": str}
        {"type": "error", "message": str}

        支持外部通过 cancel_flag 中断生成（Esc 键）。
        """
        self.round_count += 1
        self.cancel_flag = False
        try:
            self.messages.append({"role": "user", "content": user_input})
            while True:
                # 每一轮都带上 tools，模型才能正常发起工具调用
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    stream=True,
                )
                reply = ""
                calls = {}
                for chunk in stream:
                    if self.cancel_flag:
                        yield {"type": "error", "message": "用户中断生成"}
                        return
                    delta = chunk.choices[0].delta
                    if delta.tool_calls:
                        for d in delta.tool_calls:
                            item = calls.setdefault(d.index, {"id": "", "name": "", "arguments": ""})
                            if d.id:
                                item["id"] = d.id
                            if d.function and d.function.name:
                                item["name"] = d.function.name
                            if d.function and d.function.arguments:
                                item["arguments"] += d.function.arguments
                    if delta.content:
                        reply += delta.content
                        yield {"type": "token", "content": delta.content}

                if not calls:
                    self.messages.append({"role": "assistant", "content": reply})
                    yield {"type": "done", "reply": reply}
                    return

                self.messages.append({
                    "role": "assistant",
                    "content": reply or None,
                    "tool_calls": [
                        {
                            "id": item["id"],
                            "type": "function",
                            "function": {"name": item["name"], "arguments": item["arguments"]}
                        }
                        for item in calls.values()
                    ]
                })

                for item in calls.values():
                    name = item["name"]
                    args = json.loads(item["arguments"]) if item["arguments"] else {}
                    t0 = time.perf_counter()
                    result = dispatch(name, args)
                    elapsed = (time.perf_counter() - t0) * 1000
                    self.total_tool_calls += 1
                    yield {"type": "tool", "name": name, "args": args,
                           "result": result, "elapsed_ms": elapsed}
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": item["id"],
                        "content": result
                    })
        except Exception as e:
            yield {"type": "error", "message": str(e)}
