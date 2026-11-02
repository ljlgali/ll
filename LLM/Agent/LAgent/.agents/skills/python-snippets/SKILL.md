---
name: python-snippets
description: Python 常用代码片段库。用户问 Python 怎么写、求代码示例时触发。
---

# Python 常用代码片段库

本 Skill 收录了 Python 开发中常见任务的标准写法。当用户问"Python 怎么 XXX"、
"求一段代码实现 XXX" 时，先调用 loadSkill 加载相关附件再回答。

## 可用附件文件

- `common-patterns.py`：10+ 个高频代码片段（文件读写、CSV 处理、HTTP 请求等）
- `regex-cheatsheet.txt`：正则表达式速查表

## 行动指引

1. 遇到 Python 相关编码问题时，先调用 loadSkill(name="python-snippets", filename="common-patterns.py")
2. 如果问题涉及字符串匹配或提取，再加载 regex-cheatsheet.txt
3. 回答时：先给出代码 → 简要解释关键行 → 提醒可能的坑（如路径编码、异常处理）
4. **禁止编造 Python 语法**，不确定就先查附件或承认"这部分我不太确定"
