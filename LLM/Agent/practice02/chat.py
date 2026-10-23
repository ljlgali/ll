import time
import configparser
import json
import os
import shutil
import mimetypes
from openai import OpenAI
from datetime import datetime

DELAY = 0.02

TEXT_EXTS = {
    ".txt", ".md", ".py", ".json", ".csv", ".log", ".ini", ".cfg",
    ".html", ".css", ".js", ".xml", ".yaml", ".yml", ".bat", ".sh",
    ".java", ".c", ".cpp", ".h", ".sql", ".properties"
}

cfg = configparser.ConfigParser()
cfg.read("config.ini", encoding="utf-8")
client = OpenAI(
    base_url=cfg["llm"]["base_url"],
    api_key=cfg["llm"]["api_key"],
)

# ========== 两个工具：getDate + isLeapYear ==========
tools = [
    {
        "type": "function",
        "function": {
            "name": "getDate",
            "description": "获取本机当前的日期和时间。只要用户的问题涉及时间、日期、几点、几号、多久之后、现在时刻、倒计时、对比时间等一切和实时时间相关的内容，你都必须调用这个工具获取最新时间，禁止使用记忆里的旧时间。",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "isLeapYear",
            "description": "判断输入的年份是不是闰年，调用时必须传入year参数。闰年规则：能被4整除且不能被100整除，或者能被400整除。",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "待判断的年份，例如2026"
                    }
                },
                "required": ["year"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getCwd",
            "description": "获取当前工作目录的绝对路径。用户问“当前目录/工作目录/在哪个目录”时调用。",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "listFiles",
            "description": "列出指定目录下的所有文件和子目录名称。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "目标目录的绝对路径，例如 E:\\LLM\\LLM\\Agent\\practice02"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getFileType",
            "description": "获取指定文件的文件类型，返回扩展名、MIME类型以及是否为纯文本文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件的绝对路径，例如 E:\\LLM\\LLM\\Agent\\practice02\\config.ini"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "readFile",
            "description": "获取指定文件的内容，仅支持纯文本格式文件（txt、md、py、json、csv 等），二进制文件会返回不支持。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "待读取文件的绝对路径"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "createFile",
            "description": "根据指定的目录和文件名创建一个新的纯文本文件，可同时写入初始内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir": {
                        "type": "string",
                        "description": "新文件所在目录的绝对路径"
                    },
                    "filename": {
                        "type": "string",
                        "description": "新文件名，需带扩展名，例如 note.txt"
                    },
                    "content": {
                        "type": "string",
                        "description": "新文件的初始内容，可为空"
                    }
                },
                "required": ["dir", "filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "editFile",
            "description": "编辑指定文件的内容，仅支持纯文本格式文件。mode=overwrite 覆盖原内容，mode=append 在文件末尾追加内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "待编辑文件的绝对路径"
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的新内容"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["overwrite", "append"],
                        "description": "编辑方式：overwrite 覆盖，append 追加，默认 overwrite"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "createDir",
            "description": "创建一个新目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "待创建目录的绝对路径"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deleteDir",
            "description": "删除指定目录及其全部内容，支持删除非空目录。高危操作，执行前必须确认路径无误。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "待删除目录的绝对路径"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deleteFile",
            "description": "删除指定文件。高危操作，执行前必须确认路径无误。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "待删除文件的绝对路径"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "renamePath",
            "description": "重命名指定的文件或目录。new_name 只写新名称（含扩展名），文件或目录仍保留在原目录下。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "原文件或目录的绝对路径"
                    },
                    "new_name": {
                        "type": "string",
                        "description": "新名称，需带扩展名，例如 readme.md，不需要写路径"
                    }
                },
                "required": ["path", "new_name"]
            }
        }
    }
]

messages = [
    {
        "role": "system",
        "content": "你是一个Agent。和时间日期相关，调用getDate；用户询问某一年是否是闰年，调用isLeapYear，传入year参数。涉及本地文件操作时：获取当前目录用getCwd；列出目录内容用listFiles；查看文件类型用getFileType；读取文件内容用readFile；创建新文件用createFile；编辑文件内容用editFile；创建目录用createDir；删除目录用deleteDir；删除文件用deleteFile；重命名文件或目录用renamePath。禁止编造结果，必须调用工具。用户只问几点就只输出时分秒，问日期输出年月日。输出闰年结果时，展示：调用工具名称、工具返回结果、闰年判断依据。工具返回的内容要如实转述给用户。"
    }
]


def get_current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_leap_year(year: int) -> str:
    """本地计算闰年，返回带依据的完整信息"""
    rule = "闰年判断依据：年份能被4整除且不能被100整除，或者能被400整除"
    if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
        result = f"✅ 调用工具：isLeapYear\n工具结果：{year} 是闰年\n{rule}"
    else:
        result = f"✅ 调用工具：isLeapYear\n工具结果：{year} 不是闰年\n{rule}"
    return result


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


while True:
    prompt = input("please input prompt :")
    print("---")
    messages.append({"role": "user", "content": prompt})
    try:
        while True:
            # 每一轮都带上 tools，模型才能正常发起工具调用
            stream = client.chat.completions.create(
                model=cfg["llm"]["model"],
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=True
            )
            reply = ""
            calls = {}
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.tool_calls:
                    for d in delta.tool_calls:
                        item = calls.setdefault(d.index, {"id": "", "name": "", "arguments": ""})
                        if d.id:
                            item["id"] = d.id
                        if d.function and d.function.name:
                            item["name"] = d.function.name
                        if d.function and d.function.arguments:
                            item["arguments"] += d.function.arguments
                if delta.content:
                    reply += delta.content
                    for char in delta.content:
                        print(char, end="", flush=True)
                        time.sleep(DELAY)

            # 模型没有要求调用工具，说明已经给出最终回答
            if not calls:
                print()
                messages.append({"role": "assistant", "content": reply})
                break

            messages.append({
                "role": "assistant",
                "content": reply or None,
                "tool_calls": [
                    {
                        "id": item["id"],
                        "type": "function",
                        "function": {"name": item["name"], "arguments": item["arguments"]}
                    }
                    for item in calls.values()
                ]
            })

            for item in calls.values():
                name = item["name"]
                args = json.loads(item["arguments"]) if item["arguments"] else {}
                print(f"[LOG] 调用工具 {name}")

                if name == "getDate":
                    result = get_current_time()
                elif name == "isLeapYear":
                    result = is_leap_year(args["year"])
                elif name == "getCwd":
                    result = get_cwd()
                elif name == "listFiles":
                    result = list_files(args["path"])
                elif name == "getFileType":
                    result = get_file_type(args["path"])
                elif name == "readFile":
                    result = read_file(args["path"])
                elif name == "createFile":
                    result = create_file(args["dir"], args["filename"], args.get("content", ""))
                elif name == "editFile":
                    result = edit_file(args["path"], args["content"], args.get("mode", "overwrite"))
                elif name == "createDir":
                    result = create_dir(args["path"])
                elif name == "deleteDir":
                    result = delete_dir(args["path"])
                elif name == "deleteFile":
                    result = delete_file(args["path"])
                elif name == "renamePath":
                    result = rename_path(args["path"], args["new_name"])
                else:
                    result = f"错误：未知工具 {name}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": item["id"],
                    "content": result
                })

    except Exception as e:
        print("Error:", e)
