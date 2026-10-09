import time
import configparser

from openai import OpenAI

DELAY = 0.02

cfg = configparser.ConfigParser()
cfg.read("config.ini", encoding="utf-8")

client = OpenAI(
    base_url=cfg["llm"]["base_url"],
    api_key=cfg["llm"]["api_key"],
)

messages = []
while True:
    prompt = input("please input prompt :")
    print("---")
    messages.append({"role": "user", "content": prompt})
    try:
        stream = client.chat.completions.create(
            model=cfg["llm"]["model"],
            messages=messages,
            stream=True,
        )
        reply = ""
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content is None:
                continue
            reply += content
            for char in content:
                print(char, end="", flush=True)
                time.sleep(DELAY)
        print()
        messages.append({"role": "assistant", "content": reply})
    except Exception as e:
        print(e)
