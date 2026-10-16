<div align="center">

<!-- Animated GIF rather than SVG on purpose: GitHub proxies SVGs through camo and strips
     scripts/animation, while a GIF plays everywhere. Editable source: assets/banner.svg,
     static fallback: assets/banner.png -->
<img src="assets/banner.gif" alt="AgentFlow — Drag-and-drop AI Agent workflows" width="100%">

<br>

[![Stars](https://img.shields.io/github/stars/PHclaw/agentflow?style=flat-square&logo=github&label=Stars&color=6366F1)](https://github.com/PHclaw/agentflow/stargazers)
[![Forks](https://img.shields.io/github/forks/PHclaw/agentflow?style=flat-square&label=Forks&color=00D9C0)](https://github.com/PHclaw/agentflow/forks)
[![Issues](https://img.shields.io/github/issues/PHclaw/agentflow?style=flat-square&label=Issues&color=F59E0B)](https://github.com/PHclaw/agentflow/issues)
[![License](https://img.shields.io/badge/License-MIT-FF6B6B?style=flat-square)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](https://github.com/PHclaw/agentflow/pulls)

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=white)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Docker](https://img.shields.io/badge/Docker-compose-2496ED?style=flat-square&logo=docker&logoColor=white)](docker-compose.yml)

**Drag-and-drop AI Agent workflows · No code required · Live in 5 minutes**

An open-source zero-code AI Agent platform: drag-and-drop workflow editor + multi-model support + knowledge-base RAG + one-command deploy.

[Live demo](#-live-demo) · [Quick start](#-quick-start) · [Features](#-features) · [Docs](#-docs) · [FAQ](docs/FAQ.md)

[English](README.en.md) · [中文](README.md)

</div>

---

## 📽️ Live demo

> Real screen recordings (captured by a headless browser, unedited). Full videos live in `assets/videos/`.

<h3 align="center">① One sentence to a PPT — end-to-end delivery</h3>

Describe what you need in the chat box. The Agent reads its own workspace, writes code, runs scripts, and hands the result back as a **downloadable attachment**.

<img src="assets/gifs/demo-ppt-generation.gif" alt="Chat to PPT" width="900">

<p align="center">
  <a href="assets/videos/demo-ppt-generation.mp4">▶ Full conversation (51s)</a> &nbsp;·&nbsp;
  <a href="assets/videos/demo-ppt-result-preview.mp4">▶ Page-by-page preview (20s)</a>
</p>

<h3 align="center">② Building a workflow by dragging nodes</h3>

Pick nodes from the left panel onto the canvas, edit parameters on the right, save and it takes effect immediately — no code at any point.

<img src="assets/gifs/demo-workflow-build.gif" alt="Workflow builder" width="900">

<p align="center"><a href="assets/videos/demo-workflow-build.mp4">▶ Full recording (12s)</a></p>

<h3 align="center">③ Tool calls inside a conversation</h3>

While the Agent runs, a live "calling tool" line appears; only the current one stays on screen, and it hides itself as soon as the reply is done.

<img src="assets/gifs/demo-chat-tool-calls.gif" alt="Tool calls in chat" width="900">

<p align="center"><a href="assets/videos/demo-chat-tool-calls.mp4">▶ Full recording (8s)</a></p>

<h3 align="center">④ Knowledge base: upload and semantic search</h3>

Upload a document → automatic chunking and indexing → recall by relevance when you ask a question. Matched snippets are highlighted right in the UI.

<img src="assets/gifs/demo-knowledge-rag.gif" alt="Knowledge base RAG" width="900">

<p align="center"><a href="assets/videos/demo-knowledge-rag.mp4">▶ Full recording (26s)</a></p>

---

## 🖼️ Screenshots

<img src="assets/screens/05-workflow.png" alt="Workflow editor">

**Workflow editor** — three-column layout of node panel / drag-and-drop canvas / node configuration, node and connection counts in the top bar, with test, undo/redo, import and export.

<table>
<tr>
<td width="50%"><img src="assets/screens/01-landing.png" alt="Landing page"><br><sub><b>Landing page</b> — the no-code value proposition</sub></td>
<td width="50%"><img src="assets/screens/04-agent-create.png" alt="Agent setup"><br><sub><b>Agent setup</b> — model, prompt, knowledge, skills</sub></td>
</tr>
<tr>
<td width="50%"><img src="assets/screens/06-chat.png" alt="Chat"><br><sub><b>Chat</b> — streaming replies + downloadable artifacts</sub></td>
<td width="50%"><img src="assets/screens/07-conversations.png" alt="Conversations"><br><sub><b>Conversations</b> — pick any past session and keep talking</sub></td>
</tr>
<tr>
<td width="50%"><img src="assets/screens/09-skills.png" alt="Skill plaza"><br><sub><b>Skill plaza</b> — Excel / PDF / PPT and other built-in skills</sub></td>
<td width="50%"><img src="assets/screens/10-knowledge.png" alt="Knowledge base"><br><sub><b>Knowledge base</b> — upload, chunk, semantic search</sub></td>
</tr>
</table>

---

## ✨ Features

- **🎨 Drag-and-drop workflow editor** — ReactFlow canvas, with LLM / condition / tool / knowledge / agent / response nodes to combine freely
- **🤖 Multi-model support** — OpenAI · Claude · DeepSeek · Ollama, keys entered straight in the UI, **hot-swap without restart**
- **📚 Knowledge-base RAG** — documents chunked automatically on upload, pgvector vector search, results with relevance scores
- **🧩 Skill plaza** — 8 built-in skills (Excel / PDF / PPT / meeting notes / statistics …), ready to use out of the box
- **📎 Artifact delivery** — files generated by an Agent come back as downloadable attachments, and past conversations can be revisited
- **🌐 Browser automation** — built-in Browser-Use engine, the AI drives the browser itself to get things done
- **👤 User system** — JWT auth, data fully self-hosted, never passes through a third party

**Who it's for**: companies that want an AI customer-service or sales assistant but have no dev team; product managers who need to validate an Agent scenario fast; developers who want to orchestrate LLM workflows with low code.

---

## 🚀 Quick start

### Requirements

| Dependency | Version |
|:--|:--|
| Python | 3.11+ |
| Node.js | 18+ |
| PostgreSQL | 14+ (needs the pgvector extension) |
| Redis | 7+ |
| Docker (recommended) | 20+ |

### Docker (recommended)

```bash
git clone https://github.com/PHclaw/agentflow.git
cd agentflow
cp .env.example .env      # JWT_SECRET_KEY plus at least one model API key is required
docker compose up --build
```

Frontend http://localhost:3000 · Backend http://localhost:8001

### Local development

```bash
# backend
cd backend && python -m venv venv
.\venv\Scripts\Activate.ps1          # macOS / Linux: source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# frontend (in another terminal)
cd frontend && npm install && npm run dev
```

Just want the backend running, without PostgreSQL and Redis? Use the SQLite lite mode:

```powershell
.\scripts\dev-backend.ps1
```

> For environment variables, model configuration and the SQLite lite mode, see the **[configuration guide](docs/CONFIGURATION.md)**.

---

## 🏗️ Architecture

```
  React 18 + ReactFlow  ──►  FastAPI  ──►  PostgreSQL + pgvector
      frontend :3000        backend :8001     Redis · Celery Worker
```

| Layer | Tech |
|:--|:--|
| Frontend | React 18 · TypeScript 5 · Vite 5 · ReactFlow · Tailwind CSS · Zustand |
| Backend | Python 3.11 · FastAPI · SQLAlchemy 2.0 · Alembic · Celery |
| Storage | PostgreSQL 14 + pgvector · Redis 7 |
| Models | OpenAI · Anthropic · DeepSeek · Ollama (OpenAI-compatible) |

The full picture — system architecture, workflow node types, project layout — is in the **[architecture guide](docs/ARCHITECTURE.md)**.

---

## ⚖️ How it differs from Dify / Coze

- **Fully open source, data stays yours** — MIT licensed, every byte lives in your own PostgreSQL, nothing goes through a third party
- **Built-in browser automation** — a capability Dify / Coze don't have; the AI drives the browser itself to get things done
- **Self-hosting first** — one command with Docker, SQLite lite mode for a single machine, plus deep integration with 9 agent-* libraries

The full comparison lives in **[How it differs from Dify / Coze](docs/COMPARISON.md)**.

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
## ⚠️ Note

The version uploaded here is not the latest one. To get the latest version, contact the author: 2730545346@qq.com
## 🤝 Contributing

Issue → Fork → Branch → Develop → Test → PR → Review → Merge

## 📄 License

MIT © 2025 [PHclaw](https://github.com/PHclaw)

---

<div align="center">

**Find it useful? Leave a ⭐**

[⭐ Star](https://github.com/PHclaw/agentflow) · [🍴 Fork](https://github.com/PHclaw/agentflow/fork) · [🐛 Issues](https://github.com/PHclaw/agentflow/issues)

</div>