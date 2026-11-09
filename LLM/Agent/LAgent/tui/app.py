"""
朴素版 Textual 界面：对话区 + 输入框
自动滚到底，支持 Ctrl+C / Ctrl+Q 退出
"""
import os
import json
from pathlib import Path

from textual.app import App, ComposeResult, Screen
from textual.containers import ScrollableContainer, Vertical, Horizontal
from textual.widgets import Input, Static, Footer, Header, Button
from textual.screen import ModalScreen

from core.agent import Agent


def _format_messages(messages: list, max_chars: int = 3000) -> str:
    """把 messages 列表格式化为可读文本，用于面板左右对比"""
    role_icons = {"system": "⚙", "user": "👤", "assistant": "🤖", "tool": "🔧"}
    lines = []
    for i, msg in enumerate(messages):
        role = msg.get("role", "?")
        icon = role_icons.get(role, "📨")
        content = msg.get("content", "") or ""
        # 截断过长内容
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n... [截断 {len(content) - max_chars} 字符]"
        # 处理 tool_calls
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                name = tc.get("function", {}).get("name", "?")
                args = tc.get("function", {}).get("arguments", "")
                try:
                    args_obj = json.loads(args)
                    args_str = json.dumps(args_obj, ensure_ascii=False)[:200]
                except Exception:
                    args_str = args[:200]
                lines.append(f"{icon} [{role}] (tool_call) {name}({args_str})")
                if content:
                    lines.append(f"  {content[:200]}")
                content = ""
        if content:
            # 压缩换行，保持紧凑
            first_line = content.split("\n")[0]
            if len(first_line) > 120:
                first_line = first_line[:120] + "..."
            remaining = content[len(first_line):].strip() if first_line != content else ""
            if remaining:
                remaining = f"\n  ... {len(remaining)} more chars"
            lines.append(f"{icon} [{role}] {first_line}{remaining}")
        lines.append("")
    return "\n".join(lines)


