# -*- coding: utf-8 -*-
"""生成《活着》读书心得 .docx（纯标准库，无第三方依赖）"""
import os, zipfile

BASE = r"E:\LLM\LLM\Agent\LAgent"
OUT = os.path.join(BASE, "活着_读书心得.docx")

TITLE = "读《活着》有感"
SUB = "——余华《活着》读书心得"

SECTIONS = [
    ("一、初读：一个老人的讲述", [
        "翻开《活着》的第一页，是一个叫福贵的老人坐在田埂上，对着一头也叫福贵的老牛说话。余华用这个画面开了场，看似随意，其实已经定下了整本书的调子：这不是一个要你去同情的故事，而是一个要你去听的故事。",
        "我原本以为会读到一个哭天抢地的苦难叙事，读下去才发现不是。福贵讲自己的一生，语气平得近乎淡漠，家产输光、被抓壮丁、亲人一个个离世，他都讲得不动声色。正是这种平，压得人喘不过气。余华后来在序言里说，人是为活着本身而活着的，而不是为活着之外的任何事物所活着。读到这句话时我停了很久。",
    ]),
    ("二、福贵的一生：把苦难写成家常", [
        "福贵的苦难密度高得惊人：父母、妻子家珍、儿子有庆、女儿凤霞、女婿二喜、外孙苦根，一个接一个地走了，最后只剩下他和一头牛。如果按一般的写法，这样的故事很容易滑向煽情，读者会被按着头哭。但余华偏偏不。",
        "有庆死的那一段，我印象最深。那么鲜活的一个孩子，为了给县长夫人献血，被抽血抽死了。福贵抱着儿子往家走，路上还在想怎么瞒着家珍。没有控诉，没有呐喊，只有一个人硬着头皮往前走的沉默。这种克制不是冷漠，而是那代人对苦难的日常化处理——日子还得过，饭还得吃，牛还得喂。",
        "我读到一半时意识到，这本书真正写的不是苦难的强度，而是人承受苦难时的姿态。福贵没有反抗命运，也没有被命运击垮，他只是活着，一天一天地活。这种姿态谈不上壮烈，甚至有点被动，可它有一种很难被摧毁的韧性。",
    ]),
    ("三、家珍：我读到的最有分量的一个人", [
        "在所有人物里，家珍让我最受触动。她是城里米行老板的女儿，嫁给福贵时是真心实意的，后来福贵赌光家产、被拉去当兵、家里穷得揭不开锅，她都没有走。她患了软骨病，站不起来还想着下地干活，怕给家里添负担。",
        "她临终前对福贵说，这辈子也知足了，下辈子还要一起过。这句话轻，但压得我难受。她的知足不是麻木，是在极窄的生存空间里，把能握住的都握住了。余华写女性很少用形容词，只写动作和话，反而让人记住了。",
    ]),
    ("四、它让我想到什么", [
        "读这本书时，我一直想到家里的老人。他们经历过比我艰难得多的年代，却很少主动讲那些事。偶尔提起，也是三言两语带过，语气和福贵一样平。以前我以为是不愿回忆，读完这本书我才想到另一种可能：有些经历,讲出来反而轻了，对他们而言，那些事早已成了生活本身的一部分，不需要被特别叙述。",
        "还有一层是艺术上的领悟。余华在序言里说，写作让他拥有了双重的身份，一个是现实中的自己,一个是写作中的自己。这本书让我第一次清楚地感受到，克制是比宣泄更难的技术。把最痛的地方轻轻带过，读者的心反而会自己补上那份重量。",
        "这本书也修正了我对\u201c坚强\u201d的理解。以前我总觉得坚强是迎难而上、是不服输。福贵不是，他更多是接受，然后继续。这种\u201c接受之后的继续\u201d，比对抗更消耗人，也更接近普通人真实的生存状态。",
    ]),
    ("五、一点保留", [
        "当然也有可以商榷的地方。全书苦难的密度确实过高，六个亲人接连离世，情节推进上有堆叠感，个别地方会让人怀疑作者是否有意把苦难推到极致以强化冲击。此外，福贵作为叙述者，他的自省力度有时显得不足，对自己年轻时的荒唐，忏悔的分量略轻。",
        "不过这些并不动摇它的分量。《活着》的价值不在于它讲了一个多惨的故事，而在于它让\u201c活着\u201d这个词从一个中性词，变成了一个有重量的词。",
    ]),
    ("六、结语", [
        "合上书时是傍晚，窗外有人在楼下喊孩子回家吃饭。我把书放回桌上，脑子里还是最后一页那个画面：福贵和老牛走在黄昏的田埂上，他喊一声\u201c福贵\u201d,牛就停下来，他再喊\u201c家珍\u201d\u201c有庆\u201d\u201c凤霞\u201d,牛还是走。",
        "余华没有给福贵任何补偿，也没有给读者任何安慰。他只是把一个人的一生摊开在那里，然后让你自己去看。看完之后，我没有觉得绝望，反而有一种很安静的踏实——日子再难，也还是一天一天地过。这大概就是这本书给我最实在的东西。",
    ]),
]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


paras = []
# 大标题
paras.append(
    '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:after="120"/></w:pPr>'
    '<w:r><w:rPr><w:b/><w:sz w:val="36"/></w:rPr>'
    '<w:t xml:space="preserve">' + esc(TITLE) + '</w:t></w:r></w:p>'
)
# 副标题
paras.append(
    '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:after="240"/></w:pPr>'
    '<w:r><w:rPr><w:sz w:val="24"/></w:rPr>'
    '<w:t xml:space="preserve">' + esc(SUB) + '</w:t></w:r></w:p>'
)

for head, body in SECTIONS:
    paras.append(
        '<w:p><w:pPr><w:pStyle w:val="Heading2"/><w:spacing w:before="240" w:after="120"/></w:pPr>'
        '<w:r><w:rPr><w:b/><w:sz w:val="28"/></w:rPr>'
        '<w:t xml:space="preserve">' + esc(head) + '</w:t></w:r></w:p>'
    )
    for p in body:
        paras.append(
            '<w:p><w:pPr><w:spacing w:line="360" w:lineRule="auto" w:after="100"/>'
            '<w:ind w:firstLine="480"/></w:pPr>'
            '<w:r><w:rPr><w:sz w:val="24"/></w:rPr>'
            '<w:t xml:space="preserve">' + esc(p) + '</w:t></w:r></w:p>'
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
    '<dc:title>' + esc(TITLE) + '</dc:title>'
    '<dc:subject>活着 读书心得</dc:subject></cp:coreProperties>'
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

# ---- 校验 ----
with zipfile.ZipFile(OUT, "r") as z:
    bad = z.testzip()
    doc_back = z.read("word/document.xml").decode("utf-8")
    parts = z.namelist()

import xml.dom.minidom as md
md.parseString(doc_back)

# ---- 字数统计 ----
import re
total_han = sum(len(re.findall(r"[\u4e00-\u9fff]", p)) for _, b in SECTIONS for p in b)
total_han += len(re.findall(r"[\u4e00-\u9fff]", TITLE + SUB))

print("生成成功:", OUT)
print("大小: %d 字节" % os.path.getsize(OUT))
print("部件数:", len(parts))
print("zip 完整性:", "OK" if bad is None else "损坏:" + str(bad))
print("XML 解析: OK")
print("段落数:", doc_back.count("<w:p>"))
print("汉字总数(含标题):", total_han)
