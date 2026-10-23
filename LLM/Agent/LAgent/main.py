# LAgent 统一入口：启动 TUI 界面
# 运行方式：在 LAgent 目录下执行  python main.py
from tui.app import LAgentApp

if __name__ == "__main__":
    LAgentApp().run()
