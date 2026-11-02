# -*- coding: utf-8 -*-
"""用标准库 zipfile 手写最小可用 .docx（OOXML），无需 python-docx"""
import os
import zipfile

BASE = r"E:\LLM\LLM\Agent\LAgent"
SRC = os.path.join(BASE, "读书心得.txt")
OUT = os.path.join(BASE, "读书心得.docx")

with open(SRC, "r", encoding="utf-8") as f:
    lines = [ln.rstrip("\n") for ln in f.readlines()]

# ---------- 组装 word/document.xml 正文 ----------
def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

# 判断是否标题行：首个非空行 = 大标题；以“——”“一、..五、”“结语”开头 = 小标题
paras = []
first_text_done = False
heads_small = ("一、", "二、", "三、", "四、", "五、", "结语")

for ln in lines:
    t = ln.strip()
    if not t:
        # 空行 -> 小间距空段落
        paras.append('<w:p><w:pPr><w:spacing w:after="0"/></w:pPr></w:p>')
        continue
    if not first_text_done:
        style = '<w:pStyle w:val="Heading1"/><w:jc w:val="center"/>'
        run_pr = '<w:rPr><w:b/><w:sz w:val="36"/></w:rPr>'
        first_text_done = True
    elif t.startswith("——"):
        style = '<w:jc w:val="center"/>'
        run_pr = '<w:rPr><w:sz w:val="24"/></w:rPr>'
    elif t.startswith(heads_small):
        style = '<w:pStyle w:val="Heading2"/>'
        run_pr = '<w:rPr><w:b/><w:sz w:val="28"/></w:rPr>'
    else:
        style = '<w:spacing w:line="360" w:lineRule="auto" w:after="80"/><w:ind w:firstLine="480"/>'
        run_pr = '<w:rPr><w:sz w:val="24"/></w:rPr>'
    paras.append(
        '<w:p><w:pPr>' + style + '</w:pPr>'
        '<w:r>' + run_pr + '<w:t xml:space="preserve">' + esc(t) + '</w:t></w:r></w:p>'
    )

document_xml = (
'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
'<w:body>' + "".join(paras) +
'<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
'<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
'w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
'</w:body></w:document>'
)

content_types = (
'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
'<Default Extension="xml" ContentType="application/xml"/>'
'<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
'<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
'<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
'<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
'</Types>'
)

rels = (
'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
'<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
'</Relationships>'
)

doc_rels = (
'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
'</Relationships>'
)

styles = (
'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
'<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
'<w:docDefaults><w:rPrDefault><w:rPr>'
'<w:rFonts w:ascii="Times New Roman" w:eastAsia="宋体" w:hAnsi="Times New Roman"/>'
'<w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:rPrDefault>'
'<w:pPrDefault><w:pPr><w:spacing w:line="360" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
'</w:docDefaults>'
'<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
'<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
'<w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr>'
'<w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>'
'<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
'<w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="1"/></w:pPr>'
'<w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>'
'</w:styles>'
)

core = (
'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
'xmlns:dc="http://purl.org/dc/elements/1.1/">'
'<dc:title>读书心得</dc:title></cp:coreProperties>'
)

app = (
'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
'<Application>Python zipfile</Application></Properties>'
)

if os.path.exists(OUT):
    os.remove(OUT)

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", content_types)
    z.writestr("_rels/.rels", rels)
    z.writestr("word/document.xml", document_xml)
    z.writestr("word/_rels/document.xml.rels", doc_rels)
    z.writestr("word/styles.xml", styles)
    z.writestr("docProps/core.xml", core)
    z.writestr("docProps/app.xml", app)

# 校验：重新打开 zip，检查关键部件是否存在且可解析
with zipfile.ZipFile(OUT, "r") as z:
    names = z.namelist()
    bad = z.testzip()
    doc_back = z.read("word/document.xml").decode("utf-8")

import xml.dom.minidom as md
md.parseString(doc_back)  # 抛异常即 XML 不合法

print("生成成功:", OUT)
print("大小: %d 字节" % os.path.getsize(OUT))
print("部件:", names)
print("zip 完整性:", "OK" if bad is None else "损坏 " + str(bad))
print("document.xml 长度:", len(doc_back), "字符")
print("XML 解析: OK")
print("段落数:", doc_back.count("<w:p>"))
