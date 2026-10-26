# core/functions.py —— 工具实现层
# 每个工具的本地实现 + 统一分发入口 dispatch(name, args)
# 界面层不直接调用这里的函数，一律经过 Agent 转发
import json
import mimetypes
import os
import shutil
import subprocess

import requests
import trafilatura

from core.config import load_search_settings

TEXT_EXTS = {
    ".txt", ".md", ".py", ".json", ".csv", ".log", ".ini", ".cfg",
    ".html", ".css", ".js", ".xml", ".yaml", ".yml", ".bat", ".sh",
    ".java", ".c", ".cpp", ".h", ".sql", ".properties"
}

# 千帆智能搜索生成 API 地址与请求超时（秒）
QIANFAN_SEARCH_URL = "https://qianfan.baidubce.com/v2/ai_search"
SEARCH_TIMEOUT = 30
# fetchWeb / RunCli 的通用限制
FETCH_TIMEOUT = 25          # curl 下载网页超时
CLI_TIMEOUT = 30            # 本地命令执行超时
MAX_OUTPUT_CHARS = 4000     # 过长输出截断阈值


def get_current_time() -> str:
    """调用本地 date 命令获取当前日期和时间（不使用 Python datetime）"""
    try:
        r = subprocess.run("date /t & time /t", shell=True, capture_output=True, text=True)
        out = (r.stdout or "").strip()
        return out if out else f"未能获取本机时间（返回码 {r.returncode}）"
    except Exception as e:
        return f"调用本地 date 命令失败：{e}"


def is_leap_year(year: int) -> str:
    """本地计算闰年，返回带依据的完整信息"""
    rule = "闰年判断依据：年份能被4整除且不能被100整除，或者能被400整除"
    if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
        return f"✅ 调用工具：isLeapYear\n工具结果：{year} 是闰年\n{rule}"
    return f"✅ 调用工具：isLeapYear\n工具结果：{year} 不是闰年\n{rule}"


def get_cwd() -> str:
    """获取当前工作目录"""
    return os.getcwd()


def list_files(path: str) -> str:
    """列出指定目录下的所有文件和子目录"""
    if not os.path.isdir(path):
        return f"错误：目录不存在 -> {path}"
    items = os.listdir(path)
    if not items:
        return f"目录 {path} 为空"
    dirs = sorted(i for i in items if os.path.isdir(os.path.join(path, i)))
    files = sorted(i for i in items if os.path.isfile(os.path.join(path, i)))
    out = [f"目录 {path} 下共 {len(items)} 项："]
    if dirs:
        out.append("【子目录】" + "、".join(dirs))
    if files:
        out.append("【文件】" + "、".join(files))
    return "\n".join(out)


def get_file_type(path: str) -> str:
    """获取指定文件的文件类型"""
    if not os.path.exists(path):
        return f"错误：文件不存在 -> {path}"
    ext = os.path.splitext(path)[1].lower()
    mime = mimetypes.guess_type(path)[0] or "未知"
    kind = "纯文本文件" if ext in TEXT_EXTS else "非纯文本文件（二进制）"
    return (f"文件名：{os.path.basename(path)}\n"
            f"扩展名：{ext or '无'}\n"
            f"MIME类型：{mime}\n"
            f"类型判断：{kind}")


def read_file(path: str) -> str:
    """获取指定纯文本文件的内容"""
    if not os.path.isfile(path):
        return f"错误：文件不存在 -> {path}"
    if os.path.splitext(path)[1].lower() not in TEXT_EXTS:
        return f"错误：仅支持纯文本格式文件，{os.path.basename(path)} 不是纯文本文件"
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return content if content else "（文件为空）"
    except UnicodeDecodeError:
        return f"错误：{os.path.basename(path)} 无法按UTF-8文本读取，可能不是纯文本文件"
    except Exception as e:
        return f"读取失败：{e}"


def create_file(dir_path: str, filename: str, content: str = "") -> str:
    """根据指定的目录和文件名创建新文件"""
    if not os.path.isdir(dir_path):
        return f"错误：目录不存在 -> {dir_path}"
    path = os.path.join(dir_path, filename)
    if os.path.exists(path):
        return f"错误：文件已存在，未创建 -> {path}"
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"创建成功：{path}（初始内容 {len(content)} 字符）"
    except Exception as e:
        return f"创建失败：{e}"


def edit_file(path: str, content: str, mode: str = "overwrite") -> str:
    """编辑指定纯文本文件：overwrite 覆盖 / append 追加"""
    if not os.path.isfile(path):
        return f"错误：文件不存在 -> {path}"
    if os.path.splitext(path)[1].lower() not in TEXT_EXTS:
        return f"错误：仅支持纯文本格式文件，{os.path.basename(path)} 不是纯文本文件"
    try:
        if mode == "append":
            text = content if os.path.getsize(path) == 0 else "\n" + content
            with open(path, "a", encoding="utf-8") as f:
                f.write(text)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        return f"编辑成功（{mode}）：{path}"
    except Exception as e:
        return f"编辑失败：{e}"


