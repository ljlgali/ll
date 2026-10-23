"""
朴素版 Textual 界面：对话区 + 输入框
自动滚到底，支持 Ctrl+C / Ctrl+Q 退出
"""
from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer
from textual.widgets import Input, Static

from core.agent import Agent


class LAgentApp(App):
    TITLE = "LAgent"
    SUB_TITLE = "core / tui 分层架构"

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
        # agent 必须在 compose() 之前创建，_topbar_text() 会读它
        self.agent = Agent()
        self._busy = False

    def compose(self) -> ComposeResult:
        yield ScrollableContainer(id="chat")
        yield Input(
            placeholder="输入问题后 Enter 发送；Ctrl+C 退出",
            id="input",
        )

    def on_mount(self) -> None:
        self.query_one("#input", Input).focus()
        # 欢迎信息
        self._chat.mount(Static(
            "[bold green]LAgent 已启动[/]\n"
            "输入问题开始对话；Ctrl+C 退出。",
        ))

    @property
    def _chat(self) -> ScrollableContainer:
        return self.query_one("#chat", ScrollableContainer)

    # ============== 输入处理 ==============
    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text or self._busy:
            return

        # 手动滚到底（auto_scroll 在新 mount 后需要一帧延迟）
        self._mount_user(text)
        self._scroll_bottom()
        self._busy = True
        self._chat_thread(text)

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
                    self.call_from_thread(
                        lambda n=ev["name"], r=ev["result"], t=ev["elapsed_ms"]:
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
