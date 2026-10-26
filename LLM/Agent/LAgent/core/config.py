# core/config.py —— 配置加载层
# 负责读取项目根目录的 config.ini 并创建 OpenAI 客户端
# 路径基于本文件定位，与启动时的工作目录无关
import configparser
from pathlib import Path

from openai import OpenAI

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.ini"


def load_settings() -> dict:
    """读取 [llm] 配置，返回 dict"""
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH, encoding="utf-8")
    return dict(cfg["llm"])


def load_search_settings() -> dict:
    """读取 [search] 配置（千帆 API Key 等），小节不存在则返回空 dict"""
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH, encoding="utf-8")
    if cfg.has_section("search"):
        return dict(cfg["search"])
    return {}


def create_client() -> tuple[OpenAI, str]:
    """创建 OpenAI 客户端，返回 (client, model)"""
    s = load_settings()
    client = OpenAI(base_url=s["base_url"], api_key=s["api_key"])
    return client, s["model"]