def create_dir(path: str) -> str:
    """创建新目录"""
    if os.path.exists(path):
        return f"错误：路径已存在，未创建 -> {path}"
    try:
        os.makedirs(path)
        return f"创建成功：{path}"
    except Exception as e:
        return f"创建失败：{e}"


def delete_dir(path: str) -> str:
    """删除目录（支持非空目录）"""
    if not os.path.isdir(path):
        return f"错误：目录不存在 -> {path}"
    try:
        count = sum(len(files) for _, _, files in os.walk(path))
        shutil.rmtree(path)
        return f"删除成功：{path}（含 {count} 个文件）"
    except Exception as e:
        return f"删除失败：{e}"


def delete_file(path: str) -> str:
    """删除文件"""
    if not os.path.isfile(path):
        return f"错误：文件不存在 -> {path}"
    try:
        os.remove(path)
        return f"删除成功：{path}"
    except Exception as e:
        return f"删除失败：{e}"


def rename_path(path: str, new_name: str) -> str:
    """重命名文件或目录（保留原所在目录）"""
    if not os.path.exists(path):
        return f"错误：路径不存在 -> {path}"
    target = os.path.join(os.path.dirname(path), os.path.basename(new_name))
    if os.path.exists(target):
        return f"错误：目标名称已存在，未重命名 -> {target}"
    try:
        is_dir = os.path.isdir(path)
        os.rename(path, target)
        return f"重命名成功：{'目录' if is_dir else '文件'} {path} -> {target}"
    except Exception as e:
        return f"重命名失败：{e}"


