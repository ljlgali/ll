# core/functions.py —— 工具实现层
# 每个工具的本地实现 + 统一分发入口 dispatch(name, args)
# 界面层不直接调用这里的函数，一律经过 Agent 转发
import json
import mimetypes
import os
import shutil
import subprocess

TEXT_EXTS = {
    ".txt", ".md", ".py", ".json", ".csv", ".log", ".ini", ".cfg",
    ".html", ".css", ".js", ".xml", ".yaml", ".yml", ".bat", ".sh",
    ".java", ".c", ".cpp", ".h", ".sql", ".properties"
}


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
