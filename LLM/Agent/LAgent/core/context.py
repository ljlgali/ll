# core/context.py —— 上下文压缩与历史检索
# 包含：Token 估算、归档保存（JSONL）、recallContext 关键词检索
# 实现上不依赖向量数据库或 Embedding，仅用 Python 标准库
import json
import os
from datetime import datetime
from pathlib import Path

# 项目根目录（定位 config.ini）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 压缩归档根目录 + 会话持久化目录（优先读 config.ini，回退默认值）
try:
    from core.config import load_agent_settings as _load_agent_settings
    _agent_cfg = _load_agent_settings()
except Exception:
    _agent_cfg = {}

AGENTS_ROOT = _PROJECT_ROOT / ".agents"
CONTEXT_DIR = _PROJECT_ROOT / _agent_cfg.get("context_dir", ".agents/context")
SESSIONS_DIR = _PROJECT_ROOT / _agent_cfg.get("sessions_dir", ".agents/sessions")

# 上下文窗口默认值（DeepSeek deepseek-chat 为 128k）
DEFAULT_CONTEXT_WINDOW = 128_000

# 触发警告的阈值（占上下文窗口的百分比）
WARNING_RATIO = 0.70

# Token 估算：中文约 1.5 字符/token，英文约 4 字符/token
# 取折中值 3 字符/token 作为通用估算
CHARS_PER_TOKEN = 3


def ensure_context_dir() -> Path:
    """确保归档目录存在，返回其路径"""
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    return CONTEXT_DIR


