# LAgent

基于 `core / UI` 分层架构的本地文件操作 Agent，当前前端为 Textual 终端界面，可扩展 Web / Desktop / Mobile。

## 目录结构

```
LAgent/
├── main.py              程序入口：python main.py 启动 TUI
├── config.ini           模型配置（必须与 main.py 同目录）
├── core/                业务核心层（不含任何界面代码）
│   ├── config.py        读取 config.ini，创建 OpenAI 客户端
│   ├── tools.py         12 个工具的 JSON Schema + system 提示词
│   ├── functions.py     工具实现：12 个本地函数 + dispatch 统一分发
│   └── agent.py         Agent 类：维护多轮历史、流式请求、工具调用循环
└── tui/                 终端界面层（不含任何业务逻辑）
    └── app.py           Textual 界面：对话区 + 输入框
```

## 环境准备

```
pip install openai textual
```

`config.ini` 三个字段：

```ini
[llm]
base_url = https://api.deepseek.com
api_key = sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
model = deepseek-chat
```

## 运行

```
cd /d E:\LLM\LLM\Agent\LAgent
D:\东软软件\课堂python\.venv\Scripts\python.exe main.py
```

**注意**：`main.py` 会按自身所在目录定位 `config.ini`，所以两个文件必须放在同一目录。

## 已实现的 12 个工具

| 工具名 | 功能 | 实现方式 |
|---|---|---|
| getDate | 获取本机日期时间 | subprocess 调本地 `date /t & time /t` |
| isLeapYear | 判断年份是否闰年 | Python 计算 |
| getCwd | 获取当前工作目录 | `os.getcwd()` |
| listFiles | 列出目录下所有文件和子目录 | `os.listdir()` |
| getFileType | 获取文件类型、MIME、是否纯文本 | `mimetypes` |
| readFile | 读取纯文本文件内容 | `open()` + 扩展名白名单 |
| createFile | 创建新文件 | `open(..., "x")` |
| editFile | 编辑文件（overwrite/append） | `open(..., "w" / "a")` |
| createDir | 创建目录 | `os.makedirs()` |
| deleteDir | 删除目录（非空） | `shutil.rmtree()` |
| deleteFile | 删除文件 | `os.remove()` |
| renamePath | 重命名文件或目录 | `os.rename()` |

## 扩展其他前端

`core.Agent.chat_stream()` 返回一个生成器，每 yield 一个事件字典：

```python
for ev in agent.chat_stream("现在几点了"):
    # ev["type"] == "token"  → ev["content"] 流式文本
    # ev["type"] == "tool"   → ev["name"] / ev["args"] / ev["result"] / ev["elapsed_ms"]
    # ev["type"] == "done"   → 对话结束
    # ev["type"] == "error"  → ev["message"] 异常信息
```

新增 `web/`、`desktop/`、`mobile/` 前端时，只需 `from core import Agent`，消费这个事件流即可，core 层无需任何改动。
