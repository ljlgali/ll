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

while True:
    prompt = input("please input prompt :")
    print("---")
    try:
        stream = client.chat.completions.create(
            model=cfg["llm"]["model"],
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content is None:
                continue
            for char in content:
                print(char, end="", flush=True)
                time.sleep(DELAY)
        print()
    except Exception as e:
        print(e)
