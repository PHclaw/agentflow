<div align="center">

<!-- Animated GIF rather than SVG on purpose: GitHub proxies SVGs through camo and strips
     scripts/animation, while a GIF plays everywhere. Demo assets live in assets/. -->
<img src="assets/banner.gif" alt="AgentFlow — Zero-code AI Agent Platform" width="100%">

<br>

[![Stars](https://img.shields.io/github/stars/PHclaw/agentflow?style=flat-square&logo=github&label=Stars&color=6366F1)](https://github.com/PHclaw/agentflow/stargazers)
[![Forks](https://img.shields.io/github/forks/PHclaw/agentflow?style=flat-square&label=Forks&color=00D9C0)](https://github.com/PHclaw/agentflow/forks)
[![Issues](https://img.shields.io/github/issues/PHclaw/agentflow?style=flat-square&label=Issues&color=F59E0B)](https://github.com/PHclaw/agentflow/issues)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue?style=flat-square)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](https://github.com/PHclaw/agentflow/pulls)

[![CI](https://img.shields.io/github/actions/workflow/status/PHclaw/agentflow/ci.yml?style=flat-square&label=CI)](.github/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=white)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.3-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Docker](https://img.shields.io/badge/Docker-compose-2496ED?style=flat-square&logo=docker&logoColor=white)](docker-compose.yml)

**Drag-and-drop AI Agent workflows · No code required · Live in 5 minutes**

An open-source, zero-code AI Agent platform: drag-and-drop workflow editor + multi-model hot-swap + knowledge-base RAG + Skill marketplace + one-command deploy.<br>
Runs on SQLite out of the box, so a single machine is enough — and every byte of data stays on your own hardware.

<br>

<a href="http://159.75.21.251:3000/"><img src="https://img.shields.io/badge/%F0%9F%9A%80_Try_it_online-159.75.21.251%3A3000-6366F1?style=for-the-badge&labelColor=4338CA" alt="Try it online · no install"></a>

<br>

<sub>No install needed · just open it in a browser · sign up and build your own Agent</sub>

<br>

[Product demo](#️-product-demo) · [Quick start](#-quick-start) · [Features](#-features) · [Skill extension](#-skill-extension) · [Docs](#-docs) · [FAQ](docs/FAQ.md)

<br>

[English](README.en.md) · [中文](README.md)

</div>

---

## 📖 Table of contents

- [Product demo](#️-product-demo)　·　[Screenshots](#️-screenshots)
- [Features](#-features)　·　[Skill extension](#-skill-extension)
- [Quick start](#-quick-start)　·　[Key configuration](#️-key-configuration)
- [Architecture](#️-architecture)　·　[Project layout](#-project-layout)
- [How it differs from Dify / Coze](#️-how-it-differs-from-dify--coze)
- [Roadmap](#️-roadmap)　·　[Contributing](#-contributing)
- [Disclaimer](#️-disclaimer)　·　[License](#-license)　·　[Support](#-support)

---

## 📽️ Product demo

> Real screen recordings (captured by a headless browser, unedited). Full videos live in `assets/videos/`.

<h3 align="center">① The whole flow, end to end</h3>

Landing page → sign in → pick a template from the marketplace → create an Agent → chat → put a Skill to work. One clip, everything the product can do.

<img src="assets/gifs/demo-product-tour.gif" alt="Product tour" width="900">

<p align="center"><a href="assets/videos/demo-product-tour.mp4">▶ Full recording</a></p>

<h3 align="center">② One sentence to a PPT — end-to-end delivery</h3>

Describe what you need in the chat box. The Agent reads its own workspace, writes code, runs scripts, and hands the result back as a **downloadable attachment**.

<img src="assets/gifs/demo-ppt-generation.gif" alt="Chat-to-PPT flow" width="900">

<p align="center">
  <a href="assets/videos/demo-ppt-generation.mp4">▶ Full conversation</a> &nbsp;·&nbsp;
  <a href="assets/videos/demo-ppt-result-preview.mp4">▶ Page-by-page preview</a>
</p>

<h3 align="center">③ Building a workflow by dragging nodes</h3>

Pick nodes from the left panel onto the canvas, edit parameters on the right, save and it takes effect immediately — no code at any point.

<img src="assets/gifs/demo-workflow-canvas.gif" alt="Workflow canvas" width="900">

<p align="center">
  <a href="assets/videos/demo-workflow-canvas.mp4">▶ Full recording</a> &nbsp;·&nbsp;
  <a href="assets/videos/demo-workflow-build.mp4">▶ Wiring nodes together</a>
</p>

<h3 align="center">④ Skill marketplace: paste a table, get a chart</h3>

No need to tidy up the format first — messy tables with Chinese units are understood too. The chart shows up in the conversation seconds later, with the raw data and the script alongside.

<img src="assets/gifs/demo-skill-plaza.gif" alt="Skill plaza" width="900">

<p align="center"><a href="assets/videos/demo-skill-plaza.mp4">▶ Full recording</a></p>

<h3 align="center">⑤ Knowledge base: upload and semantic search</h3>

Upload a document → automatic chunking and indexing → recall by relevance when you ask a question. Matched snippets are highlighted right in the UI.

<img src="assets/gifs/demo-knowledge-rag.gif" alt="Knowledge base RAG" width="900">

<p align="center"><a href="assets/videos/demo-knowledge-rag.mp4">▶ Full recording</a></p>

<h3 align="center">⑥ Tool calls inside a conversation</h3>

While the Agent runs, a live "calling tool" line appears; only the current one stays on screen, and it hides itself as soon as the reply is done.

<img src="assets/gifs/demo-chat-tool-calls.gif" alt="Tool calls in chat" width="900">

<p align="center"><a href="assets/videos/demo-chat-tool-calls.mp4">▶ Full recording</a></p>

---

## 🖼️ Screenshots

<img src="assets/screens/05-workflow.png" alt="Workflow editor">

**Workflow editor** — three-column layout of node panel / drag-and-drop canvas / node configuration, node and connection counts in the top bar, with test, undo/redo, import and export.

<table>
<tr>
<td width="50%"><img src="assets/screens/01-landing.png" alt="Landing page"><br><sub><b>Landing page</b> — the no-code value proposition</sub></td>
<td width="50%"><img src="assets/screens/02-dashboard.png" alt="Dashboard"><br><sub><b>Dashboard</b> — total agents, active conversations, knowledge bases, new conversations this month</sub></td>
</tr>
<tr>
<td width="50%"><img src="assets/screens/04-agent-create.png" alt="Agent setup"><br><sub><b>Agent setup</b> — name, prompt, model, with workflow and knowledge base on separate tabs</sub></td>
<td width="50%"><img src="assets/screens/06-chat.png" alt="Chat"><br><sub><b>Chat</b> — streaming replies with inline artifact preview</sub></td>
</tr>
<tr>
<td width="50%"><img src="assets/screens/08-templates.png" alt="Templates"><br><sub><b>Template marketplace</b> — browse by category, one click to apply</sub></td>
<td width="50%"><img src="assets/screens/09-skills.png" alt="Skill plaza"><br><sub><b>Skill plaza</b> — skill extension and installation</sub></td>
</tr>
<tr>
<td width="50%"><img src="assets/screens/10-knowledge.png" alt="Knowledge base"><br><sub><b>Knowledge base</b> — upload, chunk, semantic search</sub></td>
<td width="50%"><img src="assets/screens/07-conversations.png" alt="Conversations"><br><sub><b>Conversations</b> — pick any past session and keep talking</sub></td>
</tr>
</table>

---

## ✨ Features

- **🎨 Drag-and-drop workflow editor** — ReactFlow canvas with six node types (Trigger / LLM / Knowledge / Tool / Condition / Response) to combine freely; edits take effect on save
- **🤖 Multi-model hot-swap** — just fill in the endpoint and model name under Settings → Model Config. Works with any **OpenAI-compatible** endpoint (including local Ollama), **no restart needed**
- **📚 Knowledge-base RAG** — documents are chunked and indexed on upload, vector recall returns results with relevance scores; the embedding model is configured **separately** from the chat model
- **🧩 Skill marketplace** — skills are plain directories with a `SKILL.md`; admins can add or remove them from the console. Community skills are installed separately (see [skills/README.md](skills/README.md))
- **📎 Artifact delivery** — files generated by an Agent come back as downloadable attachments, and **image artifacts render inline in the conversation** instead of forcing a download first
- **🧰 Template marketplace** — customer service / sales / HR / finance scenarios; one click turns a template into a working Agent
- **👤 User system** — JWT auth, email-code signup, plan quotas, admin allowlist, fully self-hosted data

**Who it's for**: companies that want an AI customer-service or sales assistant but have no dev team; product managers who need to validate an Agent scenario fast; developers who want to orchestrate LLM workflows with low code.

---

## 🚀 Quick start

### Requirements

| Dependency | Version | Notes |
|:--|:--|:--|
| Python | 3.11+ | CI baseline; official images use 3.13 |
| Node.js | 18+ | CI baseline; official images use 20 |
| Docker | 20+ | Recommended — one command brings everything up |

> **Neither PostgreSQL nor Redis is required.** SQLite is the default, and when Redis is missing verification codes fall back to process memory — plenty for a single-machine deployment.

### Option 1: Docker (recommended)

```bash
git clone https://github.com/PHclaw/agentflow.git
cd agentflow
cp .env.example .env      # at minimum, set JWT_SECRET_KEY
docker compose up -d --build
docker compose logs -f backend
```

Open http://localhost:3000 and you're in. The default stack is just two containers (backend + frontend/nginx), data lands in `./data/agentflow.db`, and `docker compose down` won't lose it.

If you need PostgreSQL + pgvector:

```bash
docker compose --profile postgres up -d
```

### Option 2: local development

```bash
# backend
cd backend && python -m venv venv
.\venv\Scripts\Activate.ps1          # macOS / Linux: source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# frontend (in another terminal)
cd frontend && npm install && npm run dev
```

The frontend dev server runs on http://localhost:5173 , the backend on http://localhost:8001 .

### Option 3: SQLite single-machine lite mode

Just want the backend running, without installing PostgreSQL and Redis:

```powershell
.\scripts\dev-backend.ps1
```

> For environment variables, model configuration and other details, see the **[configuration guide](docs/CONFIGURATION.md)**.

---

## ⚙️ Key configuration

The full list lives in [`.env.example`](.env.example) (every entry is commented) and the **[configuration guide](docs/CONFIGURATION.md)**. The ones you'll touch most:

| Variable | Required | Notes |
|:--|:--:|:--|
| `JWT_SECRET_KEY` | ✅ | Falls back to a built-in plaintext secret when empty, which means anyone can forge a token. `openssl rand -hex 32` |
| `DATABASE_URL` | — | Empty = SQLite; for PostgreSQL use `postgresql+asyncpg://…` |
| `REDIS_URL` | — | Empty = verification codes in process memory; only needed for multi-instance deploys |
| `EMBEDDING_BASE_URL` | Recommended for Docker | Embedding model for the knowledge base. **The official image does not ship sentence-transformers**, so leaving it empty falls back to local inference and fails |
| `ADMIN_EMAILS` | — | Admin email allowlist; logging in grants console access (grant-only, never revoked) |
| `REQUIRE_EMAIL_CODE` | — | Keep `true` in production; set `false` for internal demos |
| `MAIL_ENABLED` | — | When `false` no mail is sent and the code is printed to the backend log |
| `FREE_AGENTS` / `TEAM_AGENTS` etc. | — | Plan quotas, **defined in exactly one place**, shared by copy and enforcement |

**Three easy traps** (all spelled out in `.env.example`):

1. **Don't leave `DATABASE_URL` as an empty string.** An empty value is treated as a real connection string and the backend won't start — if you don't need to change it, comment the whole line out.
2. **Always set `EMBEDDING_BASE_URL` for Docker deployments.** The image doesn't include `sentence-transformers` (about 2GB extra), so knowledge-base search is unavailable when it's empty.
3. **Changing plan quotas requires a re-login to take effect.** Quotas are defined once in `.env` to avoid "advertise 20, enforce 5".

---

## 🏗️ Architecture

![AgentFlow system architecture](assets/architecture-en.svg)

```
   React 18 + ReactFlow  ──►  FastAPI  ──►  SQLite (default)
        frontend :5173 / :3000      backend :8001      └ switchable to PostgreSQL + pgvector
                                                          └ Redis (optional, verification codes)
```

| Layer | Tech |
|:--|:--|
| Frontend | React 18 · TypeScript 5.3 · Vite 5 · ReactFlow 11 · Tailwind CSS 3 · Zustand 4 · react-router 6 |
| Backend | Python 3.11+ · FastAPI · SQLAlchemy 2.0 (async) · Alembic · pydantic-settings |
| Storage | SQLite (default, `aiosqlite`) · PostgreSQL + pgvector (optional) · Redis (optional) |
| Models | Any OpenAI-compatible endpoint: OpenAI · Anthropic · DeepSeek · Qwen · Ollama … |
| Retrieval | Vector embeddings configured independently, decoupled from the chat model |
| Deploy | Docker Compose (FastAPI + nginx) · local venv / npm |
| CI | GitHub Actions: ruff + pytest / tsc + vite build |

The full picture — system architecture, workflow node types, request flow — is in the **[architecture guide](docs/ARCHITECTURE.md)**.

---

## 📁 Project layout

```
agentflow/
├── backend/            # FastAPI application
│   ├── app/
│   │   ├── api/        # REST routes: auth / users / agents / templates / knowledge / chat / skills …
│   │   ├── core/       # config, security, database
│   │   ├── models/     # SQLAlchemy models
│   │   └── services/   # workflow engine, skill execution, model gateway
│   └── tests/
├── frontend/           # React + Vite application
│   └── src/
│       ├── pages/      # landing / dashboard / agent / workflow / chat / skills / knowledge / templates
│       ├── components/ # UI kit, layout, workflow nodes
│       ├── stores/     # Zustand
│       └── services/   # API client
├── skills/             # skill directory (docs only; skills installed separately)
├── static/             # runtime artifacts mount point (avatars / generated files)
├── docs/               # documentation
├── assets/             # banner / screenshots / GIFs / videos used by the README
├── config/             # static config for model validation
├── docker-compose.yml
└── .env.example
```

---

## 🧩 Skill extension

> **This repository does not ship third-party skills.** Community skills carry different licenses (Apache-2.0 / MIT / no notice / all rights reserved) and cannot be redistributed as a whole under Apache-2.0; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). `skills/` is kept as an empty runtime mount point. Startup does not depend on any skill: an empty directory simply yields an empty plaza, and all other features work. To install one, drop a directory containing `SKILL.md` into `skills/` and keep its original LICENSE. The table below lists optional community skills, not bundled content:

| Skill | What it does |
|:--|:--|
| **Excel Assistant** | Upload Excel/CSV or paste a table → charts, grouped summaries, export |
| **PPT Assistant** | Generates a 16:9 HTML deck after confirming purpose and slide count, editable |
| **HTML Slides** | Multi-style static HTML presentations |
| **Frontend Slides** | Author animation-rich HTML presentations from scratch or by conversion |
| **PDF Assistant** | Upload a PDF → extract TOC, key points, tables, or just ask the document questions |
| **Academic Search** | Search papers by topic, with year, authors, citations and a clickable summary table |
| **Paper Notes** | Turn a paper into problem / method / results / limitations / references notes |
| **Meeting Notes** | Raw meeting transcript → conclusions, decisions and a task table (owners / deadlines) |
| **Clinical Case Report** | Chief complaint and findings → structured teaching case |
| **Statistics Assistant** | Hypothesis testing, sample size, confidence intervals, with decision advice |
| **Chart Visualization** | Picks the chart type that fits the data and renders it |

Self-authored skills carry no such restrictions: add a folder following the `SKILL.md` format. The optional HTML-PPT pipeline also reads assets such as `skills/html-ppt-skill-main/assets`; calling it without those skills installed raises a missing-file error, which is expected.

---

## ⚖️ How it differs from Dify / Coze

|  | AgentFlow | Dify | Coze | WorkBuddy | Codex |
|:--|:--:|:--:|:--:|:--:|:--:|
| Positioning | Zero-code agent orchestration | LLM app development platform | Conversational bot builder | Desktop AI agent workbench for office work | Terminal coding agent |
| Deployment | Self-hosted first, **SQLite single-machine by default** | Self-hosted / cloud | Cloud only | Desktop client, install and run | Local CLI + cloud sandbox |
| Data ownership | All in your own database | Yours when self-hosted | On the platform side | Local execution; enterprise edition centrally managed | Code stays local; cloud tasks run in sandboxes |
| License | **Apache-2.0** | Open source (with additional terms) | Closed source | Proprietary | Open source (CLI, Apache-2.0) |
| Multi-model hot-swap | Change it in the UI, **no restart** | Edit config | Platform-bound | Hunyuan-first, hybrid multi-model access | OpenAI models mainly, configurable endpoints |
| Skill extension | Add a directory with `SKILL.md` | Plugin marketplace | Plugin marketplace | Built-in skills + office connectors | MCP + config files |
| Deliverables | ✅ file download + **inline image preview** | Partial | Partial | Reports / decks / spreadsheets | Code diffs and command output |

> WorkBuddy and Codex belong to different categories — a desktop office agent and a terminal coding agent — rather than visual agent-orchestration platforms like the first three. They are listed for positioning context, not as a ranking of like-for-like competitors.

The full comparison lives in **[How it differs from Dify / Coze](docs/COMPARISON.md)**.

---

## 🗺️ Roadmap

- [x] Drag-and-drop workflow editor (six node types)
- [x] Multi-model hot-swap + any OpenAI-compatible endpoint
- [x] Knowledge-base RAG (embedding model configured independently)
- [x] Skill plaza and template marketplace
- [x] Artifact delivery + inline image preview
- [x] One-command Docker Compose deploy (SQLite by default)
- [ ] End-to-end pgvector path verification
- [ ] Async task queue (the current compose has no worker container; `celery_app.py` is unreferenced)
- [ ] More skills and templates

---

## 📚 Docs

| Document | Contents |
|:--|:--|
| [Configuration guide](docs/CONFIGURATION.md) | Environment variables · model hot-swap · SQLite lite mode |
| [Architecture guide](docs/ARCHITECTURE.md) | System architecture · workflow node types · project layout |
| [Deployment guide](docs/DEPLOYMENT.md) | Docker · Nginx reverse proxy · database backup |
| [API reference](docs/API.md) | REST endpoints · auth · error handling |
| [Development guide](docs/DEVELOPMENT.md) | Tests · database migrations · UI diagnostic scripts |
| [FAQ](docs/FAQ.md) | Models · RAG · self-hosting · billing |
| [Changelog](docs/CHANGELOG.md) | Version history and roadmap |

> These documents are written in Chinese.

Once the server is up, the live API docs are at http://localhost:8001/docs (Swagger) · http://localhost:8001/redoc

---

## 🤝 Contributing

Issue → Fork → Branch → Develop → Test → PR → Review → Merge

- Run the two CI steps locally before pushing: `cd backend && ruff check app/ && python -m pytest tests/ -v` and `cd frontend && npx tsc --noEmit && npm run build`
- See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow; report security issues privately per [SECURITY.md](SECURITY.md)

---

## ⚠️ Disclaimer

> Licensed under **Apache-2.0**: use, modification and redistribution, including commercial use, are permitted. No use restrictions beyond the license terms.

**Use and compliance:**

- This repository ships no API keys, mail credentials or user data; deployers configure `.env` themselves and keep it private
- Users should assess the suitability and risk of the project themselves and comply with local laws
- When using crawler, document parsing or data analysis features, users must comply with robots.txt, terms of service, data protection law and third-party content licenses

**Crawler disclaimer:**

- Users determine the applicable scenario for crawler features and bear the corresponding responsibility
- Users must comply with the robots.txt protocol and terms of use of the target websites
- Users must comply with applicable laws and regulations, and must not crawl maliciously or abuse data
- Any legal consequences arising from use of the crawler functionality are borne solely by the user

**Data usage disclaimer:**

- Users are responsible for determining the suitability and compliance obligations of the data analysis features
- Any legal consequences arising from use of this project are borne solely by the user
- Users should ensure the legality and compliance of the data being analyzed

**Technical disclaimer:**

- This project is provided "as is", without any express or implied warranty
- The authors accept no liability for any direct or indirect loss caused by use of this project
- Users should assess the suitability and risk of the project themselves

**Limitation of liability:**

- Users should fully understand applicable laws and regulations before using this project
- Users should ensure their use complies with local laws and regulations
- Any consequence arising from use of this project in violation of laws and regulations is borne solely by the user

See [SECURITY.md](SECURITY.md) for private vulnerability reporting.

---

## 📄 License

Released under the **Apache License 2.0**. Full text in [LICENSE](LICENSE). Third-party skills and assets are not distributed with this repository; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

## 🎉 Support

### Getting help

| Channel | Where |
|:--|:--|
| FAQ | [docs/FAQ.md](docs/FAQ.md) |
| Live demo | [http://159.75.21.251:3000/](http://159.75.21.251:3000/) |
| Bug reports | [Issues](https://github.com/PHclaw/agentflow/issues) |
| Feature requests | [Discussions](https://github.com/PHclaw/agentflow/discussions) |

### Contact

📧 Email: 2730545346@qq.com

### Business inquiries

- Enterprise custom development
- Big data services
- Academic collaboration
- Technical training

---

<div align="center">

**Find it useful? Leave a ⭐**

[⭐ Star](https://github.com/PHclaw/agentflow) · [🍴 Fork](https://github.com/PHclaw/agentflow/fork) · [🐛 Issues](https://github.com/PHclaw/agentflow/issues)
## Star History

<a href="https://www.star-history.com/?repos=phclaw%2Fagentflow&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=phclaw/agentflow&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=phclaw/agentflow&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=phclaw/agentflow&type=date&legend=to