"""
朴素版 Textual 界面：对话区 + 输入框
自动滚到底，支持 Ctrl+C / Ctrl+Q 退出
"""
import os
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer
from textual.widgets import Input, Static

from core.agent import Agent


class LAgentApp(App):
    TITLE = "LAgent"
    # SUB_TITLE 留空，__init__ 里根据 cwd + Skill 数动态设置
    SUB_TITLE = ""

    CSS = """
    #chat {
        height: 1fr;
    }
    #input {
        dock: bottom;
        height: 3;
    }
    """

    def __init__(self):
        super().__init__()
        # agent 必须在 compose() 之前创建
        self.agent = Agent()
        self._busy = False
        # 记录启动时的工作目录和 Skill 数，欢迎信息直接展示
        self._cwd = Path.cwd()
        self._skills_count = len(self.agent.discovered_skills)
        self._mcp_count = len(self.agent.mcp_tools)

    def compose(self) -> ComposeResult:
        yield ScrollableContainer(id="chat")
        yield Input(
            placeholder="输入问题后 Enter 发送；Ctrl+C 退出",
            id="input",
        )

    def on_mount(self) -> None:
        self.query_one("#input", Input).focus()
        # 欢迎信息：一进界面就显示工具位置（盘符路径）和 Skill 数
        self._chat.mount(Static(
            "[bold green]LAgent 已启动[/]\n"
            f"[dim]工作目录：[/]{self._cwd}\n"
            f"[dim]发现 Skill：[/]{self._skills_count} 个\n"
            f"[dim]MCP 工具：[/]{self._mcp_count} 个\n"
            "输入问题开始对话；Ctrl+C 退出。",
        ))

    @property
    def _chat(self) -> ScrollableContainer:
        return self.query_one("#chat", ScrollableContainer)

    # ============== 输入处理 ==============
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

        # 手动滚到底（auto_scroll 在新 mount 后需要一帧延迟）
        self._mount_user(text)
        self._scroll_bottom()
        self._busy = True
        self._chat_thread(text)

    def _handle_command(self, cmd: str) -> None:
        """处理 /new /help 等斜杠命令"""
        self._busy = False          # 命令不受 busy 锁限制
        parts = cmd.strip().split(maxsplit=1)
        head = parts[0].lower()

        if head in ("/new", "/reset", "/clear"):
            self.agent.reset()
            self._refresh_subtitle()
            self._chat.mount(Static(
                "[bold yellow]● 会话已重置[/]\n"
                f"发现 {len(self.agent.discovered_skills)} 个 Skill\n"
                f"session_id = {self.agent.session_id}",
            ))
            self._scroll_bottom()
        elif head in ("/help", "/?"):
            self._chat.mount(Static(
                "[bold]可用命令：[/]\n"
                "  /new  /reset  /clear —— 重置会话（重新发现 Skill）\n"
                "  /help  /? —— 显示本帮助\n"
                "  /skills —— 列出当前已发现的 Skill\n"
                "  /mcp —— 查看 MCP Server 连接状态与工具\n"
                "\n"
                "[bold]快捷键：[/]\n"
                "  Ctrl+C —— 退出程序\n"
                "  Enter —— 发送消息",
            ))
            self._scroll_bottom()
        elif head == "/skills":
            skills = self.agent.discovered_skills
            if not skills:
                self._chat.mount(Static("[dim]当前未发现任何 Skill[/]"))
            else:
                lines = ["[bold]已发现 Skill：[/]"]
                for s in skills:
                    lines.append(f"  • [cyan]{s['name']}[/] — {s['description']}")
                self._chat.mount(Static("\n".join(lines)))
            self._scroll_bottom()
        elif head == "/mcp":
            # 展示 MCP Server 连接状态与已注册的工具
            info = self.agent.mcp.describe()
            self._chat.mount(Static(f"[bold]MCP Server：[/]\n{info}"))
            self._scroll_bottom()
        else:
            self._chat.mount(Static(f"[red]未知命令：{cmd}[/]，输入 /help 查看可用命令"))
            self._scroll_bottom()

    def _mount_user(self, text: str) -> None:
        self._chat.mount(Static(f"[bold cyan]你[/]\n{text}"))

    def _mount_agent_widget(self) -> Static:
        widget = Static("[bold blue]LAgent[/]\n")
        self._chat.mount(widget)
        return widget

    def _scroll_bottom(self) -> None:
        try:
            self._chat.scroll_end(animate=False)
        except Exception:
            try:
                self._chat.scroll_y = self._chat.max_scroll_y
            except Exception:
                pass

    def _refresh_subtitle(self) -> None:
        """更新顶栏副标题（reset 后 Skill 数可能变化）"""
        cwd = Path.cwd()
        skills_count = len(self.agent.discovered_skills)
        self.SUB_TITLE = f"{cwd}  |  Skills: {skills_count}"

    # ============== 后台流式对话 ==============
    def _chat_thread(self, text: str) -> None:
        """后台线程消费 Agent 事件流，UI 更新通过 run_worker 回到主线程"""
        import threading

        widget_ref = [None]
        buffer = [""]

        def worker():
            for ev in self.agent.chat_stream(text):
                kind = ev["type"]
                if kind == "token":
                    buffer[0] += ev["content"]
                    if widget_ref[0] is None:
                        # 把返回值赋回 widget_ref[0]！
                        self.call_from_thread(lambda: widget_ref.__setitem__(0, self._mount_agent_widget()))
                    else:
                        current = buffer[0]
                        w = widget_ref[0]
                        self.call_from_thread(lambda w=w, c=current: w.update(f"[bold blue]LAgent[/]\n{c}"))
                    self.call_from_thread(self._scroll_bottom)
                elif kind == "tool":
                    # loadSkill 特殊处理：只显示加载成功提示，不把 Skill 正文刷屏显示
                    tool_name = ev["name"]
                    elapsed = ev["elapsed_ms"]
                    if tool_name == "loadSkill":
                        result = ev["result"]
                        # 从 load_skill 返回值里提取 Skill 名称
                        # 格式形如 "【Skill：horoscope-daily】..." 或 "【Skill xxx 附件】common-patterns.py"
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
                    else:
                        # 其他工具正常显示结果（[xx] 转义防 Textual 吞标记）
                        self.call_from_thread(
                            lambda n=tool_name, r=ev["result"].replace("[", "\\["), t=elapsed:
                                self._chat.mount(Static(f"[dim]▶ 工具 {n} · {t:.0f} ms[/]\n{r}"))
                        )
                    self.call_from_thread(self._scroll_bottom)
                elif kind == "error":
                    msg = ev["message"]
                    self.call_from_thread(lambda: self._chat.mount(Static(f"[red]Error: {msg}[/]")))
            # 收尾
            def done():
                self._busy = False
                self._scroll_bottom()
            self.call_from_thread(done)

        t = threading.Thread(target=worker, daemon=True)
        t.start()
