"""直接测试 Agent.compact() 生成器能否完整 yield compact_done"""
import sys, time, json
sys.path.insert(0, "E:/LLM/LLM/Agent/LAgent")

from core.agent import Agent

print("=== 初始化 Agent ===")
agent = Agent()
print(f"✅ Agent 初始化完成，模型={agent.model}")
print(f"   当前 messages: {len(agent.messages)} 条")
print(f"   当前 tokens: {agent.current_tokens}")

# 先塞几轮对话，让上下文够压缩
print("\n=== 先进行 3 轮对话 ===")
for i in range(3):
    # 构造几条假消息直接塞进去
    agent.messages.append({"role": "user", "content": f"问题{i+1}：请介绍一下计算机科学的基本概念，包括算法、数据结构、编程语言等。"})
    agent.messages.append({"role": "assistant", "content": f"好的，计算机科学是研究计算和信息处理的学科。第{i+1}轮回答包括：1)算法是解决问题的步骤；2)数据结构是组织数据的方式；3)编程语言是人和计算机交流的工具..." + "更多内容" * 20})

print(f"   塞完后 messages: {len(agent.messages)} 条")
print(f"   塞完后 tokens: {agent.current_tokens}")

# 开始压缩
print("\n=== 执行 compact() 生成器 ===")
t0 = time.time()
event_count = 0
got_compact_done = False

for ev in agent.compact():
    event_count += 1
    kind = ev["type"]
    elapsed = time.time() - t0
    
    if kind == "compact_start":
        print(f"[{elapsed:.1f}s] ✅ compact_start")
    elif kind == "archive_saved":
        print(f"[{elapsed:.1f}s] ✅ archive_saved → {ev['archive_id']}")
    elif kind == "token":
        # token 太多了，只打印第一次和最后一次
        if event_count == 3 or True:  # 简化：每 50 个 token 打印一次
            pass
    elif kind == "archive_replaced":
        print(f"[{elapsed:.1f}s] ✅ archive_replaced → {ev['archive_id']}")
    elif kind == "compact_done":
        print(f"[{elapsed:.1f}s] 🎉🎉🎉 compact_done !!!")
        print(f"   before: {len(ev['before_messages'])}条 / {ev['before_tokens']}t")
        print(f"   after:  {len(ev['after_messages'])}条 / {ev['after_tokens']}t")
        print(f"   archive_id: {ev['archive_id']}")
        got_compact_done = True
    elif kind == "compact_error":
        print(f"[{elapsed:.1f}s] ❌ compact_error: {ev['message']}")
    elif kind == "token":
        # 跳过 token 刷屏
        pass

total = time.time() - t0
print(f"\n=== 结束 ===")
print(f"总事件数: {event_count}")
print(f"总耗时: {total:.1f}s")
print(f"compact_done 到达: {'✅ YES' if got_compact_done else '❌ NO'}")

if not got_compact_done:
    print("\n⚠️ compact_done 没到达！检查上面的错误信息")
else:
    print("\n🎉 compact() 完整走通！问题在 TUI 层")
