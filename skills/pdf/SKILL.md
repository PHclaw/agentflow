---
{
  "id": "pdf",
  "name": "PDF处理助手",
  "description": "上传 PDF 后直接说需求，平台会生成可下载文件。\n\n【我会做】\n· 合并多个 PDF / 按页拆分\n· 抽取正文（扫描件可能无字）\n· 提取表格为 Excel；提取图片与内嵌文件\n· 文字水印；表单结构探测（JSON）\n· 解析为 Markdown（也支持 Word / Excel / PPT）\n· PDF 转 Word：说「word / 转成 word」默认 .docx；只有明确说「转成 doc」才尝试旧版 .doc\n\n【怎么开始】先上传文件再发指令。问「你会干什么 / 能不能转 word」会介绍能力，不会因为没上传就假装失败模板。\n【示例】把这份 PDF 转成 Word；转化为 docx；转化为doc文件；提取表格给我 Excel；把图片都提取出来；加水印：内部资料",
  "specialty": "PDF处理",
  "routerBlurb": "面向文档日常处理：合并/拆分/抽文本/提取表格（Excel）/表单探测/加水印；也可解析为 Markdown 并提取图像。",
  "triggers": [
    "pdf",
    "PDF",
    "合并PDF",
    "拆分PDF",
    "提取PDF",
    "提取表格",
    "提取图片",
    "填表",
    "表单结构",
    "表单探测",
    "markdown",
    "文档解析",
    "转docx",
    "转word",
    "转doc",
    "pdfplumber"
  ],
  "tags": [
    "文档",
    "PDF",
    "办公"
  ],
  "version": "v1.5.0",
  "model": "chatzoc_9b_B",
  "params": {
    "temperature": 0.2,
    "maxTokens": 4096
  },
  "authorId": "platform-preset",
  "authorName": "平台预置",
  "visibility": "public",
  "status": "published",
  "changelog": "PDF 转 Word（word→docx；明确 doc 才尝试 .doc）；能力介绍走完整能力卡片",
  "systemPrompt": "你是 PDF/文档处理专家。平台会在「上传文件摘要」中给出用户刚上传的文件（含 serverPath），并在「脚本结果」中给出服务端工具执行结果（合并/拆分/抽文本/提取表格/表单结构探测/加水印/文档解析 Markdown/提取图像/PDF转Word）。\n\n硬性规则：\n0) 若 intent=intro，或用户问「你会干什么/怎么用/能不能转 word/可以把 pdf 转 docx 吗」且未执行转换：按脚本 stdout 完整能力卡片介绍（能力清单每条、怎么开始、全部示例、做不到/注意）。禁止只说一句；禁止套用结果/下载模板；禁止声称已处理文件。没有文件也可以介绍。\n1) 若「上传文件摘要」不是「（无上传文件）」：必须承认这些文件已上传，禁止说「未检测到上传」「请提供本地路径」。\n2) 若脚本结果 exitCode=0 且含 downloadUrl：必须把该链接原样告诉用户（可用 Markdown 链接），说明已完成处理。\n3) 若 intent=extract_tables：必须给出唯一的 Excel（.xlsx）下载，不要提 CSV，不要再列其它表格文件；正文预览必须复制脚本 markdownPreview 的 GFM 表格（前后空一行，不要放进列表/加粗行内），单元格文字保持原样。\n4) 若 intent=form_probe：总结 fillable/视觉结构要点，并给出 JSON 下载链接。\n5) 若 intent=watermark：水印文字必须以脚本 watermarkText 为准（不要写 CONFIDENTIAL，除非脚本就是这个值），并给出带水印 PDF 下载链接。\n6) 若 intent=parse 或 extract_images：给出 Markdown 下载链接；若有 downloadUrls/imageCount，逐条给出图像链接。\n6b) 若 intent=to_docx 或 to_doc 且 exitCode=0：给出 Word 下载链接。用户说 word 即 .docx。禁止声称 torchv-document-api 不能转 Word——平台已用 pdf_word 生成。若 note 写明无法生成 .doc，说明已提供 docx 及原因。\n7) 若 exitCode!=0：根据 note/stderr 说明缺什么（例如请先上传 PDF），并顺带用一两句点明本助手确实支持该功能，再给补救步骤。\n8) 默认简体中文；结论先行；代码块仅作补充说明，优先报告平台已生成的结果。\n9) 禁止用 $...$ 包公式；不要寒暄。\n10) 若 intent=merge：合并顺序必须以脚本 mergeOrder/sources 为准，禁止按用户原话或上传列表自行重排后描述。\n\n输出结构：\n## 结果\n## 下载 / 产出（如有）\n## 说明",
  "userPrompt": "请根据用户需求与平台工具结果回复。\n\n## 用户需求\n{{input}}\n\n## 上传文件摘要\n{{file_summary}}\n\n## 脚本结果\n{{tool_result}}",
  "variables": [
    {
      "name": "input",
      "type": "string"
    },
    {
      "name": "file_summary",
      "type": "string"
    },
    {
      "name": "tool_result",
      "type": "string"
    }
  ],
  "examples": [
    {
      "title": "抽取PDF文本与表格",
      "note": "验收：给出 pdfplumber 代码，说明表格导出路径",
      "expectHighlights": [
        "pdfplumber",
        "extract_text",
        "extract_tables"
      ],
      "variables": {
        "input": "任务：从 report.pdf 抽取全部文本，并把第一页表格导出为 CSV。请给可运行代码。"
      }
    },
    {
      "title": "合并多个PDF",
      "note": "验收：pypdf PdfWriter 合并示例",
      "expectHighlights": [
        "PdfWriter",
        "merge",
        "add_page"
      ],
      "variables": {
        "input": "把 a.pdf、b.pdf、c.pdf 按顺序合并为 merged.pdf。"
      }
    },
    {
      "title": "填写可填表单",
      "note": "验收：提到 forms.md 与 fill_fillable_fields 脚本思路",
      "expectHighlights": [
        "forms",
        "fill",
        "字段"
      ],
      "variables": {
        "input": "有一个带可填字段的申请表 application.pdf，需要把姓名、日期字段填上。请说明步骤与可用脚本。"
      }
    }
  ],
  "workflow": {
    "agentId": "pdf",
    "version": "1.0.0",
    "kind": "pdf",
    "presetSource": "pdf/ (Anthropic-style PDF skill)",
    "steps": [
      {
        "name": "变量注入",
        "action": "injectVariables"
      },
      {
        "name": "PDF工具",
        "action": "runPdfTool"
      },
      {
        "name": "模型解读",
        "action": "callModel",
        "model": "chatzoc_9b_B"
      },
      {
        "name": "结果返回",
        "action": "formatOutput"
      }
    ]
  },
  "totalCalls": 35,
  "avgRating": 0.0,
  "publishedAt": "2026-08-12T09:06:39",
  "createdAt": "2026-08-12T09:06:39",
  "updatedAt": "2026-08-21T01:39:52",
  "source": "pdf/ (Anthropic-style PDF skill)",
  "workflowKind": "pdf"
}
---