def estimate_tokens(text: str | list | dict) -> int:
    """粗略估算 Token 数（不依赖 tiktoken 等外部库）

    对字符串按字符数 / 3 估算；对列表/字典递归累加各字段。
    实际 Token 数可能有 ±30% 偏差，仅用于监控和告警。
    """
    if text is None:
        return 0
    if isinstance(text, str):
        return max(1, len(text) // CHARS_PER_TOKEN)
    if isinstance(text, list):
        return sum(estimate_tokens(item) for item in text)
    if isinstance(text, dict):
        return sum(estimate_tokens(str(v)) + estimate_tokens(k) for k, v in text.items())
    return estimate_tokens(str(text))


def estimate_messages_tokens(messages: list) -> int:
    """估算整份 messages 列表的 Token 数（含 role / content / tool_calls 等）"""
    total = 0
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        # role 字段占一点 token
        total += estimate_tokens(msg.get("role", ""))
        # content
        total += estimate_tokens(msg.get("content", ""))
        # tool_calls（assistant 发起的工具调用）
        for tc in msg.get("tool_calls") or []:
            total += estimate_tokens(tc.get("id", ""))
            total += estimate_tokens(tc.get("type", ""))
            fn = tc.get("function") or {}
            total += estimate_tokens(fn.get("name", ""))
            total += estimate_tokens(fn.get("arguments", ""))
        # tool 消息的 tool_call_id
        if msg.get("tool_call_id"):
            total += estimate_tokens(msg.get("tool_call_id"))
    # API 每轮还有少量结构开销，这里加一个固定系数
    total = int(total * 1.05)
    return total


# ============== 归档保存 ==============

def generate_archive_id() -> str:
    """生成归档编号：YYYYMMDD-HHMMSS"""
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def save_archive(messages: list, archive_id: str | None = None) -> tuple[str, Path]:
    """把当前 messages 以 JSONL 格式保存到归档文件

    返回 (archive_id, file_path)。成功落盘才返回，否则抛异常。
    """
    ensure_context_dir()
    aid = archive_id or generate_archive_id()
    file_path = CONTEXT_DIR / f"{aid}.jsonl"

    with open(file_path, "w", encoding="utf-8") as f:
        for i, msg in enumerate(messages):
            record = {
                "index": i,
                "saved_at": datetime.now().isoformat(timespec="seconds"),
                "message": msg,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return aid, file_path


def list_archives() -> list[dict]:
    """列出所有归档文件，返回 [{id, path, size, time}]"""
    ensure_context_dir()
    archives = []
    for f in sorted(CONTEXT_DIR.glob("*.jsonl")):
        archives.append({
            "id": f.stem,
            "path": str(f),
            "size": f.stat().st_size,
            "time": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds"),
        })
    return archives


# ============== 会话持久化（/save /resume）==============

def ensure_sessions_dir() -> Path:
    """确保会话目录存在，返回其路径"""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR


def save_session(messages: list, session_id: str | None = None,
                 metadata: dict | None = None) -> tuple[str, Path]:
    """保存当前会话为 JSON 文件，返回 (session_id, file_path)"""
    ensure_sessions_dir()
    if session_id is None:
        session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = SESSIONS_DIR / f"{session_id}.json"
    payload = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "messages": messages,
    }
    if metadata:
        payload["metadata"] = metadata
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return session_id, path


def load_session(session_id: str) -> tuple[list, dict | None]:
    """从 JSON 文件恢复会话，返回 (messages, metadata)。找不到抛 FileNotFoundError"""
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"会话文件不存在：{path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["messages"], data.get("metadata")


def list_sessions() -> list[dict]:
    """列出所有会话，返回 [{id, path, size, time, round_count}]"""
    ensure_sessions_dir()
    sessions = []
    for f in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
        round_count = 0
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            round_count = len(data.get("messages", []))
        except Exception:
            pass
        sessions.append({
            "id": f.stem,
            "path": str(f),
            "size": f.stat().st_size,
            "time": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "rounds": round_count,
        })
    return sessions


# ============== recallContext 检索 ==============

def recall_context(text: str, id: str | None = None, max_chars: int = 3000) -> str:
    """在归档中检索包含关键词 text 的原始内容片段

    - text：必需，关键词（简单子串匹配，不区分大小写）
    - id：可选，指定归档编号；不填则检索全部
    - max_chars：返回结果总长度上限，避免再次占满上下文

    返回 Markdown 格式的检索结果摘要。
    """
    if not text or not text.strip():
        return "错误：text 参数不能为空，请提供要查找的关键词"

    ensure_context_dir()
    keyword = text.strip().lower()

    # 确定要检索的文件
    if id:
        target = CONTEXT_DIR / f"{id}.jsonl"
        if not target.exists():
            archives = [a["id"] for a in list_archives()]
            hint = f"现有归档：{', '.join(archives)}" if archives else "当前无任何归档"
            return f"错误：归档 {id} 不存在。{hint}"
        files = [target]
    else:
        files = sorted(CONTEXT_DIR.glob("*.jsonl"))
        if not files:
            return "当前没有任何历史归档可供检索"

    # 逐文件逐行扫描，收集匹配片段
    hits: list[dict] = []
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = record.get("message") or {}
                content = _message_to_text(msg)
                if keyword in content.lower():
                    snippet = _extract_snippet(content, keyword)
                    hits.append({
                        "archive_id": fp.stem,
                        "role": msg.get("role", "?"),
                        "index": record.get("index", "?"),
                        "snippet": snippet,
                    })

    if not hits:
        scope = f"归档 {id}" if id else "所有归档"
        return f"在{scope}中未找到包含「{text}」的内容"

    # 整理输出，控制长度
    output_lines = [f"【检索关键词】{text}", f"【命中条数】{len(hits)}"]
    total = 0
    for h in hits[:15]:       # 最多展示 15 条
        block = (
            f"\n---\n"
            f"**归档** `{h['archive_id']}` | **角色** `{h['role']}` | **位置** 第 {h['index']} 条消息\n"
            f"{h['snippet']}"
        )
        output_lines.append(block)
        total += len(block)
        if total >= max_chars:
            remaining = len(hits) - output_lines.count("---")
            if remaining > 0:
                output_lines.append(f"\n...（还有 {remaining} 条未展示）")
            break

    return "\n".join(output_lines)


def _message_to_text(msg: dict) -> str:
    """把一条 message 转成可搜索的纯文本（含 content 和 tool 返回）"""
    parts = []
    c = msg.get("content")
    if isinstance(c, str):
        parts.append(c)
    elif isinstance(c, list):
        parts.append(" ".join(str(x) for x in c if x))
    # tool 消息的 tool_call_id 和 tool_calls 的 arguments 也纳入搜索
    if msg.get("tool_call_id"):
        parts.append(msg["tool_call_id"])
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        parts.append(fn.get("name", ""))
        parts.append(fn.get("arguments", ""))
    return "\n".join(parts)


def _extract_snippet(content: str, keyword: str, context: int = 80) -> str:
    """从 content 中抽取关键词前后 context 个字符的片段"""
    idx = content.lower().find(keyword.lower())
    if idx < 0:
        return content[:context * 2]
    start = max(0, idx - context)
    end = min(len(content), idx + len(keyword) + context)
    snippet = content[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet += "..."
    # 去掉多余换行，保持紧凑
    snippet = snippet.replace("\n", " ")
    return snippet


# ============== 压缩专用 Prompt ==============

COMPACT_PROMPT = """你是一名 AI Agent 的上下文管理助手。当前会话即将达到上下文窗口限制，需要将历史对话压缩为一份高质量的工作摘要，以便 Agent 在新的上下文中继续执行任务。

请认真阅读提供的历史上下文，提取对后续工作仍然有价值的信息，并生成一份约 5,000 Tokens 的 Markdown 摘要。

摘要应重点保留以下内容：

1. **用户目标与要求**：用户希望完成什么任务？有哪些必须遵守的约束、偏好和验收条件？
2. **已经完成的工作**：哪些任务已经完成？实现了哪些功能？获得了哪些已经验证的结果？
3. **当前工作状态**：Agent 正在处理什么任务？当前进展到哪一步？是否存在尚未解决的问题？
4. **关键技术信息**：保留重要的文件路径、函数名称、接口定义、配置项、执行命令、错误信息和必要的代码片段。
5. **关键决策与原因**：记录用户和 Agent 已经确定的技术方案，以及重要的设计取舍。
6. **下一步任务**：明确接下来应该执行的操作，以及需要继续验证的事项。

请遵守以下要求：

- 优先保留对后续任务有直接影响的信息，删除寒暄、重复讨论、过时的尝试和无关内容。
- 对已经验证的事实与尚未验证的推测作出明确区分。
- 不要将计划完成的任务描述为已经完成。
- 重要的文件路径、函数名称、配置名称和命令应保留准确原文。
- 对失败的尝试，只保留有助于避免重复错误的信息。
- 如果信息存在冲突，应优先保留用户最新确认的要求，并简要说明仍然存在的冲突。
- 如果某些历史细节无法在摘要中完整保留，可简要说明它们已保存到原始上下文归档中，后续可以通过 `recallContext` 工具重新检索。
- 使用清晰的 Markdown 结构输出摘要，不要附加解释或无关内容。

**最终目标：使一个从未阅读过原始对话的 Agent，仅凭这份摘要，就能够理解当前任务、继承关键决策，并继续开展工作。**"""
