<div align="center">

<!-- 这里用 GIF 而不是 SVG：GitHub 会把 SVG 交给 camo 代理做净化，脚本一定被剥掉、SMIL/CSS 动画也不保证执行，GIF 则无条件播放。可编辑源文件是同目录的 assets/banner.svg，GIF 由 scripts/build-banner-gif.py 逐帧渲染合成；静态回退仍是 assets/banner.png -->
<img src="assets/banner.gif" alt="AgentFlow — 零代码 AI Agent 平台" width="100%">

<br>

[![Stars](https://img.shields.io/github/stars/PHclaw/agentflow?style=flat-square&logo=github&label=Stars&color=6366F1)](https://github.com/PHclaw/agentflow/stargazers)
[![Forks](https://img.shields.io/github/forks/PHclaw/agentflow?style=flat-square&label=Forks&color=00D9C0)](https://github.com/PHclaw/agentflow/forks)
[![Issues](https://img.shields.io/github/issues/PHclaw/agentflow?style=flat-square&label=Issues&color=F59E0B)](https://github.com/PHclaw/agentflow/issues)
[![License](https://img.shields.io/badge/License-GPL--2.0-FF6B6B?style=flat-square)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)](https://github.com/PHclaw/agentflow/pulls)

[![CI](https://img.shields.io/github/actions/workflow/status/PHclaw/agentflow/ci.yml?style=flat-square&label=CI)](.github/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=white)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.3-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Docker](https://img.shields.io/badge/Docker-compose-2496ED?style=flat-square&logo=docker&logoColor=white)](docker-compose.yml)

**拖拽式构建 AI Agent 工作流 · 无需一行代码 · 5 分钟上线**

开源零代码 AI Agent 平台：拖拽式工作流编辑器 + 多模型热切换 + 知识库 RAG + Skill 广场 + 一键部署。<br>
默认用 SQLite 起，单机就能跑；数据全部落在你自己的机器上。

[功能演示](#-功能演示) · [快速开始](#-快速开始) · [核心特性](#-核心特性) · [内置技能](#-内置技能) · [文档](#-文档) · [常见问题](docs/FAQ.md)

</div>

---

## 📖 目录

- [功能演示](#-功能演示)　·　[界面一览](#️-界面一览)
- [核心特性](#-核心特性)　·　[内置技能](#-内置技能)
- [快速开始](#-快速开始)　·　[关键配置](#️-关键配置)
- [技术架构](#️-技术架构)　·　[项目结构](#-项目结构)
- [与 Dify / Coze 的差异](#️-与-dify--coze-的差异)
- [路线图](#️-路线图)　·　[贡献](#-贡献)
- [免责声明](#️-免责声明)　·　[许可证](#-许可证)　·　[支持与联系](#-支持与联系)

---

## 📽️ 功能演示

> 全部是真实录屏（headless 浏览器自动采集，未剪辑）。完整视频在 `assets/videos/`。

<h3 align="center">① 全流程走一遍</h3>

落地页 → 登录 → 模板广场选模板 → 建 Agent → 对话 → Skill 实战，一条片子看完产品能做什么。

<img src="assets/gifs/demo-product-tour.gif" alt="产品全流程" width="900">

<p align="center"><a href="assets/videos/demo-product-tour.mp4">▶ 完整录屏</a></p>

<h3 align="center">② 一句话生成 PPT —— 端到端交付</h3>

在对话框里描述需求，Agent 自己读工作区、写代码、跑脚本，最后把生成的文件作为**可下载附件**交回来。

<img src="assets/gifs/demo-ppt-generation.gif" alt="对话生成 PPT 全流程" width="900">

<p align="center">
  <a href="assets/videos/demo-ppt-generation.mp4">▶ 完整对话过程</a> &nbsp;·&nbsp;
  <a href="assets/videos/demo-ppt-result-preview.mp4">▶ 生成结果逐页预览</a>
</p>

<h3 align="center">③ 拖拽搭建工作流</h3>

左侧节点面板点选即入画布，右侧实时编辑参数，保存后立即生效——全程不写代码。

<img src="assets/gifs/demo-workflow-canvas.gif" alt="拖拽搭建工作流" width="900">

<p align="center">
  <a href="assets/videos/demo-workflow-canvas.mp4">▶ 完整录屏</a> &nbsp;·&nbsp;
  <a href="assets/videos/demo-workflow-build.mp4">▶ 节点连线</a>
</p>

<h3 align="center">④ Skill 广场：贴一张表就出图</h3>

不用整理格式，带中文单位的随手记表格也能认；几十秒后图表直接显示在对话里，原始数据与脚本一并给出。

<img src="assets/gifs/demo-skill-plaza.gif" alt="Skill 广场出图" width="900">

<p align="center"><a href="assets/videos/demo-skill-plaza.mp4">▶ 完整录屏</a></p>

<h3 align="center">⑤ 知识库上传与语义检索</h3>

上传文档 → 自动分块入库 → 提问时按相关度召回，命中片段在界面直接标出。

<img src="assets/gifs/demo-knowledge-rag.gif" alt="知识库上传与检索" width="900">

<p align="center"><a href="assets/videos/demo-knowledge-rag.mp4">▶ 完整录屏</a></p>

<h3 align="center">⑥ 对话中的工具调用</h3>

Agent 执行时实时显示「正在调用工具」，同屏只保留当前这一条，回复生成完毕自动隐藏。

<img src="assets/gifs/demo-chat-tool-calls.gif" alt="对话中的工具调用" width="900">

<p align="center"><a href="assets/videos/demo-chat-tool-calls.mp4">▶ 完整录屏</a></p>

---

## 🖼️ 界面一览

<img src="assets/screens/05-workflow.png" alt="工作流编辑器">

**工作流编辑器** — 节点面板 / 拖拽画布 / 节点配置三栏布局，顶部显示节点与连接数，支持测试、撤销重做、导入导出。

<table>
<tr>
<td width="50%"><img src="assets/screens/01-landing.png" alt="落地页"><br><sub><b>落地页</b> — 无代码搭建的价值主张</sub></td>
<td width="50%"><img src="assets/screens/02-dashboard.png" alt="控制台"><br><sub><b>控制台</b> — Agent 数、活跃对话、模型用量</sub></td>
</tr>
<tr>
<td width="50%"><img src="assets/screens/04-agent-create.png" alt="Agent 配置"><br><sub><b>Agent 配置</b> — 模型、提示词、工作流、技能</sub></td>
<td width="50%"><img src="assets/screens/06-chat.png" alt="对话页"><br><sub><b>对话页</b> — 流式回复 + 产物内联预览</sub></td>
</tr>
<tr>
<td width="50%"><img src="assets/screens/08-templates.png" alt="模板市场"><br><sub><b>模板市场</b> — 按分类挑，一键套用成 Agent</sub></td>
<td width="50%"><img src="assets/screens/09-skills.png" alt="Skill 广场"><br><sub><b>Skill 广场</b> — 9 个预置技能，开箱即用</sub></td>
</tr>
<tr>
<td width="50%"><img src="assets/screens/10-knowledge.png" alt="知识库"><br><sub><b>知识库</b> — 上传、分块、语义检索</sub></td>
<td width="50%"><img src="assets/screens/07-conversations.png" alt="对话记录"><br><sub><b>对话记录</b> — 随时回到历史会话继续聊</sub></td>
</tr>
</table>

---

## ✨ 核心特性

- **🎨 拖拽式工作流编辑** — ReactFlow 画布，触发器 / LLM / 知识库 / 工具 / 条件分支 / 回复 六类节点自由组合，改完即生效
- **🤖 多模型热切换** — 在「设置 → 模型配置」里填端点与模型名即可，支持任意 **OpenAI 兼容**端点（含本地 Ollama），**改完不用重启**
- **📚 知识库 RAG** — 上传文档自动分块入库，向量检索召回结果带相关度；向量模型与对话模型**分开配置**
- **🧩 Skill 广场** — 9 个预置技能（Excel / PPT / PDF / 学术检索 / 会议纪要 / 统计分析等），管理员可在后台增删
- **📎 产物交付** — Agent 生成的文件回传为可下载附件；**图片类产物在对话里直接内联渲染**，不用先下载再看
- **🧰 模板市场** — 客服 / 销售 / HR / 财务等场景模板，一键套用即成为可用的 Agent
- **👤 用户体系** — JWT 认证、邮箱验证码注册、套餐额度、管理后台白名单，数据完全自托管

**适合谁用**：想搭 AI 客服 / 销售助手但没有开发团队的企业；需要快速验证 Agent 场景的产品经理；想用低代码编排 LLM 工作流的开发者。

---

## 🚀 快速开始

### 环境要求

| 依赖 | 版本 | 说明 |
|:--|:--|:--|
| Python | 3.11+ | CI 基线版本；官方镜像用 3.13 |
| Node.js | 18+ | CI 基线版本；官方镜像用 20 |
| Docker | 20+ | 推荐，一条命令起全部 |

> **PostgreSQL 和 Redis 都不是必需的**。默认用 SQLite 文件，Redis 缺失时验证码自动退回进程内存——单机部署完全够用。

### 方式一：Docker（推荐）

```bash
git clone https://github.com/PHclaw/agentflow.git
cd agentflow
cp .env.example .env      # 至少填 JWT_SECRET_KEY
docker compose up -d --build
docker compose logs -f backend
```

打开 http://localhost:3000 即可。默认栈只有两个容器（backend + frontend/nginx），数据落在 `./data/agentflow.db`，`docker compose down` 不会丢。

需要 PostgreSQL + pgvector 时：

```bash
docker compose --profile postgres up -d
```

### 方式二：本地开发

```bash
# 后端
cd backend && python -m venv venv
.\venv\Scripts\Activate.ps1          # macOS / Linux: source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# 前端（另开一个终端）
cd frontend && npm install && npm run dev
```

前端 dev 跑在 http://localhost:5173 ，后端 http://localhost:8001 。

### 方式三：SQLite 单机轻量模式

只想把后端跑起来、不想装 PostgreSQL 和 Redis：

```powershell
.\scripts\dev-backend.ps1
```

> 环境变量、模型配置、PiAgent 引擎等细节见 **[配置说明](docs/CONFIGURATION.md)**。

---

## ⚙️ 关键配置

完整清单见 [`.env.example`](.env.example)（每一项都写了注释）与 **[配置说明](docs/CONFIGURATION.md)**。最常改的几项：

| 变量 | 必填 | 说明 |
|:--|:--:|:--|
| `JWT_SECRET_KEY` | ✅ | 不填会退化成内置明文密钥，等于任何人可伪造 token。`openssl rand -hex 32` |
| `DATABASE_URL` | — | 留空＝SQLite；换 PostgreSQL 填 `postgresql+asyncpg://…` |
| `REDIS_URL` | — | 留空＝验证码走进程内存；多实例部署才需要 |
| `EMBEDDING_BASE_URL` | Docker 部署建议填 | 知识库向量模型。**官方镜像没装 sentence-transformers**，留空会走本地推理而失败 |
| `ADMIN_EMAILS` | — | 管理员邮箱白名单，登录即获得后台权限（只授予不回收） |
| `REQUIRE_EMAIL_CODE` | — | 生产保持 `true`；内网演示可设 `false` |
| `MAIL_ENABLED` | — | `false` 时不发信，验证码直接打印在后端日志 |
| `PIAGENT_ENABLED` | — | 开启后 Agent 可走 PiAgent 引擎（需镜像内已装 `pi` CLI） |
| `FREE_AGENTS` / `TEAM_AGENTS` 等 | — | 套餐额度，**只在这一处定义**，文案与判定共用 |

**三个容易踩的坑**（都在 `.env.example` 里写明了）：

1. **别把 `DATABASE_URL` 留成空串**。空值会被当成一个真实连接串，后端直接起不来——不需要改就把整行注释掉。
2. **Docker 部署务必填 `EMBEDDING_BASE_URL`**。镜像里没装 `sentence-transformers`（要加约 2GB），留空则知识库检索不可用。
3. **改完套餐额度要重新登录生效**；额度只在 `.env` 定义一份，避免"宣传 20 个、实际按 5 个判"。

---

## 🏗️ 技术架构

```
   React 18 + ReactFlow  ──►  FastAPI  ──►  SQLite（默认）
        前端 :5173 / :3000      后端 :8001      └ 可切 PostgreSQL + pgvector
                                              └ Redis（可选，验证码存储）
```

| 层 | 技术 |
|:--|:--|
| 前端 | React 18 · TypeScript 5.3 · Vite 5 · ReactFlow 11 · Tailwind CSS 3 · Zustand 4 · react-router 6 |
| 后端 | Python 3.11+ · FastAPI · SQLAlchemy 2.0（async）· Alembic · pydantic-settings |
| 存储 | SQLite（默认，`aiosqlite`）· PostgreSQL + pgvector（可选）· Redis（可选） |
| 模型 | 任意 OpenAI 兼容端点：OpenAI · Anthropic · DeepSeek · 通义 · Ollama … |
| 检索 | 向量嵌入可独立配置，与对话模型解耦 |
| 部署 | Docker Compose（FastAPI + nginx）· 本地 venv / npm |
| CI | GitHub Actions：ruff + pytest / tsc + vite build |

系统架构、工作流节点类型、请求链路的完整说明见 **[架构说明](docs/ARCHITECTURE.md)**。

---

## 📁 项目结构

```
agentflow/
├── backend/            # FastAPI 应用
│   ├── app/
│   │   ├── api/        # REST 路由：auth / users / agents / templates / knowledge / chat / skills …
│   │   ├── core/       # 配置、安全、数据库
│   │   ├── models/     # SQLAlchemy 模型
│   │   └── services/   # 工作流引擎、技能执行、模型网关、PiAgent
│   └── tests/
├── frontend/           # React + Vite 应用
│   └── src/
│       ├── pages/      # 落地页 / 控制台 / Agent / 工作流 / 对话 / 技能 / 知识库 / 模板
│       ├── components/ # UI 组件库、布局、工作流节点
│       ├── stores/     # Zustand
│       └── services/   # API 客户端
├── skills/             # 技能定义（每个技能一个目录，含 SKILL.md 与脚本）
├── scripts/            # 开发脚本 + UI 录屏/诊断（ui-record.mjs 可自动出演示素材）
├── docs/               # 文档
├── assets/             # README 用的 banner / 截图 / GIF / 视频
├── config/             # 模型校验用的静态配置
├── docker-compose.yml
└── .env.example
```

---

## 🧩 内置技能

技能广场开箱即用，管理员可在后台增删（直接写 `skills/` 目录）：

| 技能 | 做什么 |
|:--|:--|
| **Excel表格助手** | 贴一张随手记的表格 → 出柱状图/饼图，或汇总导出 Excel |
| **PPT助手** | 多轮确认用途与页数后生成演示稿 |
| **PPT Master** | 模板化排版生成（内置版式、图表、图标库） |
| **PDF处理助手** | 上传 PDF → 提取目录、要点、表格 |
| **学术文献检索** | 按主题检索论文，给出年份、作者与核心贡献 |
| **文献速读笔记** | 把论文整理成「问题 / 方法 / 结果 / 局限」笔记 |
| **会议纪要助手** | 原始会议记录 → 结论 + 待办 + 负责人 + 截止时间 |
| **临床病例报告** | 主诉与检查 → 结构化教学病例 |
| **统计分析助手** | 假设检验、置信区间、样本量估算，输出决策建议 |

每个技能就是一个带 `SKILL.md` 的目录，照格式加一个文件夹即可扩展自己的技能。

---

## ⚖️ 与 Dify / Coze 的差异

|  | AgentFlow | Dify | Coze |
|:--|:--:|:--:|:--:|
| 部署形态 | 自托管优先，**默认 SQLite 单机可跑** | 自托管 / 云 | 仅云 |
| 数据归属 | 全部在你自己的库里 | 自托管时自主 | 在平台侧 |
| 协议 | **GPL-2.0** | 开源（附加条款） | 闭源 |
| 多模型热切换 | 界面里改，**不用重启** | 需改配置 | 平台绑定 |
| Skill 扩展 | 加一个带 `SKILL.md` 的目录 | 插件市场 | 插件市场 |
| 产物附件回传 | ✅ 文件下载 + **图片内联预览** | 部分 | 部分 |
| 浏览器自动化 | 支持（Browser-Use） | — | — |

完整对比见 **[与 Dify / Coze 的差异](docs/COMPARISON.md)**。

---

## 🗺️ 路线图

- [x] 拖拽式工作流编辑器（六类节点）
- [x] 多模型热切换 + 任意 OpenAI 兼容端点
- [x] 知识库 RAG（向量模型独立配置）
- [x] Skill 广场与模板市场
- [x] 产物附件回传 + 图片内联预览
- [x] Docker Compose 一键部署（SQLite 默认）
- [ ] pgvector 路径端到端验证
- [ ] 异步任务队列（当前编排里没有 worker 容器，`celery_app.py` 未被引用）
- [ ] 英文 README
- [ ] 更多预置技能与模板

---

## 📚 文档

| 文档 | 内容 |
|:--|:--|
| [配置说明](docs/CONFIGURATION.md) | 环境变量 · 模型配置热切换 · SQLite 轻量模式 · PiAgent 引擎 |
| [架构说明](docs/ARCHITECTURE.md) | 系统架构 · 工作流节点类型 · 项目结构 |
| [部署指南](docs/DEPLOYMENT.md) | Docker · Nginx 反向代理 · 数据库备份 |
| [API 文档](docs/API.md) | REST 端点 · 认证 · 错误处理 |
| [开发指南](docs/DEVELOPMENT.md) | 测试 · 数据库迁移 · UI 诊断脚本 |
| [常见问题](docs/FAQ.md) | 模型 · RAG · 自托管 · 计费 |
| [更新日志](docs/CHANGELOG.md) | 版本变更记录与路线图 |

启动后可直接访问在线接口文档：http://localhost:8001/docs （Swagger）· http://localhost:8001/redoc

---

## 🤝 贡献

Issue → Fork → Branch → Develop → Test → PR → Review → Merge

- 提交前本地跑一遍 CI 的两件事：`cd backend && ruff check app/ && python -m pytest tests/ -v`、`cd frontend && npx tsc --noEmit && npm run build`
- 新增技能：在 `skills/` 下按现有目录结构加一个带 `SKILL.md` 的文件夹

---

## ⚠️ 免责声明

> **重要提醒：本项目仅供学习、学术研究和教育目的使用**

**合规性声明：**

- 本项目中的所有代码、工具和功能均仅供学习、学术研究和教育目的使用
- 严禁将本项目用于任何商业用途或盈利性活动
- 严禁将本项目用于任何违法、违规或侵犯他人权益的行为

**爬虫功能免责：**

- 项目中的爬虫功能仅用于技术学习和研究目的
- 使用者必须遵守目标网站的 robots.txt 协议和使用条款
- 使用者必须遵守相关法律法规，不得进行恶意爬取或数据滥用
- 因使用爬虫功能产生的任何法律后果由使用者自行承担

**数据使用免责：**

- 项目涉及的数据分析功能仅供学术研究使用
- 严禁将分析结果用于商业决策或盈利目的
- 使用者应确保所分析数据的合法性和合规性

**技术免责：**

- 本项目按“现状”提供，不提供任何明示或暗示的保证
- 作者不对使用本项目造成的任何直接或间接损失承担责任
- 使用者应自行评估项目的适用性和风险

**责任限制：**

- 使用者在使用本项目前应充分了解相关法律法规
- 使用者应确保其使用行为符合当地法律法规要求
- 因违反法律法规使用本项目而产生的任何后果由使用者自行承担

请在使用本项目前仔细阅读并理解上述免责声明。使用本项目即表示您已同意并接受上述所有条款。

---

## 📄 许可证

本项目采用 **GPL-2.0** 许可证。详细信息请参阅 [LICENSE](LICENSE) 文件。

---

## 🎉 支持与联系

### 获取帮助

| 渠道 | 地址 |
|:--|:--|
| 常见问题解答 | #700 |
| 项目主页 | [GitHub 仓库](https://github.com/PHclaw/agentflow) |
| 问题反馈 | [Issues 页面](https://github.com/PHclaw/agentflow/issues) |
| 功能建议 | [Discussions 页面](https://github.com/PHclaw/agentflow/discussions) |

### 联系方式

📧 邮箱：2730545346@qq.com

### 商务合作

- 企业定制开发
- 大数据服务
- 学术合作
- 技术培训

---

<div align="center">

**觉得有用？给个 ⭐ 吧**

[⭐ Star](https://github.com/PHclaw/agentflow) · [🍴 Fork](https://github.com/PHclaw/agentflow/fork) · [🐛 Issues](https://github.com/PHclaw/agentflow/issues)

</div>
