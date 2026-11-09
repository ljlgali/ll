# core/config.py —— 配置加载层
# 负责读取项目根目录的 config.ini，带默认值兜底
# 路径基于本文件定位，与启动时的工作目录无关
import configparser
from pathlib import Path

from openai import OpenAI

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.ini"


def _read_ini() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH, encoding="utf-8")
    return cfg


# ============== [llm] 段 ==============

def load_settings() -> dict:
    """读取 [llm] 配置并带默认值兜底"""
    cfg = _read_ini()
    if not cfg.has_section("llm"):
        return {"base_url": "", "api_key": "", "model": "deepseek-chat", "context_window": 128000}
    return {
        "base_url": cfg.get("llm", "base_url", fallback="https://api.deepseek.com"),
        "api_key": cfg.get("llm", "api_key", fallback=""),
        "model": cfg.get("llm", "model", fallback="deepseek-chat"),
        "context_window": cfg.getint("llm", "context_window", fallback=128000),
    }


def create_client() -> tuple[OpenAI, str]:
    """创建 OpenAI 客户端，返回 (client, model_name)"""
    s = load_settings()
    client = OpenAI(base_url=s["base_url"], api_key=s["api_key"])
    return client, s["model"]


def get_context_window() -> int:
    """返回模型上下文窗口大小"""
    return load_settings()["context_window"]


# ============== [search] 段 ==============

def load_search_settings() -> dict:
    cfg = _read_ini()
    if cfg.has_section("search"):
        return dict(cfg["search"])
    return {}


# ============== [agent] 段 ==============

def load_agent_settings() -> dict:
    """读取 [agent] 配置，带默认值兜底"""
    cfg = _read_ini()
    def _g(section, key, default):
        if cfg.has_option(section, key):
            return cfg.get(section, key)
        return default
    return {
        "warning_ratio": cfg.getfloat("agent", "warning_ratio", fallback=0.70) if cfg.has_section("agent") else 0.70,
        "compact_target_tokens": cfg.getint("agent", "compact_target_tokens", fallback=5000) if cfg.has_section("agent") else 5000,
        "skills_dirs": _g("agent", "skills_dirs", ".agents/skills"),
        "sessions_dir": _g("agent", "sessions_dir", ".agents/sessions"),
        "context_dir": _g("agent", "context_dir", ".agents/context"),
        "mcp_async_load": cfg.getboolean("agent", "mcp_async_load", fallback=True) if cfg.has_section("agent") else True,
    }


# ============== [tui] 段 ==============

def load_tui_settings() -> dict:
    cfg = _read_ini()
    if not cfg.has_section("tui"):
        return {"theme": "dark", "show_mcp_sidebar": True}
    return {
        "theme": cfg.get("tui", "theme", fallback="dark"),
        "show_mcp_sidebar": cfg.getboolean("tui", "show_mcp_sidebar", fallback=True),
    }