class CompactDiffOverlay(Vertical):
    """全屏覆盖的压缩对比面板。默认 hidden，运行时 update 内容 + visible=True 即可弹出。
    跟 ModalScreen 不同——不需要 push_screen，不需要 manage，启动时就 compose 好，弹出零失败。"""

    DEFAULT_CSS = """
    CompactDiffOverlay {
        position: absolute;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.75);
        layer: overlay;
        layout: vertical;
        padding: 2 4;
    }
    #diff-card {
        width: 100%;
        height: 100%;
        border: round $accent;
        background: $surface-darken-2;
        layout: vertical;
    }
    #diff-header {
        height: auto;
        padding: 1;
        background: $surface-darken-1;
        border-bottom: tall $accent;
    }
    #diff-footer {
        height: auto;
        padding: 1;
        background: $surface-darken-1;
        border-top: tall $accent;
        align: right middle;
    }
    #columns { height: 1fr; padding: 0 1; }
    #col-before, #col-after {
        width: 1fr; height: 1fr;
        border: round $accent;
        background: $surface-darken-3;
        margin: 0 1 0 0;
    }
    #col-after { margin: 0; }
    .col-title {
        height: auto; padding: 0 1;
        background: $accent-darken-2; text-style: bold;
    }
    .col-body { height: 1fr; padding: 0 1; }
    """

    def __init__(self):
        super().__init__(id="compact-overlay")
        self._header = Static("")
        self._before_title = Static("")
        self._after_title = Static("")
        self._before_body = Static("")
        self._after_body = Static("")
        self._footer = Static("")

    def compose(self) -> ComposeResult:
        with Vertical(id="diff-card"):
            yield self._header
            with Horizontal(id="columns"):
                with Vertical(id="col-before"):
                    yield self._before_title
                    yield ScrollableContainer(self._before_body, classes="col-body")
                with Vertical(id="col-after"):
                    yield self._after_title
                    yield ScrollableContainer(self._after_body, classes="col-body")
            with Horizontal(id="diff-footer"):
                yield Button("关闭", id="close-btn", variant="primary")

    def update_content(self, before_messages, after_messages,
                       before_tokens, after_tokens, archive_id):
        """运行时更新所有内容（不触发 compose，安全）"""
        saved = before_tokens - after_tokens
        ratio = (1 - after_tokens / before_tokens) * 100 if before_tokens else 0
        if saved >= 0:
            delta_color, delta_text = "green", f"节省 {saved} tokens ({saved/1024:.1f}k) 压缩率 {ratio:.1f}%"
        else:
            delta_color, delta_text = "yellow", f"增加 {-saved} tokens ({-saved/1024:.1f}k)"

        self._header.update(
            f"[bold cyan]📊 上下文压缩日志[/]  [dim]归档：[/][cyan]{archive_id}[/]\n"
            f"  [dim]{len(before_messages)}条 / {before_tokens:,}t → {len(after_messages)}条 / {after_tokens:,}t[/]\n"
            f"  [{delta_color}]{delta_text}[/]"
        )
        self._before_title.update(f"[bold cyan]⬅ 压缩前原文[/]  [dim]{len(before_messages)}条 · {before_tokens/1024:.1f}k[/]", classes="col-title")
        self._after_title.update(f"[bold green]➡ 压缩后结果[/]  [dim]{len(after_messages)}条 · {after_tokens/1024:.1f}k[/]", classes="col-title")
        self._before_body.update(_format_messages(before_messages))
        self._after_body.update(_format_messages(after_messages))
        self._footer.update("[dim]按 ESC 或点击关闭按钮[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-btn":
            self.visible = False


class LAgentApp(App):
    TITLE = "xAgent"
    SUB_TITLE = ""

    BINDINGS = [
        ("escape", "close_overlay", "关闭面板"),
    ]

    CSS = """
    Screen {
        layout: horizontal;
    }
    #sidebar {
        width: 28;
        height: 100%;
        border: tall $accent;
        background: $boost;
        padding: 0 1;
        overflow: auto;
    }
    #sidebar-title {
        text-style: bold;
        height: auto;
        padding: 0 1;
        border-bottom: tall $accent-darken-2;
        margin-bottom: 1;
    }
    .section-title {
        text-style: bold;
        color: $accent;
        height: auto;
        padding: 0 0;
        margin-top: 1;
    }
    .sidebar-item {
        height: auto;
        padding: 0 0 0 1;
        color: $text;
    }
    #main-area {
        width: 1fr;
        height: 100%;
    }
    #chat {
        height: 1fr;
    }
    #input {
        dock: bottom;
        height: 3;
    }
    #ctx-bar {
        height: auto;
        padding: 0 1;
        background: $boost;
        border-bottom: tall $accent-darken-2;
    }
    """

    def __init__(self):
        super().__init__()
        self.agent = Agent()
        self._busy = False
        self._cwd = Path.cwd()
        self._skills_count = len(self.agent.discovered_skills)
        self._mcp_count = len(self.agent.mcp_tools)
        self._ctx_bar: Static | None = None
        self._sidebar: Vertical | None = None
        self._overlay: CompactDiffOverlay | None = None
        self._refresh_subtitle()

    def compose(self) -> ComposeResult:
        # 左边栏
        yield Vertical(id="sidebar")
        # 主区域：先 yield main-area 容器，再嵌套 yield 子元素（Textual compose 自动父子关系）
        with Vertical(id="main-area"):
            yield ScrollableContainer(id="chat")
            yield Input(
                placeholder="输入问题后 Enter 发送；输入 / 显示斜杠命令",
                id="input",
            )
        # 🎯 overlay：跟 sidebar/main-area 平级（都是 Screen 的直接子节点）
        # 启动时就 compose 好，默认 hidden，compact_done 时只改 visible + update 内容
        yield CompactDiffOverlay()

    def on_mount(self) -> None:
        self._sidebar = self.query_one("#sidebar", Vertical)
        self._build_sidebar()
        # 存 overlay 引用 + 默认隐藏（启动时就 compose 好）
        self._overlay = self.query_one("#compact-overlay", CompactDiffOverlay)
        self._overlay.visible = False
        self.query_one("#input", Input).focus()
        # 聊天区顶部挂常驻状态栏
        self._ctx_bar = Static("", id="ctx-bar")
        self._chat.mount(self._ctx_bar)
        self._refresh_subtitle()
        # 欢迎信息
        self._chat.mount(Static(
            "[bold green]✓ xAgent 已启动[/]\n"
            f"[dim]工作目录：[/]{self._cwd}\n"
            f"[dim]技能：[/]{self._skills_count} 个\n"
            f"[dim]扩展工具：[/]{self._mcp_count} 个\n"
            f"[dim]初始上下文：[/]{self.agent.context_usage_display}\n"
            "输入问题开始对话；输入 / 显示斜杠命令。",
        ))
        # 异步刷新 MCP 状态（后台线程，界面先显示）
        self.run_worker(self._async_refresh_mcp, exclusive=False, thread=True)

    def _build_sidebar(self) -> None:
        """构建左边栏内容（可重复调用，不用固定 widget id 避免 DuplicateIds）"""
        if self._sidebar is None:
            return
        self._sidebar.remove_children()
        # 标题（不用固定 id，避免重复构建时 DuplicateIds）
        self._sidebar.mount(Static("✓ xAgent"))
        # 模型信息
        self._sidebar.mount(Static(
            f"[dim]模型：[/]{self.agent.model}\n"
            f"[dim]窗口：[/]{self.agent.context_window//1024}k",
            classes="sidebar-item"
        ))
        # 技能
        self._sidebar.mount(Static(f"📚 技能（{self._skills_count}）", classes="section-title"))
        if self.agent.discovered_skills:
            for s in self.agent.discovered_skills[:8]:
                self._sidebar.mount(Static(f"  • {s['name']}", classes="sidebar-item"))
            if len(self.agent.discovered_skills) > 8:
                self._sidebar.mount(Static(f"  ... 还有 {len(self.agent.discovered_skills)-8} 个", classes="sidebar-item"))
        else:
            self._sidebar.mount(Static("  [dim]暂无[/]", classes="sidebar-item"))
        # MCP Server
        self._sidebar.mount(Static(f"🔌 MCP Server（{self._mcp_count}）", classes="section-title"))
        self._sidebar.mount(Static("  [dim]加载中...[/]", classes="sidebar-item"))
        # 会话统计
        self._sidebar.mount(Static("📊 会话信息", classes="section-title"))
        self._sidebar.mount(Static(
            f"[dim]消息数：[/]{len(self.agent.messages)}\n"
            f"[dim]已压缩：[/]{len(list(Path(self._agent_root()/'.agents/context').glob('*.jsonl'))) if (self._agent_root()/'.agents/context').exists() else 0} 次",
            classes="sidebar-item"
        ))

    def _agent_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    def _async_refresh_mcp(self) -> None:
        """后台线程：等 MCP 连接完后刷新左栏"""
        import time
        # 等 MCP 启动完成（最多 5 秒）
        for _ in range(50):
            if self.agent.mcp_tools:
                break
            time.sleep(0.1)
        # 回主线程刷新
        tools = self.agent.mcp_tools
        self.call_from_thread(lambda: self._refresh_sidebar_mcp(tools))

    def _refresh_sidebar_mcp(self, tools: list) -> None:
        """只刷新左栏的 MCP 区域（找到那个"加载中..."替换掉）"""
        if self._sidebar is None:
            return
        # 重新构建整个左栏（简单粗暴但可靠）
        self._mcp_count = len(tools)
        self._build_sidebar()

    @property
    def _chat(self) -> ScrollableContainer:
        return self.query_one("#chat", ScrollableContainer)

    # ============== 输入处理 ==============

    # 所有可用斜杠命令（用于补全）
    SLASH_COMMANDS = [
        "/new  — 重置会话（自动保存）",
        "/save  — 手动保存当前会话",
        "/sessions  — 列出所有已保存会话",
        "/resume <id>  — 恢复历史会话",
        "/quit  — 退出（自动保存）",
        "/compact  — 手动触发上下文压缩",
        "/skills  — 列出技能",
        "/mcp  — 查看 MCP 状态",
        "/ctx  — 查看上下文使用量",
        "/archives  — 列出压缩归档",
        "/help  — 显示本帮助",
    ]

    def on_input_changed(self, event: Input.Changed) -> None:
        """输入变化时：如果以 / 开头，在聊天区底部显示补全提示"""
        text = event.value.strip()
        # 找是否已有"补全提示" Static 存在，有的话 update，没有就 mount
        hint_widget = getattr(self, "_slash_hint", None)
        if text.startswith("/"):
            # 过滤：匹配输入前缀的命令
            matches = [c for c in self.SLASH_COMMANDS if c.lower().startswith(text.lower()) or c.split()[0].startswith(text.lower())]
            if not matches:
                matches = self.SLASH_COMMANDS   # 什么都不匹配就全显示
            hint_text = "[dim]💡 斜杠命令：[/]" + "  ".join(matches[:6])
            if hint_widget is None:
                self._slash_hint = Static(hint_text)
                self._chat.mount(self._slash_hint)
                self._scroll_bottom()
            else:
                hint_widget.update(hint_text)
        else:
            if hint_widget is not None:
                hint_widget.remove()
                self._slash_hint = None

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return

        # —— Slash 命令 ——
        if text.startswith("/"):
            self._handle_command(text)
            return

        if self._busy:
            return

        # 发送前：先让字幕同步一次（此时还是旧上下文）
        self._refresh_subtitle()
        # 手动滚到底（auto_scroll 在新 mount 后需要一帧延迟）
        self._mount_user(text)
        self._scroll_bottom()
        self._busy = True
        self._chat_thread(text)

    def _handle_command(self, cmd: str) -> None:
        """处理所有斜杠命令"""
        self._busy = False          # 命令不受 busy 锁限制
        parts = cmd.strip().split(maxsplit=1)
        head = parts[0].lower()

        # —— /new 重置（自动保存当前会话）——
        if head in ("/new", "/reset", "/clear"):
            # 先自动保存当前会话
            try:
                from core.context import save_session
                sid, path = save_session(self.agent.messages, self.agent.session_id)
                self._chat.mount(Static(f"[dim]💾 自动保存当前会话 → [cyan]{path.name}[/][/]"))
            except Exception as e:
                self._chat.mount(Static(f"[yellow dim]⚠ 自动保存失败：{e}[/]"))
            self.agent.reset()
            self._refresh_subtitle()
            self._chat.mount(Static(
                "[bold yellow]● 会话已重置[/]\n"
                f"发现 {len(self.agent.discovered_skills)} 个技能\n"
                f"session_id = {self.agent.session_id}\n"
                f"上下文：{self.agent.context_usage_display}",
            ))
            self._scroll_bottom()

        # —— /save 手动保存 ——
        elif head in ("/save", "/s"):
            try:
                from core.context import save_session
                sid, path = save_session(self.agent.messages, self.agent.session_id)
                self._chat.mount(Static(
                    f"[bold green]✓ 会话已保存[/]\n"
                    f"  • 文件：[cyan]{path}[/]\n"
                    f"  • 消息：{len(self.agent.messages)} 条\n"
                    f"  • 当前 tokens：{self.agent.current_tokens}"
                ))
            except Exception as e:
                self._chat.mount(Static(f"[red]保存失败：{e}[/]"))
            self._scroll_bottom()

        # —— /sessions 列出已保存会话 ——
        elif head in ("/sessions", "/list", "/ls"):
            try:
                from core.context import list_sessions
                sessions = list_sessions()
                if not sessions:
                    self._chat.mount(Static("[dim]当前没有已保存的会话[/]"))
                else:
                    lines = [f"[bold]💾 已保存会话（共 {len(sessions)} 个）：[/]"]
                    lines.append("[dim]格式：编号  时间  消息数  大小[/]")
                    for i, s in enumerate(sessions[:20]):
                        size_kb = s["size"] / 1024
                        lines.append(f"  [{s['time']}] [cyan]{s['id']}[/]  {s['rounds']}条  {size_kb:.1f}KB")
                    self._chat.mount(Static("\n".join(lines)))
            except Exception as e:
                self._chat.mount(Static(f"[red]列表获取失败：{e}[/]"))
            self._scroll_bottom()

        # —— /resume 恢复历史会话 ——
        elif head in ("/resume", "/load", "/r"):
            try:
                from core.context import list_sessions, load_session
                sessions = list_sessions()
                if not sessions:
                    self._chat.mount(Static("[dim]没有可恢复的会话，请先用 /save 保存[/]"))
                    self._scroll_bottom()
                    return

                arg = parts[1].strip() if len(parts) > 1 else ""

                if arg:
                    # 有参数：直接恢复指定 session_id
                    target_id = arg
                else:
                    # 弹面板让用户选
                    target_id = self._show_resume_panel(sessions)
                    if target_id is None:
                        return  # 用户取消了

                # 恢复
                messages, _ = load_session(target_id)
                self.agent.messages = messages
                # 从消息中恢复 session_id（如果最后一条有记录）
                self._refresh_subtitle()
                self._chat.mount(Static(
                    f"[bold green]✓ 会话已恢复[/]\n"
                    f"  • 会话编号：[cyan]{target_id}[/]\n"
                    f"  • 消息：{len(messages)} 条\n"
                    f"  • 当前 tokens：{self.agent.current_tokens}"
                ))
            except Exception as e:
                self._chat.mount(Static(f"[red]恢复失败：{e}[/]"))
            self._scroll_bottom()

        # —— /quit 退出 ——
        elif head in ("/quit", "/q", "/exit", "/bye"):
            self._chat.mount(Static("[dim]👋 再见，自动保存当前会话...[/]"))
            self._scroll_bottom()
            # 自动保存
            try:
                from core.context import save_session
                save_session(self.agent.messages, self.agent.session_id)
            except Exception:
                pass
            self.exit()

        elif head in ("/help", "/?"):
            self._chat.mount(Static(
                "[bold]可用命令：[/]\n"
                "  /new  —— 重置会话（自动保存当前 + 重新发现技能）\n"
                "  /save  —— 手动保存当前会话\n"
                "  /sessions  —— 列出所有已保存会话\n"
                "  /resume  —— 恢复历史会话（弹选择面板）\n"
                "  /quit  —— 退出（自动保存）\n"
                "  /compact  —— 手动触发上下文压缩\n"
                "  /skills  —— 列出当前技能\n"
                "  /mcp  —— 查看 MCP Server 状态\n"
                "  /ctx  —— 查看上下文使用量\n"
                "  /archives  —— 列出压缩归档\n"
                "  /help  —— 显示本帮助\n"
                "\n"
                "[bold]快捷键：[/]\n"
                "  Ctrl+C —— 退出\n"
                "  Enter —— 发送消息",
            ))
            self._scroll_bottom()
        elif head == "/skills":
            skills = self.agent.discovered_skills
            if not skills:
                self._chat.mount(Static("[dim]当前未发现技能[/]"))
            else:
                lines = ["[bold]📚 技能：[/]"]
                for s in skills:
                    lines.append(f"  • [cyan]{s['name']}[/] — {s['description']}")
                self._chat.mount(Static("\n".join(lines)))
            self._scroll_bottom()
        elif head == "/mcp":
            info = self.agent.mcp.describe()
            self._chat.mount(Static(f"[bold]MCP Server：[/]\n{info}"))
            self._scroll_bottom()
        elif head == "/ctx":
            usage = self.agent.context_usage_display
            ratio = self.agent.context_usage_ratio * 100
            bar = "🟥" * int(ratio / 10) + "⬜" * (10 - int(ratio / 10))
            warning = " [red]⚠ 已达警告阈值，请执行 /compact[/]" if self.agent.context_warning else ""
            self._chat.mount(Static(
                f"[bold]上下文使用量：[/] {usage}\n"
                f"{bar} {ratio:.0f}%{warning}"
            ))
            self._scroll_bottom()
        elif head == "/archives":
            from core.context import list_archives
            archives = list_archives()
            if not archives:
                self._chat.mount(Static("[dim]当前无历史归档（执行 /compact 后会生成）[/]"))
            else:
                lines = [f"[bold]历史归档（共 {len(archives)} 个）：[/]"]
                for a in archives:
                    size_kb = a["size"] // 1024
                    lines.append(f"  • [cyan]{a['id']}[/] — {a['time']} — {size_kb} KB")
                self._chat.mount(Static("\n".join(lines)))
            self._scroll_bottom()
        elif head == "/compact":
            self._busy = True
            self._compact_thread()
        else:
            self._chat.mount(Static(f"[red]未知命令：{cmd}[/]，输入 /help 查看可用命令"))
            self._scroll_bottom()

    def _show_resume_panel(self, sessions: list[dict]) -> str | None:
        """把列表打印到 chat 区，提示用户用 /resume <id> 恢复"""
        lines = [f"[bold]📂 已保存会话（用 /resume <会话编号> 恢复）：[/]"]
        for s in sessions[:10]:
            lines.append(f"  • [cyan]{s['id']}[/]  {s['time']}  {s['rounds']}条  {s['size']/1024:.1f}KB")
        lines.append(f"\n[dim]共 {len(sessions)} 个会话[/]")
        self._chat.mount(Static("\n".join(lines)))
        self._scroll_bottom()
        return None  # 不阻塞等选择，交给用户手动 /resume <id>

    def _mount_user(self, text: str) -> None:
        self._chat.mount(Static(f"[bold cyan]你[/]\n{text}"))

    def _mount_agent_widget(self) -> Static:
        widget = Static("[bold blue]xAgent[/]\n")
        self._chat.mount(widget)
        return widget

    def _mount_ctx_indicator(self, prefix: str = "") -> None:
        """挂载一条上下文使用量小提示（每次问答结束后调用）"""
        usage = self.agent.context_usage_display
        msgs = len(self.agent.messages)
        ratio = self.agent.context_usage_ratio * 100
        # 根据比例选颜色
        if ratio >= 70:
            color = "red"
        elif ratio >= 50:
            color = "yellow"
        else:
            color = "dim"
        label = f"[{color}]📊 {prefix}上下文：{usage} · 消息 {msgs} 条[/]"
        self._chat.mount(Static(label))

    def _scroll_bottom(self) -> None:
        try:
            self._chat.scroll_end(animate=False)
        except Exception:
            try:
                self._chat.scroll_y = self._chat.max_scroll_y
            except Exception:
                pass

    def _show_overlay(self, snap: dict) -> None:
        """显示压缩结果面板（overlay 已在启动时 compose 好，只更新内容 + 设 visible）"""
        try:
            overlay = self._overlay
            if overlay is None:
                overlay = self.query_one("#compact-overlay", CompactDiffOverlay)
                self._overlay = overlay
            overlay.update_content(
                before_messages=snap["before_messages"],
                after_messages=snap["after_messages"],
                before_tokens=snap["before_tokens"],
                after_tokens=snap["after_tokens"],
                archive_id=snap["archive_id"],
            )
            overlay.visible = True
            overlay.refresh(layout=True)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self._chat.mount(Static(f"[red]面板显示异常：{tb[:500]}[/]"))
            self._scroll_bottom()

    def _hide_overlay(self) -> None:
        """隐藏压缩结果面板（ESC 快捷键）"""
        if self._overlay is not None:
            self._overlay.visible = False

    def action_close_overlay(self) -> None:
        """BINDINGS 绑定的 ESC 动作：如果 overlay 可见则关掉，否则不处理（让别的逻辑接手 ESC）"""
        if self._overlay is not None and self._overlay.visible:
            self._overlay.visible = False

    def _refresh_subtitle(self) -> None:
        """更新上下文状态栏（聊天区顶部常驻 widget + 顶栏 Header 双重更新）"""
        ctx = self.agent.context_usage_display
        msgs = len(self.agent.messages)
        ratio = self.agent.context_usage_ratio * 100
        cwd = Path.cwd()
        skills_count = len(self.agent.discovered_skills)

        # 根据比例选颜色
        if ratio >= 70:
            color = "red"
        elif ratio >= 50:
            color = "yellow"
        else:
            color = "cyan"

        bar_text = (
            f"[{color}]📊 {ctx} · 消息 {msgs} 条 · Skills {skills_count}[/]"
        )

        # 1. 更新聊天区顶部的常驻状态栏（最可靠，Textual Static.update 100% 生效）
        if self._ctx_bar is not None:
            self._ctx_bar.update(bar_text)

        # 2. 同时更新顶栏 App.subtitle（能生效最好，不行也不影响聊天区的状态栏）
        subtitle = f"{cwd}  |  Skills: {skills_count}  |  ctx: {ctx}"
        try:
            self.subtitle = subtitle
        except Exception:
            pass

    # ============== 后台流式对话 ==============
    def _chat_thread(self, text: str) -> None:
        """后台线程消费 Agent 事件流，UI 更新通过 call_from_thread 回到主线程"""
        import threading

        widget_ref = [None]
        buffer = [""]

        def worker():
            # 记录对话开始前的 tokens
            tokens_before = self.agent.current_tokens

            for ev in self.agent.chat_stream(text):
                kind = ev["type"]
                if kind == "token":
                    buffer[0] += ev["content"]
                    if widget_ref[0] is None:
                        self.call_from_thread(lambda: widget_ref.__setitem__(0, self._mount_agent_widget()))
                    else:
                        current = buffer[0]
                        w = widget_ref[0]
                        self.call_from_thread(lambda w=w, c=current: w.update(f"[bold blue]xAgent[/]\n{c}"))
                    self.call_from_thread(self._scroll_bottom)
                elif kind == "tool":
                    # loadSkill 特殊处理：只显示加载成功提示，不把 Skill 正文刷屏显示
                    tool_name = ev["name"]
                    elapsed = ev["elapsed_ms"]
                    if tool_name == "loadSkill":
                        result = ev["result"]
                        skill_label = ""
                        for line in result.splitlines():
                            if line.startswith("【Skill"):
                                skill_label = line.strip("【】").strip()
                                break
                        if not skill_label:
                            skill_label = "Skill"
                        self.call_from_thread(
                            lambda n=skill_label, t=elapsed:
                                self._chat.mount(Static(
                                    f"[dim]▶ 工具 loadSkill · {t:.0f} ms[/]\n"
                                    f"[dim green]✓ 已加载 {n}（正文已进入上下文）[/]"
                                ))
                        )
                    elif tool_name == "recallContext":
                        # recallContext 特殊处理：检索结果较长，折叠显示
                        result = ev["result"]
                        if len(result) > 500:
                            result_display = result[:500] + "\n[dim]...（检索结果已完整交给模型）[/]"
                        else:
                            result_display = result
                        self.call_from_thread(
                            lambda t=elapsed, r=result_display.replace("[", "\\["):
                                self._chat.mount(Static(
                                    f"[dim]▶ 工具 recallContext · {t:.0f} ms[/]\n{r}"
                                ))
                        )
                    else:
                        self.call_from_thread(
                            lambda n=tool_name, r=ev["result"].replace("[", "\\["), t=elapsed:
                                self._chat.mount(Static(f"[dim]▶ 工具 {n} · {t:.0f} ms[/]\n{r}"))
                        )
                    self.call_from_thread(self._scroll_bottom)
                elif kind == "warning":
                    # 上下文使用量警告
                    msg = ev["message"]
                    self.call_from_thread(lambda m=msg.replace("[", "\\["):
                        self._chat.mount(Static(f"[yellow]⚠ {m}[/]"))
                    )
                    self.call_from_thread(self._scroll_bottom)
                elif kind == "error":
                    msg = ev["message"]
                    self.call_from_thread(lambda: self._chat.mount(Static(f"[red]Error: {msg}[/]")))

            # —— 收尾：一轮对话结束后，显示上下文用量变化 + 刷新顶栏 ——
            tokens_after = self.agent.current_tokens
            tokens_delta = tokens_after - tokens_before

            def done():
                self._busy = False
                # 在 chat 区挂一条上下文用量指示（绿色增加、压缩后减少）
                if tokens_delta > 0:
                    delta_str = f"+{tokens_delta} (+{tokens_delta/1024:.1f}k)"
                elif tokens_delta < 0:
                    delta_str = f"{tokens_delta} ({tokens_delta/1024:.1f}k)"
                else:
                    delta_str = "不变"
                self._mount_ctx_indicator(prefix=f"本轮 Δ={delta_str}  ")
                self._refresh_subtitle()
                self._scroll_bottom()

            self.call_from_thread(done)

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    # ============== 上下文压缩线程 ==============
    def _compact_thread(self) -> None:
        """后台线程执行 /compact 压缩流程"""
        import threading

        def worker():
            widget_ref = [None]
            buffer = [""]
            snapshot_box = [None]
            tokens_before = self.agent.current_tokens

            # 节流：每 80ms 最多刷一次 UI
            import time
            last_flush = [0.0]

            def _flush_token():
                """把 buffer 当前内容刷到 UI（运行时调用，安全）"""
                if widget_ref[0] is not None:
                    try:
                        widget_ref[0].update(
                            f"[bold blue]压缩摘要[/]\n{buffer[0]}"
                        )
                        self._scroll_bottom()
                    except Exception:
                        pass

            for ev in self.agent.compact():
                kind = ev["type"]
                if kind == "compact_start":
                    self.call_from_thread(lambda: self._chat.mount(
                        Static("[bold yellow]● 开始压缩上下文...[/]")))
                    self.call_from_thread(self._scroll_bottom)
                elif kind == "archive_saved":
                    aid = ev["archive_id"]
                    path = ev["path"]
                    self.call_from_thread(lambda a=aid, p=path: self._chat.mount(
                        Static(f"[dim green]✓ 归档已保存：[/] {p}\n[dim green]✓ 归档编号：[/] [cyan]{a}[/]")))
                    self.call_from_thread(self._scroll_bottom)
                elif kind == "token":
                    buffer[0] += ev["content"]
                    now = time.time()
                    if widget_ref[0] is None:
                        # 第一个 token：先创建 widget
                        self.call_from_thread(lambda: widget_ref.__setitem__(0,
                            self._chat.mount(Static("[bold blue]压缩摘要[/]\n"))))
                        self.call_from_thread(lambda: widget_ref[0].update(
                            f"[bold blue]压缩摘要[/]\n{buffer[0]}"
                        ) if widget_ref[0] else None)
                        last_flush[0] = now
                    elif now - last_flush[0] >= 0.08:
                        # 节流：每 80ms 刷一次
                        self.call_from_thread(_flush_token)
                        last_flush[0] = now
                elif kind == "archive_replaced":
                    aid = ev["archive_id"]
                    self.call_from_thread(lambda a=aid: self._chat.mount(
                        Static(f"[dim green]✓ 历史已替换为摘要，原始上下文保留在 [cyan]{a}[/][/]")))
                    self.call_from_thread(self._scroll_bottom)
                elif kind == "compact_done":
                    aid = ev["archive_id"]
                    _snap = {
                        "before_messages": ev.get("before_messages", []),
                        "after_messages": ev.get("after_messages", []),
                        "before_tokens": ev.get("before_tokens", 0),
                        "after_tokens": ev.get("after_tokens", 0),
                        "archive_id": aid,
                    }
                    snapshot_box[0] = _snap
                    self.call_from_thread(lambda a=aid: self._chat.mount(
                        Static(f"[bold green]✓ 压缩完成[/] 归档编号：[cyan]{a}[/]")))
                    self.call_from_thread(self._scroll_bottom)
                    # 🎯 面板：找 overlay → update_content → visible=True（启动时就 compose 好，绝对不会失败）
                    self.call_from_thread(lambda s=_snap: self._show_overlay(s))
                elif kind == "compact_error":
                    msg = ev["message"]
                    self.call_from_thread(lambda m=msg: self._chat.mount(
                        Static(f"[red]压缩失败：{m}[/]")))
                    self.call_from_thread(self._scroll_bottom)
                    # 压缩失败：重置 busy 锁，允许用户继续输入
                    self._busy = False
                    return

            # —— 只有 compact_done 才会走到这里 ——
            tokens_after = self.agent.current_tokens
            saved = tokens_before - tokens_after

            def done():
                self._busy = False
                if saved > 0:
                    delta = f"节省 {saved} tokens ({saved/1024:.1f}k)"
                elif saved < 0:
                    delta = f"增加 {-saved} tokens ({-saved/1024:.1f}k)"
                else:
                    delta = "token 不变"
                self._chat.mount(Static(
                    f"[dim]📊 /compact {delta} | "
                    f"压缩前 {tokens_before/1024:.1f}k → 压缩后 {tokens_after/1024:.1f}k | "
                    f"当前：{self.agent.context_usage_display}[/]"
                ))
                self._refresh_subtitle()
                self._scroll_bottom()
                # 面板已在 compact_done 事件里立即弹出了，这里不再重复

            # for 循环结束后，确保最后的 token 内容也刷到 UI
            self.call_from_thread(_flush_token)
            self.call_from_thread(done)

        t = threading.Thread(target=worker, daemon=True)
        t.start()
