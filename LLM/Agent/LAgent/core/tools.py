# core/tools.py —— 工具声明层
# 只放"给模型看的"工具 JSON Schema 与 system 提示词，不含任何实现逻辑

SYSTEM_PROMPT = (
    "你是一个Agent。只要用户的问题涉及时间、日期、几点、几号、现在时刻等和实时时间相关的内容，"
    "都必须调用getDate工具获取本机最新时间，禁止使用记忆里的旧时间。"
    "用户询问某一年是否是闰年，调用isLeapYear，传入year参数。"
    "涉及本地文件操作时：获取当前目录用getCwd；列出目录内容用listFiles；查看文件类型用getFileType；"
    "读取文件内容用readFile；创建新文件用createFile；编辑文件内容用editFile；创建目录用createDir；"
    "删除目录用deleteDir；删除文件用deleteFile；重命名文件或目录用renamePath。"
    "用户需要联网搜索最新信息、新闻、资料时，调用searchWeb，传入query参数（搜索关键词或问题），"
    "转述搜索摘要并附上参考来源的标题和URL。"
    "用户需要查看某个网页的正文内容时，调用fetchWeb，传入url参数，如实转述返回的Markdown正文。"
    "用户需要执行本地命令行程序时，调用RunCli，传入command（程序名）和args（参数列表），"
    "如实报告stdout、stderr和退出码。"
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
    },
    {
        "type": "function",
        "function": {
            "name": "searchWeb",
            "description": "联网搜索工具：调用百度千帆智能搜索生成API，获取互联网上的最新信息。返回搜索摘要以及参考来源的标题和URL。当用户的问题涉及最新资讯、新闻、实时数据、你不确定的近期事实等需要联网查询的内容时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词或问题，例如：2026年国庆假期安排"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetchWeb",
            "description": "网页正文获取工具：通过本地curl下载指定网页的HTML源代码，再用trafilatura提取正文并转换为Markdown格式。返回Markdown正文及原始URL。当用户给出具体网页链接并希望阅读其内容时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "待获取的网页URL，需以 http:// 或 https:// 开头"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "RunCli",
            "description": "本地命令行执行工具：调用本机已安装的任意命令行程序（CLI）并返回标准输出、标准错误和退出码。当用户要求执行某个本地命令（如 ipconfig、ping、python 等）时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "程序名称，例如 ipconfig、ping、python"},
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "参数列表，例如 [\"--version\"]，可为空"
                    }
                },
                "required": ["command"]
            }
        }
    }
]
