import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from tui.app import LAgentApp

if __name__ == "__main__":
    LAgentApp().run()
