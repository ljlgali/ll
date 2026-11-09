# core/agent.py —— 会话编排层（v3：带上下文压缩、Token 监控、历史检索）
# Agent 类：维护对话历史、发起流式请求、执行工具调用循环
# 对外暴露 chat_stream(user_input) 生成器，产出统一事件流，
# 任何前端（tui / web / desktop / mobile）只需消费事件即可，无需关心 LLM 细节
import json
import time
import uuid
from pathlib import Path

from core.config import create_client, load_settings, load_agent_settings
from core.context import (
    COMPACT_PROMPT,
    DEFAULT_CONTEXT_WINDOW,
    WARNING_RATIO,
    estimate_messages_tokens,
    save_archive,
)
from core.functions import dispatch, register_skills, register_mcp
from core.mcp_client import MCPManager
from core.skills import discover_skills
from core.tools import build_system_prompt, TOOLS

# 项目根目录（定位 config.ini 和 AGENTS.md）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _friendly_error(e: Exception) -> str:
    """把常见 API 错误翻译成中文友好提示"""
    raw = str(e)
    lower = raw.lower()
    # —— 模型不存在或当前账号无权访问（千帆会以 401 invalid_model 的形式返回）——
    if (
        "invalid_model" in lower
        or "does not exist or you do not have access" in lower
        or "model_not_found" in lower
    ):
        return (
            "❌ 模型不存在或无使用权\n"
            "   请检查 config.ini [llm] model 是否拼写正确，或到控制台确认该模型已开通"
        )
    # —— 账户欠费 / 未结清 ——
    if "account_overdue" in lower or "overdue" in lower:
        return (
            "❌ 账户欠费（403）\n"
            "   请到百度千帆控制台结清欠款后再试"
        )
    # —— 401：鉴权失败 ——
    if "401" in raw or "authentication" in lower or "invalid_api_key" in lower:
        return (
            "❌ API Key 无效（401）\n"
            "   请打开 config.ini 检查 [llm] api_key 是否正确"
        )
    # —— 402：余额不足 ——
    if "402" in raw or "insufficient" in lower or "balance" in lower:
        return (
            "❌ 账户余额不足（402）\n"
            "   请到所用平台的控制台充值后再试"
        )
    # —— 404：模型不存在 ——
    if "404" in raw or "not_found" in lower or ("model" in lower and "not exist" in lower):
        return (
            "❌ 模型不存在（404）\n"
            "   请检查 config.ini [llm] model 是否拼写正确"
        )
    # —— 429：限流 ——
    if "429" in raw or "rate limit" in lower or "too many" in lower:
        return "❌ 请求过于频繁（429），请稍后再试"
    # —— 超时 ——
    if "timeout" in lower or "timed out" in lower:
        return "❌ 请求超时，请检查网络或稍后再试"
    # —— 默认：展示原始错误但截断 ——
    if len(raw) > 200:
        raw = raw[:200] + "..."
    return f"❌ LLM 调用失败：{raw}"


def _load_agents_md() -> str | None:
    """如果项目根目录下存在 AGENTS.md，读取并返回内容；不存在返回 None"""
    p = _PROJECT_ROOT / "AGENTS.md"
    if p.exists():
        try:
            return p.read_text(encoding="utf-8").strip()
        except Exception:
            return None
    return None