# PDF 处理助手

改编自 Anthropic 风格 PDF Skill。同目录资源：
- 
eference.md：进阶参考
- orms.md：表单填写流程
- scripts/：表单与转图辅助脚本
- LICENSE.txt

# PDF Processing Guide

## Overview

This guide covers essential PDF processing operations using Python libraries and command-line tools. For advanced features, JavaScript libraries, and detailed examples, see REFERENCE.md. If you need to fill out a PDF form, read FORMS.md and follow its instructions.

## Quick Start

```python
from pypdf import PdfReader, PdfWriter

# Read a PDF
reader = PdfReader("document.pdf")
print(f"Pages: {len(reader.pages)}")

# Extract text
text = ""
for page in reader.pages:
    text += page.extract_text()
```

## Python Libraries

### pypdf - Basic Operations

#### Merge PDFs
```python
from pypdf import PdfWriter, PdfReader

writer = PdfWriter()
for pdf_file in ["doc1.pdf", "doc2.pdf", "doc3.pdf"]:
    reader = PdfReader(pdf_file)
    for page in reader.pages:
        writer.add_page(page)

with open("merged.pdf", "wb") as output:
    writer.write(output)
```

#### Split PDF
```python
reader = PdfReader("input.pdf")
for i, page in enumerate(reader.pages):
    writer = PdfWriter()
    writer.add_page(page)
    with open(f"page_{i+1}.pdf", "wb") as output:
        writer.write(output)
```

#### Extract Metadata
```python
reader = PdfReader("document.pdf")
meta = reader.metadata
print(f"Title: {meta.title}")
print(f"Author: {meta.author}")
print(f"Subject: {meta.subject}")
print(f"Creator: {meta.creator}")
```

#### Rotate Pages
```python
reader = PdfReader("input.pdf")
writer = PdfWriter()

page = reader.pages[0]
page.rotate(90)  # Rotate 90 degrees clockwise
writer.add_page(page)

with open("rotated.pdf", "wb") as output:
    writer.write(output)
```

### pdfplumber - Text and Table Extraction

#### Extract Text with Layout
```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        print(text)
```

#### Extract Tables
```python
with pdfplumber.open("document.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        for j, table in enumerate(tables):
            print(f"Table {j+1} on page {i+1}:")
            for row in table:
                print(row)
```

#### Advanced Table Extraction
```python
import pandas as pd

with pdfplumber.open("document.pdf") as pdf:
    all_tables = []
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            if table:  # Check if table is not empty
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)

# Combine all tables
if all_tables:
    combined_df = pd.concat(all_tables, ignore_index=True)
    combined_df.to_excel("extracted_tables.xlsx", index=False)
```

### reportlab - Create PDFs

