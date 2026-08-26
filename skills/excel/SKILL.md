---
{
  "id": "excel",
  "name": "Excel表格助手",
  "description": "上传 Excel/CSV，或直接粘贴空格表/Markdown/CSV：探查结构、按类别汇总、SQL 分析、导出 xlsx、画常用统计图。\n\n【我会做】\n· 多 sheet 探查（列类型、行数、样例）\n· 粘贴「月份 铅笔 10支」这类文本表，自动去掉支/块等单位\n· 按类别把宽表透视汇总，并导出可下载 Excel\n· 描述统计；也可直接跑 SELECT\n· 本地出图（柱状/折线/饼/散点/直方 PNG）\n\n【怎么开始】上传文件，或把表格贴在消息里再说「按类别汇总，导出 Excel」。问「你会干什么」会介绍能力。",
  "specialty": "表格处理",
  "routerBlurb": "表格分析 + 导出工作簿 + 常用统计图，适合日常 Excel/CSV。",
  "triggers": [
    "excel",
    "xlsx",
    "csv",
    "表格",
    "透视",
    "汇总",
    "画图",
    "可视化",
    "DuckDB",
    "电子表格"
  ],
  "tags": [
    "办公",
    "Excel",
    "数据"
  ],
  "version": "v1.1.0",
  "model": "chatzoc_9b_B",
  "params": {
    "temperature": 0.2,
    "maxTokens": 4096
  },
  "authorId": "platform-preset",
  "authorName": "平台预置",
  "visibility": "public",
  "status": "published",
  "changelog": "v1.1：粘贴空格表与中文单位；按类别汇总；xlsx/data-analysis 脚本收进本目录",
  "systemPrompt": "你是 Excel/CSV 表格助手。本会话只使用当前已选定的本 Skill，禁止改用、推荐调用或假装已调用其它 Skill。平台已在「脚本结果」中跑完探查、查询、导出或出图。\n\n硬性规则：\n0) intent=intro：按 stdout 完整能力卡片介绍，禁止套用结果模板、禁止声称已分析文件。\n1) 有上传文件或脚本已解析粘贴表格时必须承认已有数据，禁止说看不到表格。\n2) 数字、列名、SQL 必须以脚本 stdout 为准，禁止编造。\n3) exitCode=0 且 intent=export 且有 downloadUrl：只给 Excel 下载链接，禁止出图、禁止提柱状图/饼图。intent=chart 且有 imageUrl：用 Markdown 图片展示。用户点名的月均/合计/总销量必须已写入 xlsx，禁止只在对话里口述。\n4) 查询失败时根据 stderr 说明如何改 SQL 或改用「按某列汇总」。空格表、「10支」这类带单位数字平台会自动识别。\n5) 默认简体中文；结论先行；不要寒暄；禁止复制系统时钟。\n\n输出结构：\n## 结果\n## 下载 / 图表（仅当工具确实生成了对应文件）\n## 说明",
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
      "title": "按列汇总并导出",
      "note": "验收：有 downloadUrl 与汇总表",
      "variables": {
        "input": "按类别汇总金额，导出 Excel"
      }
    }
  ],
  "workflow": {
    "agentId": "excel",
    "version": "1.1.0",
    "kind": "excel",
    "steps": [
      {
        "name": "表格工具",
        "action": "runExcelTool"
      },
      {
        "name": "模型解读",
        "action": "callModel",
        "model": "chatzoc_9b_B"
      }
    ]
  },
  "totalCalls": 68,
  "avgRating": 0.0,
  "publishedAt": "2026-08-20T01:11:07",
  "createdAt": "2026-08-20T01:11:07",
  "updatedAt": "2026-08-21T01:31:18",
  "workflowKind": "excel"
}
---

# Excel表格助手

本目录即原 `xlsx` + `data-analysis` + 平台 `excel` 的合并结果（广场只加载这一份）。

- 运行时：`app/services/skill/excel_engine.py`、`excel_pipeline.py`
- 公式重算（可选）：`scripts/recalc.py`
- 参考 CLI：`scripts/analyze.py`

粘贴空格/制表符对齐的文本表即可分析；`10支`、`8块` 会收成数字。宽表说「按类别汇总」会按列名透视后再导出。

常用图种在本地生成 PNG。A/B 假设检验请用「统计分析助手」。
