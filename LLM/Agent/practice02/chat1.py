# chat1.py —— 作业（一）：新增 getDate 工具
# 基础：Practice01/chat-stream-loop-history.py（流式打字机 + 无限循环 + 多轮对话历史）
#   1. 新增一个 tool：getDate，获取当前电脑的日期和时间
#   2. 获取日期时间的方式：调用本地 date 命令（subprocess），而不是编写 python 代码
import time
import configparser
import json
import subprocess
from openai import OpenAI

DELAY = 0.02

cfg = configparser.ConfigParser()
cfg.read("config.ini", encoding="utf-8")
client = OpenAI(
    base_url=cfg["llm"]["base_url"],
    api_key=cfg["llm"]["api_key"],
)

# ========== 一个工具：getDate ==========
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
    }
]

messages = [
    {
        "role": "system",
        "content": "你是一个Agent。只要用户的问题涉及时间、日期、几点、几号、现在时刻等和实时时间相关的内容，都必须调用getDate工具获取本机最新时间，禁止使用记忆里的旧时间。禁止编造结果，必须调用工具。用户只问几点就只输出时分秒，问日期输出年月日。工具返回的内容要如实转述给用户。"
    }
]


def get_current_time() -> str:
    """调用本地 date 命令获取当前日期和时间（不使用 Python datetime）"""
    try:
        r = subprocess.run("date /t & time /t", shell=True, capture_output=True, text=True)
        out = (r.stdout or "").strip()
        return out if out else f"未能获取本机时间（返回码 {r.returncode}）"
    except Exception as e:
        return f"调用本地 date 命令失败：{e}"


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
                else:
                    result = f"错误：未知工具 {name}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": item["id"],
                    "content": result
                })

    except Exception as e:
        print("Error:", e)
