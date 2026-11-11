# Practice02 —— LLM Agent 工具调用练习

基于 Practice01 的 `chat-stream-loop-history.py`（流式打字机 + 无限循环 + 多轮对话历史）逐步迭代，
为模型挂载可被自动调用的本地工具（function call）：从获取时间，到文件操作。

## 文件说明

| 文件 | 作用 | 说明 |
|---|---|---|
| `chat.py` | 唯一的可运行程序，12 个内置工具 | 把作业（一）~（三）的三个阶段合并到一处：`getDate` → `isLeapYear` → 10 个文件操作工具，避免三份高度重复的代码 |
| `chat_architecture.mmd` | Mermaid 源码，描述 `chat.py` 的调用链 | 工具注册 → 模型返回 tool_calls → 本地分发 → 结果回填 → 继续循环 |
| `config.ini` | 模型配置 | 与 `chat.py` 同目录，被 `.gitignore` 忽略，不入库 |

`chat.py` 的 12 个工具：

| 类别 | 工具 |
|---|---|
| 时间 | `getDate`（调用本机 `date /t & time /t` 取系统时间）、`isLeapYear`（Python 计算闰年） |
| 目录 | `getCwd`、`listFiles`、`createDir`、`deleteDir` |
| 文件 | `getFileType`、`readFile`、`createFile`、`editFile`、`deleteFile`、`renamePath` |

> 历史说明：早期版本按作业拆成 `chat1.py` / `chat2.py` / `chat3.py` 三个递进文件，
> 后因三份代码工具定义与主循环高度重复，合并为单个 `chat.py`（12 个工具一次到位），
> 三个阶段的差异写在本节与 `chat.py` 开头注释里。

## 环境准备

1. Python 3.8+，安装依赖库：

   ```bash
   pip install openai
   ```

2. 在 `config.ini` 中填写自己的模型配置（缺一不可，未填写会报编码错误）：

   ```ini
   [llm]
   base_url = https://api.deepseek.com
   api_key = sk-xxxxxxxx
   model = deepseek-chat
   ```

## 运行方式

`config.ini` 必须与程序文件放在同一个目录下（程序按相对路径读取），然后：

```bash
python chat.py
```

按提示输入问题即可，例如：

- `现在几点了`
- `2026 年是闰年吗`
- `列出 E:\LLM\LLM\Agent\practice02 目录下的所有文件`

程序会在调用工具时打印 `[LOG] 调用工具 xxx`，便于观察工具链路。
按 `Ctrl+C` 退出（在 cmd 或 PyCharm 的 Terminal 中有效；PyCharm 的 Run 窗口会把 Ctrl+C 当作复制）。

## 说明

- `getDate` 按要求调用本地 `date /t & time /t` 命令取系统时间，不使用 Python 的 `datetime`。
- `isLeapYear` 按要求由 Python 代码本地计算：能被 4 整除且不能被 100 整除，或能被 400 整除。
- 读取/编辑文件仅支持纯文本格式（`.txt .md .py .json .csv` 等），二进制文件会返回不支持。
- 删除目录、删除文件、重命名属于高危操作，执行前请确认路径无误（本练习未加路径边界，仅作教学示例）。
