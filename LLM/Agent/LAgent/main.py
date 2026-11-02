# LAgent 统一入口：启动 TUI 界面
# 运行方式：任意目录下执行  python E:\LLM\LLM\Agent\LAgent\main.py
# 内部自动把 LAgent 项目根目录加进 sys.path
import sys
from pathlib import Path

# 把当前脚本所在目录（LAgent 项目根）加入 sys.path，
# 这样 cwd 是 E:\Office 也能正确 import tui / core
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from tui.app import LAgentApp

if __name__ == "__main__":
    LAgentApp().run()
