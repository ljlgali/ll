# core/tools.py —— 工具声明层
# 只放"给模型看的"工具 JSON Schema 与 system 提示词，不含任何实现逻辑

SYSTEM_PROMPT = (
    "你是一个Agent。只要用户的问题涉及时间、日期、几点、几号、现在时刻等和实时时间相关的内容，"
    "都必须调用getDate工具获取本机最新时间，禁止使用记忆里的旧时间。"
    "用户询问某一年是否是闰年，调用isLeapYear，传入year参数。"
    "涉及本地文件操作时：获取当前目录用getCwd；列出目录内容用listFiles；查看文件类型用getFileType；"
    "读取文件内容用readFile；创建新文件用createFile；编辑文件内容用editFile；创建目录用createDir；"
    "删除目录用deleteDir；删除文件用deleteFile；重命名文件或目录用renamePath。"
    "禁止编造结果，必须调用工具。用户只问几点就只输出时分秒，问日期输出年月日。"
    "输出闰年结果时，展示：调用工具名称、工具返回结果、闰年判断依据。"
    "工具返回的内容要如实转述给用户。"
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "getDate",
            "description": "获取本机当前的日期和时间。只要用户的问题涉及时间、日期、几点、几号、多久之后、现在时刻、倒计时、对比时间等一切和实时时间相关的内容，你都必须调用这个工具获取最新时间，禁止使用记忆里的旧时间。",
            "parameters": {"type": "object", "properties": {}}
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
                    "year": {"type": "integer", "description": "待判断的年份，例如2026"}
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
            "parameters": {"type": "object", "properties": {}}
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
                    "path": {"type": "string", "description": "目标目录的绝对路径，例如 E:\\LLM\\LLM\\Agent\\XAgent"}
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
                    "path": {"type": "string", "description": "文件的绝对路径，例如 E:\\LLM\\LLM\\Agent\\XAgent\\config.ini"}
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
                    "path": {"type": "string", "description": "待读取文件的绝对路径"}
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
                    "dir": {"type": "string", "description": "新文件所在目录的绝对路径"},
                    "filename": {"type": "string", "description": "新文件名，需带扩展名，例如 note.txt"},
                    "content": {"type": "string", "description": "新文件的初始内容，可为空"}
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
                    "path": {"type": "string", "description": "待编辑文件的绝对路径"},
                    "content": {"type": "string", "description": "要写入的新内容"},
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
                    "path": {"type": "string", "description": "待创建目录的绝对路径"}
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
                    "path": {"type": "string", "description": "待删除目录的绝对路径"}
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
                    "path": {"type": "string", "description": "待删除文件的绝对路径"}
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
                    "path": {"type": "string", "description": "原文件或目录的绝对路径"},
                    "new_name": {"type": "string", "description": "新名称，需带扩展名，例如 readme.md，不需要写路径"}
                },
                "required": ["path", "new_name"]
            }
        }
    }
]
