# Practice02 —— LLM Agent 工具调用练习

基于 Practice01 的 `chat-stream-loop-history.py`（流式打字机 + 无限循环 + 多轮对话历史）逐步迭代，
为模型挂载可被自动调用的本地工具（function call）：从获取时间，到文件操作。

## 文件说明

| 文件 | 对应作业 | 工具数 | 新增内容 |
|---|---|---|---|
| `chat1.py` | （一） | 1 | `getDate`：获取本机日期时间，**调用本地 date 命令**实现 |
| `chat2.py` | （二） | 2 | `isLeapYear`：判断闰年，**用 python 代码计算** |
| `chat3.py` | （三） | 12 | 本地文件操作 10 个：获取当前目录、列出目录内容、获取文件类型、读取文件内容、创建文件、编辑文件、创建目录、删除目录、删除文件、重命名文件和目录 |
| `chat1_architecture.mmd` | （四） | — | chat1 的 Mermaid 代码架构图 |
| `chat2_architecture.mmd` | （四） | — | chat2 的 Mermaid 代码架构图 |
| `chat3_architecture.mmd` | （四） | — | chat3 的 Mermaid 代码架构图 |
| `config.ini` | — | — | 模型配置，三个程序共用 |

三个版本是递进关系：`chat2.py` = `chat1.py` + isLeapYear，`chat3.py` = `chat2.py` + 文件操作工具。
每个文件开头都注明了"基于哪个文件开发"和"相对上一版改动了哪几处"。

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
python chat1.py     # 或 chat2.py / chat3.py
```

按提示输入问题即可，例如：

- `现在几点了`（chat1 起）
- `2026 年是闰年吗`（chat2 起）
- `列出 E:\LLM\LLM\Agent\practice02 目录下的所有文件`（chat3）

程序会在调用工具时打印 `[LOG] 调用工具 xxx`，便于观察工具链路。
按 `Ctrl+C` 退出（在 cmd 或 PyCharm 的 Terminal 中有效；PyCharm 的 Run 窗口会把 Ctrl+C 当作复制）。

## 说明

- `getDate` 按要求调用本地 `date /t & time /t` 命令取系统时间，不使用 Python 的 `datetime`。
- `isLeapYear` 按要求由 Python 代码本地计算：能被 4 整除且不能被 100 整除，或能被 400 整除。
- 读取/编辑文件仅支持纯文本格式（`.txt .md .py .json .csv` 等），二进制文件会返回不支持。
- 删除目录、删除文件、重命名属于高危操作，执行前请确认路径无误。
