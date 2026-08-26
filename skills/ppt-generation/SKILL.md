---
{
  "id": "ppt-generation",
  "name": "PPT助手",
  "description": "问卷确认用途、页数、内容与密度 → 选风格封面 → 生成 16:9 HTML 演示稿和可编辑 PPTX。也可读取或替换已有 pptx。\n\n【怎么开始】说「做一份 PPT」。选项用题号+字母一次答完，如 `1b 2a 3a 4b`。详细大纲请写在当前消息。\n【示例】做一份季度复盘 PPT；读取我上传的 pptx 有几页。",
  "specialty": "PPT处理",
  "routerBlurb": "逐步确认用途与风格，再产出可在浏览器演示的 HTML 幻灯片。",
  "triggers": [
    "PPT",
    "pptx",
    "演示文稿",
    "幻灯片",
    "PowerPoint",
    "做PPT",
    "生成PPT",
    "读PPT",
    "改PPT",
    "keynote"
  ],
  "tags": [
    "办公",
    "PPT",
    "演示"
  ],
  "version": "v1.3.1",
  "model": "chatzoc_9b_B",
  "params": {
    "temperature": 0.35,
    "maxTokens": 3072
  },
  "authorId": "platform-preset",
  "authorName": "平台预置",
  "visibility": "public",
  "status": "published",
  "changelog": "问卷对齐 frontend-slides：用途/页数/内容/密度；无正文不生成；HTML 固定 1920×1080 + html-ppt 主题模板",
  "systemPrompt": "你是 PPT 助手。平台用向导逐步确认需求；每一步都要真正理解用户并组织回复，不要只复读脚本。\n\n硬性规则：\n0) intent=intro：按脚本 stdout 完整能力卡片介绍（问卷、风格选择、HTML+PPTX、示例），不要只说一句。\n1) intent=brief / content-ask：把脚本中的题号 1/2/3/4 与选项 a/b/c/d 完整列出，请用户输入如 `1b 2a 3a 4b`；也可以自己写。禁止改成点选按钮或开放问答题。禁止生成完整 PPT。\n2) intent=style-preview：对比 style-a/b/c，给出 HTML 链接，请用户输入 `1a`/`1b`/`1c`。禁止声称这是完整稿。\n3) intent=generate 且含 downloadUrl：说明已按当轮大纲与所选主题生成，给出 HTML 与 PPTX。\n4) 默认简体中文；结论先行；不要复制系统时钟。\n\n输出结构：\n## 结果\n## 下载（如有）\n## 说明",
  "userPrompt": "请根据用户需求与平台工具结果回复。\n\n## 用户需求\n{{input}}\n\n## 脚本结果\n{{tool_result}}",
  "variables": [
    {
      "name": "input",
      "type": "string"
    },
    {
      "name": "tool_result",
      "type": "string"
    }
  ],
  "examples": [
    {
      "title": "按大纲生成PPT",
      "note": "验收：有 downloadUrl",
      "expectHighlights": [
        "downloadUrl",
        "pptx"
      ],
      "variables": {
        "input": "生成一份 PPT，风格 keynote。\n标题：季度业务复盘\n1. 目标回顾\n- 营收\n- 毛利"
      }
    }
  ],
  "workflow": {
    "agentId": "ppt-generation",
    "version": "1.1.0",
    "kind": "ppt-generation",
    "steps": [
      {
        "name": "PPT工具",
        "action": "runPptTool"
      },
      {
        "name": "模型解读",
        "action": "callModel",
        "model": "chatzoc_9b_B"
      }
    ]
  },
  "totalCalls": 23,
  "avgRating": 0.0,
  "publishedAt": "2026-08-12T10:00:00",
  "createdAt": "2026-08-12T10:00:00",
  "updatedAt": "2026-08-19T09:15:40",
  "workflowKind": "ppt-generation"
}
---

# PPT助手

结合 html-ppt 主题版式与 frontend-slides 的逐步确认流程。广场只保留这一份 Skill；`html-ppt-skill-main` / `frontend-slides-main` 仅作模板资源。

1. 问用途、页数、能否在浏览器改字
2. 问风格选择方式与观感
3. 给出 style-a / style-b / style-c 三套封面
4. 你选定后再生成完整 HTML 演示稿，并附 PPTX

- 读取：上传 `.pptx`，说「读大纲」
- 替换：上传 `.pptx`，说「把旧词改成新词」
- 想跳过问卷：说「直接生成」
