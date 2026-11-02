# Python 高频代码片段（节选）

# 1. 安全地读取纯文本文件（兼容 UTF-8 / GBK）
def safe_read(path: str) -> str:
    for enc in ("utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return open(path, "r", encoding="utf-8", errors="replace").read()

# 2. 写文件（自动创建目录）
from pathlib import Path
def ensure_write(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

# 3. 用 requests 发 GET 请求（带超时和错误处理）
import requests
def http_get(url: str, timeout: int = 15) -> str:
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.text
    except requests.exceptions.Timeout:
        return "（请求超时）"
    except requests.exceptions.RequestException as e:
        return f"（请求失败：{e}）"

# 4. 递归扫描目录下所有 .py 文件
from pathlib import Path
def find_py_files(root: str) -> list:
    return [str(p) for p in Path(root).rglob("*.py")]

# 5. 带重试的网络请求（指数退避）
import time, random
def retry_request(url: str, max_retries: int = 3) -> str:
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            return r.text
        except requests.exceptions.RequestException:
            if attempt == max_retries:
                raise
            time.sleep(2 ** attempt + random.random())
