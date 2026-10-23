# core 包：业务核心层，与界面完全解耦
# 未来新增 web / desktop / mobile 等前端时，直接复用 core 即可，无需改动本包
from core.agent import Agent

__all__ = ["Agent"]