# ========== （一）searchWeb：百度千帆智能搜索生成 ==========
def search_web(query: str) -> str:
    """调用百度千帆智能搜索生成API，返回搜索摘要与参考来源（标题+URL）"""
    key = (load_search_settings().get("baidu_qianfan_api_key") or "").strip()
    if not key:
        return ("错误：缺少配置。请在 config.ini 的 [search] 小节中填写 "
                "baidu_qianfan_api_key（百度千帆 API Key）后重试")
    payload = {
        "messages": [{"role": "user", "content": query}],
        "search_source": "baidu_search_v2",
        "resource_type_filter": [{"type": "web", "top_k": 5}],
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    try:
        resp = requests.post(QIANFAN_SEARCH_URL, json=payload,
                             headers=headers, timeout=SEARCH_TIMEOUT)
    except requests.exceptions.Timeout:
        return f"错误：搜索请求超时（{SEARCH_TIMEOUT} 秒），请稍后重试"
    except requests.exceptions.RequestException as e:
        return f"错误：网络请求失败 -> {e}"

    try:
        data = resp.json()
    except ValueError:
        return f"错误：API 返回内容无法解析（HTTP {resp.status_code}）"

    # API 层错误：兼容 {"error":{...}} 与 {"error_code":...,"error_msg":...} 两种结构
    if resp.status_code != 200 or "error" in data or "error_code" in data:
        err = data.get("error") if isinstance(data.get("error"), dict) else data
        code = err.get("code", err.get("error_code", resp.status_code))
        msg = err.get("message", err.get("error_msg", str(err)))
        return f"错误：搜索API返回错误（{code}）->{msg}"

    refs = data.get("references") or []
    lines = []
    answer = (data.get("answer") or "").strip()
    if answer:
        lines.append(f"【搜索摘要】{answer}")
    if not refs:
        if answer:
            lines.append("【参考来源】无")
            return "\n".join(lines)
        return f"搜索完成：未找到与「{query}」相关的结果"
    lines.append("【参考来源】")
    for i, ref in enumerate(refs, 1):
        title = (ref.get("title") or "无标题").strip()
        url = (ref.get("url") or "").strip()
        snippet = ((ref.get("content") or ref.get("snippet") or "").strip())
        if len(snippet) > 150:
            snippet = snippet[:150] + "..."
        lines.append(f"{i}. {title}\n   {url}")
        if snippet:
            lines.append(f"   摘要：{snippet}")
    return "\n".join(lines)


# ========== （二）fetchWeb：curl 下载 + trafilatura 提取正文 ==========
def fetch_web(url: str) -> str:
    """用本地curl（参数列表方式，不用shell=True）下载网页，trafilatura 提取正文转 Markdown"""
    if not url.lower().startswith(("http://", "https://")):
        return f"错误：无效的URL -> {url}（需以 http:// 或 https:// 开头）"
    try:
        proc = subprocess.run(
            ["curl", "-s", "-L", "--max-time", str(FETCH_TIMEOUT),
             "-A", "Mozilla/5.0 (compatible; LAgent/1.0)", url],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            shell=False, timeout=FETCH_TIMEOUT + 5,
        )
    except subprocess.TimeoutExpired:
        return f"错误：下载网页超时（{FETCH_TIMEOUT} 秒）-> {url}"
    except FileNotFoundError:
        return "错误：未找到本地 curl 程序，请确认系统已安装 curl"
    except Exception as e:
        return f"错误：调用 curl 失败 -> {e}"

    if proc.returncode != 0:
        err = (proc.stderr or "").strip()[:200]
        return f"错误：curl 访问失败（退出码 {proc.returncode}）->{err or url}"
    html = proc.stdout or ""
    if not html.strip():
        return f"错误：网页内容为空 -> {url}"

    try:
        markdown = trafilatura.extract(
            html, output_format="markdown",
            include_links=True, include_tables=True,
            include_images=False, favor_recall=True,
        )
    except Exception as e:
        return f"错误：HTML 解析失败 -> {e}"
    if not markdown or not markdown.strip():
        return f"错误：无法从该网页提取正文 -> {url}"
    text = markdown.strip()
    if len(text) > MAX_OUTPUT_CHARS:
        text = text[:MAX_OUTPUT_CHARS] + f"\n\n（正文过长，已截断：原文约 {len(markdown)} 字符）"
    return f"【URL】{url}\n\n【正文 Markdown】\n{text}"


# ========== （三）RunCli：执行本地命令行程序 ==========
def _truncate(text: str, label: str) -> str:
    """过长输出截断并标明截断情况"""
    if len(text) > MAX_OUTPUT_CHARS:
        return text[:MAX_OUTPUT_CHARS] + f"\n...（{label}过长，已截断：原文 {len(text)} 字符）"
    return text


def _decode_output(data: bytes) -> str:
    """控制台输出解码：优先 UTF-8，失败退 GBK（中文 Windows 控制台默认编码）"""
    if not data:
        return ""
    for enc in ("utf-8", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def run_cli(command: str, args: list) -> str:
    """以参数列表 + shell=False 方式执行本地CLI，返回 stdout/stderr/退出码"""
    if not command or not command.strip():
        return "错误：command 不能为空"
    cmd_list = [command.strip()] + [str(a) for a in (args or [])]
    try:
        proc = subprocess.run(
            cmd_list, capture_output=True,
            shell=False, timeout=CLI_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return f"错误：命令执行超时（{CLI_TIMEOUT} 秒）-> {' '.join(cmd_list)}"
    except FileNotFoundError:
        return f"错误：未找到程序 {command}，请确认已安装并加入 PATH"
    except OSError as e:
        return f"错误：执行失败 -> {e}"

    stdout = _truncate(_decode_output(proc.stdout).strip() or "（无输出）", "标准输出")
    stderr = _truncate(_decode_output(proc.stderr).strip() or "（无）", "标准错误")
    status = "成功" if proc.returncode == 0 else "失败"
    return (f"命令：{' '.join(cmd_list)}\n"
            f"退出码：{proc.returncode}（{status}）\n"
            f"【stdout】\n{stdout}\n"
            f"【stderr】\n{stderr}")


# ========== 统一分发：工具名 -> (函数, 参数组装) ==========
def dispatch(name: str, args: dict) -> str:
    """根据工具名和参数调用对应实现，返回工具结果字符串"""
    handlers = {
        "getDate": lambda: get_current_time(),
        "isLeapYear": lambda: is_leap_year(args["year"]),
        "getCwd": lambda: get_cwd(),
        "listFiles": lambda: list_files(args["path"]),
        "getFileType": lambda: get_file_type(args["path"]),
        "readFile": lambda: read_file(args["path"]),
        "createFile": lambda: create_file(args["dir"], args["filename"], args.get("content", "")),
        "editFile": lambda: edit_file(args["path"], args["content"], args.get("mode", "overwrite")),
        "createDir": lambda: create_dir(args["path"]),
        "deleteDir": lambda: delete_dir(args["path"]),
        "deleteFile": lambda: delete_file(args["path"]),
        "renamePath": lambda: rename_path(args["path"], args["new_name"]),
        "searchWeb": lambda: search_web(args["query"]),
        "fetchWeb": lambda: fetch_web(args["url"]),
        "RunCli": lambda: run_cli(args["command"], args.get("args", [])),
    }
    handler = handlers.get(name)
    if handler is None:
        return f"错误：未知工具 {name}"
    try:
        return handler()
    except KeyError as e:
        return f"错误：工具 {name} 缺少参数 {e}"
    except json.JSONDecodeError as e:
        return f"错误：工具参数解析失败 {e}"
