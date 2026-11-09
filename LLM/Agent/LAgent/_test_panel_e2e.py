"""正确的端到端面板测试：用 call_from_thread 调度"""
import sys, os, time, threading
sys.path.insert(0, r"E:\LLM\LLM\Agent\LAgent")

from core.agent import Agent
print("=== Step 1: agent.compact() ===")
a = Agent()
a.messages = [
    {"role": "system", "content": "你是农业专家"},
    {"role": "user", "content": "今天星期几？"},
    {"role": "assistant", "content": "星期四"},
]
events = []
for ev in a.compact():
    events.append(ev["type"])
print(f"  事件: {events[:5]}... 最后: {events[-3:]}")
print(f"  compact_done: {'compact_done' in events}")

print("\n=== Step 2: 在真实 TUI 里 mount 面板（用 call_from_thread）===")
from tui.app import LAgentApp, CompactDiffOverlay
from textual.containers import ScrollableContainer, Horizontal

panel_ok = [False]
panel_err = [None]
simple_ok = [False]

def run_test():
    app = LAgentApp()

    def background():
        time.sleep(1.5)  # 等 TUI 完全启动

        snap = {
            "before_messages": [
                {"role": "system", "content": "你是农业专家"},
                {"role": "user", "content": "今天星期几？"},
                {"role": "assistant", "content": "星期四"},
            ],
            "after_messages": [
                {"role": "system", "content": "你是农业专家"},
                {"role": "assistant", "content": "## 摘要\n用户问星期几，答星期四。"},
            ],
            "before_tokens": 50,
            "after_tokens": 30,
            "archive_id": "TEST-001",
        }

        # 测试 A: CompactDiffOverlay（全屏覆盖层）
        def try_overlay():
            try:
                overlay = CompactDiffOverlay(
                    before_messages=snap["before_messages"],
                    after_messages=snap["after_messages"],
                    before_tokens=snap["before_tokens"],
                    after_tokens=snap["after_tokens"],
                    archive_id=snap["archive_id"],
                )
                app.screen.mount(overlay)
                panel_ok[0] = True
                print("  ✅ CompactDiffOverlay mount 成功！（你应该能看到弹层 2 秒）")
                time.sleep(2)
                try:
                    overlay.remove()
                except Exception:
                    pass
                print("  ✅ overlay remove 成功")
            except Exception as e:
                import traceback
                panel_err[0] = traceback.format_exc()
                print(f"  ❌ CompactDiffOverlay 失败：{e}")
                traceback.print_exc()

        # 测试 B: 简化版（Horizontal in chat）
        def try_simple():
            try:
                h = Horizontal()
                left = ScrollableContainer(
                    __import__('textual.widgets', fromlist=['Static']).Static("⬅ 压缩前\n3条消息...")
                )
                right = ScrollableContainer(
                    __import__('textual.widgets', fromlist=['Static']).Static("➡ 压缩后\n2条摘要...")
                )
                h.mount(left)
                h.mount(right)
                app._chat.mount(h)
                simple_ok[0] = True
                print("  ✅ 简化版 Horizontal mount 成功！")
            except Exception as e:
                import traceback
                print(f"  ❌ 简化版失败：{e}")
                traceback.print_exc()

        # 关键！用 call_from_thread 调度到主线程
        app.call_from_thread(try_overlay)
        app.call_from_thread(try_simple)

        time.sleep(1)
        app.call_from_thread(app.exit)

    threading.Thread(target=background, daemon=True).start()
    app.run()

run_test()

print("\n=== Step 3: 结果 ===")
print(f"  CompactDiffOverlay OK: {panel_ok[0]}")
print(f"  简化版 Horizontal OK: {simple_ok[0]}")
if panel_err[0]:
    print(f"  错误:\n{panel_err[0]}")
