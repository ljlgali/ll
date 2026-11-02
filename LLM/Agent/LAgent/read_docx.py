# -*- coding: utf-8 -*-
"""读取 docx 正文（纯标准库）"""
import zipfile, re, sys

p = r"E:\LLM\LLM\Agent\LAgent\读书心得.docx"
with zipfile.ZipFile(p, "r") as z:
    print("=== 部件清单 ===")
    for n in z.namelist():
        print(" -", n, z.getinfo(n).file_size, "字节")
    xml = z.read("word/document.xml").decode("utf-8")

print("\n=== 正文 ===")
# 按段落切分，提取每段的 w:t 文本
paras = re.findall(r"<w:p[ >].*?</w:p>|<w:p/>", xml, re.S)
out = []
for para in paras:
    texts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", para, re.S)
    line = "".join(texts)
    line = (line.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))
    out.append(line)

for i, line in enumerate(out, 1):
    print("[%02d] %s" % (i, line if line.strip() else "(空行)"))

body = "\n".join(out).strip()
print("\n=== 统计 ===")
print("段落总数:", len(out))
print("非空段落:", sum(1 for l in out if l.strip()))
print("正文字符数(含标点):", len(body.replace("\n", "")))
print("中文汉字数:", len(re.findall(r"[\u4e00-\u9fff]", body)))