#### Basic PDF Creation
```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("hello.pdf", pagesize=letter)
width, height = letter

# Add text
c.drawString(100, height - 100, "Hello World!")
c.drawString(100, height - 120, "This is a PDF created with reportlab")

# Add a line
c.line(100, height - 140, 400, height - 140)

# Save
c.save()
```

#### Create PDF with Multiple Pages
```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet

doc = SimpleDocTemplate("report.pdf", pagesize=letter)
styles = getSampleStyleSheet()
story = []

# Add content
title = Paragraph("Report Title", styles['Title'])
story.append(title)
story.append(Spacer(1, 12))

body = Paragraph("This is the body of the report. " * 20, styles['Normal'])
story.append(body)
story.append(PageBreak())

# Page 2
story.append(Paragraph("Page 2", styles['Heading1']))
story.append(Paragraph("Content for page 2", styles['Normal']))

# Build PDF
doc.build(story)
```

#### Subscripts and Superscripts

**IMPORTANT**: Never use Unicode subscript/superscript characters (₀₁₂₃₄₅₆₇₈₉, ⁰¹²³⁴⁵⁶⁷⁸⁹) in ReportLab PDFs. The built-in fonts do not include these glyphs, causing them to render as solid black boxes.

Instead, use ReportLab's XML markup tags in Paragraph objects:
```python
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet

styles = getSampleStyleSheet()

# Subscripts: use <sub> tag
chemical = Paragraph("H<sub>2</sub>O", styles['Normal'])

# Superscripts: use <super> tag
squared = Paragraph("x<super>2</super> + y<super>2</super>", styles['Normal'])
```

For canvas-drawn text (not Paragraph objects), manually adjust font the size and position rather than using Unicode subscripts/superscripts.

## Command-Line Tools

### pdftotext (poppler-utils)
```bash
# Extract text
pdftotext input.pdf output.txt

# Extract text preserving layout
pdftotext -layout input.pdf output.txt

# Extract specific pages
pdftotext -f 1 -l 5 input.pdf output.txt  # Pages 1-5
```

### qpdf
```bash
# Merge PDFs
qpdf --empty --pages file1.pdf file2.pdf -- merged.pdf

# Split pages
qpdf input.pdf --pages . 1-5 -- pages1-5.pdf
qpdf input.pdf --pages . 6-10 -- pages6-10.pdf

# Rotate pages
qpdf input.pdf output.pdf --rotate=+90:1  # Rotate page 1 by 90 degrees

# Remove password
qpdf --password=mypassword --decrypt encrypted.pdf decrypted.pdf
```

### pdftk (if available)
```bash
# Merge
pdftk file1.pdf file2.pdf cat output merged.pdf

# Split
pdftk input.pdf burst

# Rotate
pdftk input.pdf rotate 1east output rotated.pdf
```

## Common Tasks

### Extract Text from Scanned PDFs
```python
# Requires: pip install pytesseract pdf2image
import pytesseract
from pdf2image import convert_from_path

# Convert PDF to images
images = convert_from_path('scanned.pdf')

# OCR each page
text = ""
for i, image in enumerate(images):
    text += f"Page {i+1}:\n"
    text += pytesseract.image_to_string(image)
    text += "\n\n"

print(text)
```

### Add Watermark
```python
from pypdf import PdfReader, PdfWriter

# Create watermark (or load existing)
watermark = PdfReader("watermark.pdf").pages[0]

# Apply to all pages
reader = PdfReader("document.pdf")
writer = PdfWriter()

for page in reader.pages:
    page.merge_page(watermark)
    writer.add_page(page)

with open("watermarked.pdf", "wb") as output:
    writer.write(output)
```

### Extract Images
```bash
# Using pdfimages (poppler-utils)
pdfimages -j input.pdf output_prefix

# This extracts all images as output_prefix-000.jpg, output_prefix-001.jpg, etc.
```

### Password Protection
```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("input.pdf")
writer = PdfWriter()

for page in reader.pages:
    writer.add_page(page)

# Add password
writer.encrypt("userpassword", "ownerpassword")

with open("encrypted.pdf", "wb") as output:
    writer.write(output)
```

## Quick Reference

| Task | Best Tool | Command/Code |
|------|-----------|--------------|
| Merge PDFs | pypdf | `writer.add_page(page)` |
| Split PDFs | pypdf | One page per file |
| Extract text | pdfplumber | `page.extract_text()` |
| Extract tables | pdfplumber | `page.extract_tables()` |
| Create PDFs | reportlab | Canvas or Platypus |
| Command line merge | qpdf | `qpdf --empty --pages ...` |
| OCR scanned PDFs | pytesseract | Convert to image first |
| Fill PDF forms | pdf-lib or pypdf (see FORMS.md) | See FORMS.md |

## Next Steps

- For advanced pypdfium2 usage, see REFERENCE.md
- For JavaScript libraries (pdf-lib), see REFERENCE.md
- If you need to fill out a PDF form, follow the instructions in FORMS.md
- For troubleshooting guides, see REFERENCE.md
