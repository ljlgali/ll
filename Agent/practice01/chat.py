import configparser

from openai import OpenAI

cfg = configparser.ConfigParser()
cfg.read("config.ini", encoding="utf-8")

client = OpenAI(
    base_url=cfg["llm"]["base_url"],
    api_key=cfg["llm"]["api_key"],
)

prompt = input("please input prompt :")
print("---")
try:
    resp = client.chat.completions.create(
        model=cfg["llm"]["model"],
        messages=[{"role": "user", "content": prompt}],
    )
    print(resp.choices[0].message.content)
except Exception as e:
    print(e)
