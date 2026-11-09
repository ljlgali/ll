# core/tools.py —— 工具声明层
# 只放"给模型看的"工具 JSON Schema 与 system 提示词，不含任何实现逻辑

def build_system_prompt(skills: list | None = None, mcp=None) -> str:
    """根据已发现的 Skill 与已连接的 MCP Server 动态拼装 system prompt。
    skills 为空时省略"可用技能"段落；mcp 没有可用工具时省略 MCP 段落。
    同时注入 recallContext 工具的说明，让模型知道如何检索被压缩的历史。
    """
    base = (
        "你是一名通用 AI 助手，名叫「xAgent」。你可以帮用户回答问题、编写代码、操作文件、执行命令、联网搜索，"
        "回答要准确、务实、可操作，必要时追问关键信息。\n\n"
        "**回答原则：**\n"
        "- 优先给出可直接执行的建议，用具体步骤或数字说话\n"
        "- 用户需求不明确时，主动追问关键信息\n"
        "- 严禁编造数据或结论，所有专业判断必须有依据（工具返回、已加载 Skill、联网搜索结果）\n\n"
        "**时间与日期工具：**\n"
        "只要用户的问题涉及时间、日期、几点、几号、现在时刻等，"
        "都必须调用 getDate 工具获取本机最新时间，禁止使用记忆里的旧时间。"
        "用户询问某一年是否是闰年，调用 isLeapYear，传入 year 参数。\n\n"
        "**文件操作：**\n"
        "获取当前目录用 getCwd；列出目录内容用 listFiles；查看文件类型用 getFileType；"
        "读取文件内容用 readFile；创建新文件用 createFile；编辑文件内容用 editFile；创建目录用 createDir；"
        "删除目录用 deleteDir；删除文件用 deleteFile；重命名文件或目录用 renamePath。\n\n"
        "**联网检索：**\n"
        "需要查询最新信息（新闻、政策、天气、技术文档、产品信息等）时，"
        "调用 searchWeb，传入 query 参数，转述摘要并附上参考来源标题和 URL。"
        "需要读取某个网页的正文时，调用 fetchWeb，传入 url 参数。\n\n"
        "**命令执行：**\n"
        "需要在本地执行计算、脚本或命令行程序时，调用 RunCli，传入 command 和 args。\n\n"
        "**严禁编造数据或结论**，所有专业判断必须有依据（工具返回、已加载 Skill、联网搜索结果）。"
        "\n\n"
        "**上下文压缩与历史检索：**\n"
        "当你发现历史对话被压缩，或需要查找被压缩前的历史细节时，调用 recallContext 工具。"
        "它接收 text（必需，关键词）和 id（可选，归档编号）两个参数，"
        "返回包含关键词的原始消息片段及其所在归档编号和位置。"
        "归档编号可从压缩摘要末尾的归档说明中获得。"
    )
    if skills:
        skill_lines = ["\n\n"
                       "你可以调用以下技能（Skill），每个 Skill 是一份可复用的专业指令包："]
        for s in skills:
            skill_lines.append(f"- `{s['name']}`: {s['description']}")
        skill_lines.append(
            "\n当用户的问题与某个技能相关，或你需要额外的专业指令时，"
            "调用 loadSkill 工具传入 name 参数加载完整技能内容。"
            "如需读取技能目录下的附件文件（如数据表、模板），再传入 filename 参数。"
            "Skill 的完整内容只有在调用 loadSkill 时才会进入对话上下文，"
            "请先加载再根据内容行动。"
        )
        base += "".join(skill_lines)
    if mcp is not None:
        # 已连接的 MCP Server 工具说明（由 MCPManager 生成，无工具时返回空串）
        base += mcp.prompt_block()
    return base


# 保留旧常量作为后备（不发现 skills 时使用）
SYSTEM_PROMPT = build_system_prompt()

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "getDate",
            "description": "获取本机当前的日期和时间。只要用户的问题涉及时间、日期、几点、几号、多久之后、现在时刻、倒计时、节气、农时、播种期、收获期等一切和实时时间相关的内容，你都必须调用这个工具获取最新时间，禁止使用记忆里的旧时间。",
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
            "description": "获取当前工作目录的绝对路径。用户问'当前目录/工作目录/在哪个目录'时调用。",
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
                    "path": {"type": "string", "description": "目标目录的绝对路径"}
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
                    "path": {"type": "string", "description": "文件的绝对路径"}
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
                    "filename": {"type": "string", "description": "新文件名，需带扩展名，例如 report.csv"},
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
                    "new_name": {"type": "string", "description": "新名称，需带扩展名，例如 春耕计划2026.md，不需要写路径"}
                },
                "required": ["path", "new_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "searchWeb",
            "description": "联网搜索工具：获取互联网上的最新信息。当用户需要查询新闻、政策、天气、技术文档、产品信息等需要联网的内容时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词或问题，例如：2026年小麦赤霉病发生趋势预报"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetchWeb",
            "description": "网页正文获取工具：通过本地curl下载指定网页的HTML源代码，再用trafilatura提取正文并转换为Markdown格式。当用户给出具体网页链接并希望阅读其内容时调用。",
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
            "description": "本地命令行执行工具：调用本机已安装的任意命令行程序（CLI）并返回标准输出、标准错误和退出码。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "程序名称"},
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "参数列表，可为空"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "loadSkill",
            "description": "动态加载 Skill（技能）的完整内容。Skill 是放在 .agents/skills/ 目录下的可复用专业指令包，每个 Skill 子目录至少有一个 SKILL.md（YAML Frontmatter 声明 name 和 description）。调用 loadSkill 后，Skill 的正文才会进入对话上下文，避免一次性塞入所有 Skill 造成 token 浪费。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "必需，Skill 的名称（YAML Frontmatter 里的 name 字段，或 Skill 目录名）"},
                    "filename": {"type": "string", "description": "可选，需要加载的附件文件名。不填时加载 SKILL.md 全文；填写时加载 Skill 目录内的该文件"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "createSkill",
            "description": "在 .agents/skills/ 下新建一个 Skill（落盘为目录 + SKILL.md，含 YAML frontmatter）。当用户希望把一套可复用的专业指令、流程、领域知识沉淀成以后能反复调用的技能时使用。会校验命名合法性、拒绝覆盖已有 Skill。新 Skill 创建后需 /new 或重启才会被自动发现。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "必需，Skill 名：2-40 字符，只能含小写字母、数字、连字符、下划线，首尾为字母或数字，例如 wheat-disease"},
                    "description": {"type": "string", "description": "必需，一句话说明这个 Skill 是干什么的、什么时候触发，会注入 System Prompt 让模型判断是否加载，建议 ≤200 字"},
                    "body": {"type": "string", "description": "必需，Skill 正文 Markdown：执行步骤、规则、参考资料、示例。≤20000 字"}
                },
                "required": ["name", "description", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recallContext",
            "description": "在历史压缩归档中检索包含指定关键词的原始消息片段。当你发现上下文被压缩、需要查找被压缩前的历史细节时调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "必需，要查找的关键词或短语"},
                    "id": {"type": "string", "description": "可选，归档编号（形如 20261022-153000），不填则检索全部"}
                },
                "required": ["text"]
            }
        }
    }
]
