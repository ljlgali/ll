# chat2.py —— 作业（二）：在 chat1 基础上新增 isLeapYear 工具
# 基础：@Agent/Practice02/chat-stream-tool-getDate.py（即 chat1.py）
#   1. 新增一个 tool：isLeapYear，计算输入的年份是否是闰年
#   2. 计算的方式：编写 python 代码完成计算
# 相对 chat1.py 的改动：
#   ① tools 列表新增 isLeapYear 工具定义
#   ② system 提示词追加“用户询问某一年是否是闰年，调用isLeapYear，传入year参数。”
#   ③ 新增 is_leap_year 实现函数（纯 python 计算，返回闰年判断依据）
#   ④ 工具分发分支新增 elif name == "isLeapYear"
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
    }
]

messages = [
    {
        "role": "system",
        "content": "你是一个Agent。只要用户的问题涉及时间、日期、几点、几号、现在时刻等和实时时间相关的内容，都必须调用getDate工具获取本机最新时间，禁止使用记忆里的旧时间。用户询问某一年是否是闰年，调用isLeapYear，传入year参数。禁止编造结果，必须调用工具。用户只问几点就只输出时分秒，问日期输出年月日。输出闰年结果时，展示：调用工具名称、工具返回结果、闰年判断依据。工具返回的内容要如实转述给用户。"
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


def is_leap_year(year: int) -> str:
    """本地计算闰年，返回带依据的完整信息"""
    rule = "闰年判断依据：年份能被4整除且不能被100整除，或者能被400整除"
    if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
        result = f"✅ 调用工具：isLeapYear\n工具结果：{year} 是闰年\n{rule}"
    else:
        result = f"✅ 调用工具：isLeapYear\n工具结果：{year} 不是闰年\n{rule}"
    return result


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
                else:
                    result = f"错误：未知工具 {name}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": item["id"],
                    "content": result
                })

    except Exception as e:
        print("Error:", e)