class Agent:
    """会话级 Agent：内部持有 messages，多轮对话历史自动累积"""

    def __init__(self, context_window: int | None = None):
        self.client, self.model = create_client()
        self.base_url = self.client.base_url
        self.cancel_flag = False          # 供 UI 层设置，Esc 中断生成用
        # 上下文窗口优先用传入参数，再用 config.ini，最后用默认值
        if context_window is None:
            context_window = load_settings().get("context_window", DEFAULT_CONTEXT_WINDOW)
        self.context_window = context_window
        # 警告阈值从 config.ini 读取（硬编码 WARNING_RATIO 作为兜底）
        agent_cfg = load_agent_settings()
        self.warning_ratio = agent_cfg.get("warning_ratio", WARNING_RATIO)
        # —— Skill 发现：初始化时扫描一次，只加载 name / description ——
        self.discovered_skills = discover_skills()
        register_skills(self.discovered_skills)
        # —— MCP Server 连接：读取 .mcp.json，连接并动态注册 MCP 工具 ——
        self.mcp = MCPManager()
        self.mcp.start()
        register_mcp(self.mcp)
        system_prompt = build_system_prompt(self.discovered_skills, self.mcp)
        self._reset_stats()
        self.messages = [{"role": "system", "content": system_prompt}]
        # —— AGENTS.md 一次性注入（reset 时也会重新走一遍）——
        self._inject_agents_md()
        # —— Token 使用统计 ——
        self.prompt_tokens = 0
        self.completion_tokens = 0
        # —— 压缩状态标志 ——
        self.compacting = False

    def _inject_agents_md(self) -> None:
        """把项目根目录 AGENTS.md 作为长期规则追加到 messages 末尾。
        由 __init__ 和 reset() 共同调用，保证 /new 之后规则不丢。"""
        content = _load_agents_md()
        if not content:
            return
        # 长度截断（避免超长 AGENTS.md 直接撑爆上下文）
        if len(content) > 4000:
            content = content[:4000] + "\n...(AGENTS.md 过长，已截断)"
        self.messages.append({
            "role": "user",
            "content": (
                "[AGENTS.md]\n"
                "以下是项目根目录 AGENTS.md 文件的内容，请你在整个会话中遵守这些项目规则。\n"
                "你不需要引用它，只需要默默地按其中的规则行事。\n\n"
                + content
            ),
        })
        self.messages.append({
            "role": "assistant",
            "content": "收到，我已经阅读并理解 AGENTS.md 中的项目规则，会在后续对话中遵守。",
        })

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
        """当前全部工具：本地工具 + 动态注册的 MCP 工具 + recallContext"""
        # recallContext 已在 TOOLS 里，直接返回
        return TOOLS + self.mcp.schemas

    @property
    def mcp_tools(self) -> list:
        return self.mcp.schemas

    # ===== Token 使用量监控 =====
    @property
    def current_tokens(self) -> int:
        """估算当前 messages 列表的总 Token 数"""
        return estimate_messages_tokens(self.messages)

    @property
    def total_tokens(self) -> int:
        """累计消耗的 Token 数（prompt + completion）"""
        return self.prompt_tokens + self.completion_tokens

    @property
    def context_usage_ratio(self) -> float:
        """当前上下文使用比例（0~1）"""
        return self.current_tokens / self.context_window if self.context_window else 0

    @property
    def context_warning(self) -> bool:
        """是否达到警告阈值（从 config.ini 读取 warning_ratio，默认 0.70）"""
        return self.context_usage_ratio >= self.warning_ratio

    @property
    def context_usage_display(self) -> str:
        """TUI 直接显示的格式字符串"""
        used_k = self.current_tokens / 1024
        window_k = self.context_window // 1024
        pct = self.context_usage_ratio * 100
        label = f"默认 {window_k}k" if self.context_window == DEFAULT_CONTEXT_WINDOW else f"{window_k}k"
        # < 1k 显示一位小数（如 0.8k），>= 1k 才取整
        used_str = f"{used_k:.1f}k" if used_k < 1 else f"{int(used_k)}k"
        return f"{used_str} / {label}  ·  {pct:.1f}%"

    # ===== 会话控制 =====
    def reset(self):
        """/new 命令：重建会话，保留同一个 Agent 实例（MCP 连接常驻，无需重连）"""
        self.discovered_skills = discover_skills()
        register_skills(self.discovered_skills)
        system_prompt = build_system_prompt(self.discovered_skills, self.mcp)
        self.messages = [{"role": "system", "content": system_prompt}]
        self._inject_agents_md()
        self.cancel_flag = False
        self._reset_stats()
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.compacting = False

    # ===== 上下文压缩 =====
    def compact(self):
        """/compact 命令：保存归档 → 调 LLM 生成摘要 → 替换历史

        返回一个生成器，yield 事件字典：
        {"type": "compact_start"}
        {"type": "archive_saved", "archive_id": str, "path": str}
        {"type": "token", "content": str}   —— 压缩摘要的流式输出
        {"type": "archive_replaced", "archive_id": str}
        {"type": "compact_done", "reply": str, "archive_id": str,
         "before_messages": list, "after_messages": list,
         "before_tokens": int, "after_tokens": int}
        {"type": "compact_error", "message": str}
        """
        if self.compacting:
            # 可能是上次卡死没解锁（比如网络中断、进程被 Ctrl+C 了）
            # 直接强制解锁继续跑，比让用户 /new 重置好
            self.compacting = False

        self.compacting = True
        # 压缩前快照（深拷贝，后面 messages 会被替换）
        before_messages = list(self.messages)
        before_tokens = self.current_tokens
        yield {"type": "compact_start"}

        # —— 步骤 1：保存原始上下文归档 ——
        try:
            archive_id, file_path = save_archive(self.messages)
            yield {"type": "archive_saved", "archive_id": archive_id, "path": str(file_path)}
        except Exception as e:
            self.compacting = False
            yield {"type": "compact_error", "message": f"归档保存失败：{e}"}
            return

        # —— 步骤 2：构造压缩请求 ——
        # 把当前消息历史序列化成可读文本，作为压缩 Prompt 的用户输入
        history_text = self._serialize_messages_for_compact()
        compact_messages = [
            {"role": "system", "content": COMPACT_PROMPT},
            {"role": "user", "content": history_text},
        ]

        # —— 步骤 3：调 LLM 生成摘要（流式，带 3 分钟超时） ——
        summary = ""
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=compact_messages,
                stream=True,
                timeout=180.0,  # 3 分钟超时（压缩任务历史长 + 输出长，需要更多时间）
            )
            last_token_time = time.time()  # 记录最后一次收到 token 的时间
            for chunk in stream:
                # 60 秒无新 token 判定为卡死
                if time.time() - last_token_time > 60:
                    self.compacting = False
                    yield {"type": "compact_error", "message": "压缩超时（60秒无响应），请检查网络或稍后再试"}
                    return
                if self.cancel_flag:
                    self.compacting = False
                    yield {"type": "compact_error", "message": "用户中断压缩"}
                    return
                # ⚠️ 检查流式错误（余额不足时 API 不抛异常，而是在 chunk 里藏 error）
                if hasattr(chunk, "error") and chunk.error:
                    self.compacting = False
                    yield {"type": "compact_error", "message": f"API 错误：{chunk.error}"}
                    return
                if hasattr(chunk, "choices") and chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta is None:
                        continue
                    # delta 也可能藏 error
                    if hasattr(delta, "error") and delta.error:
                        self.compacting = False
                        yield {"type": "compact_error", "message": f"流式错误：{delta.error}"}
                        return
                    if delta.content:
                        last_token_time = time.time()  # 收到新 token，重置计时
                        summary += delta.content
                        yield {"type": "token", "content": delta.content}
                else:
                    # 有些 API 会直接返回 error 字段
                    if hasattr(chunk, "model"):
                        # 正常 chunk 但无 choices，可能是 DONE 信号
                        pass
                    else:
                        # 可能是错误消息
                        self.compacting = False
                        yield {"type": "compact_error", "message": f"异常响应：{chunk}"}
                        return

            # 收集 usage
            try:
                if hasattr(chunk, "usage") and chunk.usage:
                    self.completion_tokens += (chunk.usage.completion_tokens or 0)
            except Exception:
                pass
        except Exception as e:
            self.compacting = False
            yield {"type": "compact_error", "message": _friendly_error(e)}
            return

        # —— 步骤 4：替换历史消息 ——
        # 保留 system prompt，把其余历史替换成摘要 + 归档说明
        from datetime import datetime
        archive_note = (
            f"\n\n---\n"
            f"此前上下文已于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 完成压缩，"
            f"原始上下文保存在编号为 {archive_id} 的归档文件中。"
            f"如需查找历史信息，请使用 recallContext 工具，传入 id='{archive_id}' 和关键词 text。"
        )
        summary_with_note = summary.strip() + archive_note

        system_msg = self.messages[0]   # 保留原 system prompt
        # 用摘要替换所有非 system 消息
        self.messages = [
            system_msg,
            {"role": "assistant", "content": summary_with_note},
        ]

        yield {"type": "archive_replaced", "archive_id": archive_id}
        after_tokens = self.current_tokens
        after_messages = list(self.messages)
        yield {"type": "compact_done", "reply": summary_with_note,
               "archive_id": archive_id,
               "before_messages": before_messages,
               "after_messages": after_messages,
               "before_tokens": before_tokens,
               "after_tokens": after_tokens}
        self.compacting = False

    def _serialize_messages_for_compact(self) -> str:
        """把 messages 序列化为可读文本，供压缩 LLM 阅读"""
        lines = []
        for i, msg in enumerate(self.messages):
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "?")
            content = msg.get("content", "") or ""
            # tool_calls
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                lines.append(f"[{i}] {role} (tool_call {tc.get('id','?')}): {fn.get('name','')}({fn.get('arguments','')})")
            if role == "tool":
                tool_call_id = msg.get("tool_call_id", "")
                lines.append(f"[{i}] {role} ({tool_call_id}): {content[:500]}")
            elif role == "system":
                lines.append(f"[{i}] {role}: {content[:1000]}")
            else:
                lines.append(f"[{i}] {role}: {content[:2000]}")
        return "\n\n".join(lines)

    # ===== 主入口 =====
    def chat_stream(self, user_input: str):
        """处理一轮用户输入，yield 事件字典：
        {"type": "token", "content": str}
        {"type": "tool",  "name": str, "args": dict, "result": str, "elapsed_ms": float}
        {"type": "done",  "reply": str}
        {"type": "warning", "message": str}   —— 上下文使用量警告
        {"type": "error", "message": str}

        支持外部通过 cancel_flag 中断生成（Esc 键）。
        """
        # 压缩期间拒绝普通输入
        if self.compacting:
            yield {"type": "error", "message": "正在压缩上下文，请稍候再试"}
            return

        self.round_count += 1
        self.cancel_flag = False
        # 每轮都带上完整工具集（本地工具 + MCP 工具 + recallContext）
        all_tools = TOOLS + self.mcp.schemas
        try:
            self.messages.append({"role": "user", "content": user_input})
            while True:
                # 每一轮都带上 tools，模型才能正常发起工具调用
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    tools=all_tools,
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

                # 收集 usage（如果 API 返回）
                try:
                    if hasattr(chunk, "usage") and chunk.usage:
                        self.prompt_tokens += (chunk.usage.prompt_tokens or 0)
                        self.completion_tokens += (chunk.usage.completion_tokens or 0)
                except Exception:
                    pass

                if not calls:
                    self.messages.append({"role": "assistant", "content": reply})
                    # —— 每次响应后检查上下文使用量 ——
                    if self.context_warning:
                        ratio_pct = self.context_usage_ratio * 100
                        yield {"type": "warning",
                               "message": f"上下文已使用 {ratio_pct:.0f}%（{self.current_tokens // 1024}k / {self.context_window // 1024}k），建议执行 /compact 压缩"}
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
            yield {"type": "error", "message": _friendly_error(e)}

