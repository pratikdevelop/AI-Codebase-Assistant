# 🧠 CodeMind — AI Personal Codebase Assistant

<div align="center">

![CodeMind Banner](https://img.shields.io/badge/CodeMind-AI%20Codebase%20Assistant-00d8a0?style=for-the-badge&logo=openai&logoColor=white)

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-0.2.6-1C3C3C?style=flat-square&logo=chainlink&logoColor=white)](https://langchain.com)
[![Docker](https://img.shields.io/badge/Docker%20Model%20Runner-Required-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docs.docker.com/desktop/features/model-runner/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

**Ask questions about your codebase in plain English. Edit files. Generate entire new projects. All running 100% locally — no API keys, no data leaves your machine.**

[Features](#-features) • [Quick Start](#-quick-start) • [Architecture](#-architecture) • [Usage](#-usage) • [Tech Stack](#-tech-stack) • [Contributing](#-contributing)

</div>

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Codebase Q&A** | Ask anything — *"Where is auth handled?"*, *"Find all SQL queries"* |
| 📁 **File Explorer** | Browse, open, edit, create and delete files in-browser |
| ✏️ **Built-in Editor** | Tab support, Ctrl+S to save, unsaved-changes indicator |
| 🤖 **AI Code Apply** | One-click to apply AI-suggested code directly into the editor |
| ✨ **Project Generator** | Scaffold a complete new project in any language from a description |
| 🐙 **GitHub Support** | Index any public GitHub repo by pasting the URL |
| 🔒 **100% Local** | Powered by Docker Model Runner — no cloud, no API keys |
| 💬 **Multi-turn Chat** | Follows conversation context across follow-up questions |

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | 4.40+ | Required for `docker model` command |
| [Python](https://python.org) | 3.11+ | For the backend |

### 1. Pull the AI model

```bash
docker model pull ai/llama3.2
```

> This downloads ~2 GB once and caches it locally. No account needed.

### 2. Start the model

```bash
docker model run ai/llama3.2
```

The model is now available at `http://localhost:12434/engines/llama.cpp/v1` (OpenAI-compatible API).

### 3. Install backend dependencies

```bash
pip install -r requirements.txt
```

> **Windows users:** If you hit a `chroma-hnswlib` build error, that's expected — we use FAISS instead which has prebuilt Windows wheels. `requirements.txt` already handles this.

### 4. Start the backend

```bash
python main.py
```

Backend runs at `http://localhost:8000`. Visit `http://localhost:8000/docs` for the interactive API docs.

### 5. Open the UI

```bash
cd frontend
python -m http.server 3000
```

Open **http://localhost:3000** in your browser.

---

## 🎯 Usage

### Index an existing project

1. Paste a local path (e.g. `C:/Users/you/projects/my-app`) or a GitHub URL into the sidebar
2. Click **Index Codebase** — files are chunked, embedded, and stored in a local FAISS vector index
3. Start asking questions in the chat

### Ask questions

```
"Where is user authentication handled?"
"Find all SQL queries in this project"
"What API routes are defined?"
"Explain the main entry point"
"What environment variables does this project need?"
"Summarize the overall architecture"
```

### Edit files

- Click any file in the **Explorer** panel to open it in the editor
- Edit directly — **Tab** inserts spaces, **Ctrl+S** saves to disk
- Use **"Ask AI"** to send the current file to the chat for review
- Use **"Apply to Editor"** on any AI code block to insert it at your cursor

### Generate a new project

1. Click **✨ Generate New Project** in the header
2. Choose a template or describe your project:
   ```
   A REST API for a blog with posts, comments, JWT auth, PostgreSQL, and Docker
   ```
3. Set an output directory and click Generate
4. Watch files get created live — the project is auto-indexed when done

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser UI                               │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ File Explorer│  │  Chat Panel  │  │    Code Editor        │ │
│  │ (tree view)  │  │ (Q&A + RAG)  │  │  (edit + save files)  │ │
│  └──────────────┘  └──────────────┘  └───────────────────────┘ │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP / REST
┌─────────────────────────▼───────────────────────────────────────┐
│                    FastAPI Backend                               │
│                                                                 │
│  /index  ──► CodebaseIndexer                                    │
│               ├── File walker (language-aware chunking)         │
│               ├── HuggingFace Embeddings (all-MiniLM-L6-v2)    │
│               └── FAISS vector store (local, no C++ needed)    │
│                                                                 │
│  /query  ──► CodebaseAssistant                                  │
│               ├── Relevance score gate (blocks hallucination)   │
│               ├── LangChain ConversationalRetrievalChain        │
│               └── Docker Model Runner (OpenAI-compatible API)   │
│                                                                 │
│  /files/* ──► FileManager (sandboxed read/write/delete)         │
│                                                                 │
│  /generate ──► ProjectGenerator                                 │
│               ├── Phase 1: Plan (file manifest, ~400 tokens)    │
│               └── Phase 2: Generate each file individually      │
└─────────────────────────┬───────────────────────────────────────┘
                          │ OpenAI-compatible REST
┌─────────────────────────▼───────────────────────────────────────┐
│            Docker Model Runner (local)                          │
│            http://localhost:12434/engines/llama.cpp/v1          │
│            Model: ai/llama3.2 (or any model you pull)           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
AI-Codebase-Assistant/
├── main.py                 # FastAPI server & all routes
├── assistant.py            # LangChain RAG chain (Docker Model Runner LLM)
├── indexer.py              # File loading, chunking, FAISS embedding
├── file_manager.py         # Sandboxed file read/write/delete/rename
├── project_generator.py    # Two-phase AI project scaffolding
├── requirements.txt        # Python dependencies
├── frontend/
│   └── index.html          # Single-file UI (no build step needed)
└── faiss_index/            # Auto-created on first index (gitignored)
```

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **LLM** | Docker Model Runner + `ai/llama3.2` | Local, private, no API key |
| **LLM Client** | `langchain-openai` (OpenAI-compatible) | Swap models without code changes |
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` | Fast CPU embeddings, ~90MB, no service needed |
| **Vector Store** | FAISS | Prebuilt Windows/Mac/Linux wheels, no C++ compiler |
| **RAG Framework** | LangChain `ConversationalRetrievalChain` | Multi-turn chat with context |
| **Backend** | FastAPI + uvicorn | Async, fast, auto-generates `/docs` |
| **Frontend** | Vanilla HTML/CSS/JS | Zero build step, single file |

---

## ⚙️ Configuration

Set environment variables before running `python main.py`:

| Variable | Default | Description |
|---|---|---|
| `DOCKER_MODEL_BASE_URL` | `http://localhost:12434/engines/llama.cpp/v1` | Docker Model Runner endpoint |
| `DOCKER_MODEL_NAME` | `ai/llama3.2` | Model to use for chat + generation |

### Swap to a different model

```bash
docker model pull ai/mistral        # 32K context — better for large files
docker model pull ai/phi4           # 16K context — fast and capable
docker model pull ai/gemma3         # Google's model

DOCKER_MODEL_NAME=ai/mistral python main.py
```

---

## 🔌 API Reference

| Method | Route | Description |
|---|---|---|
| `GET` | `/status` | Index status (indexed, file count, chunk count) |
| `POST` | `/index` | Index a local path or GitHub URL |
| `DELETE` | `/index` | Clear the current index |
| `POST` | `/query` | Ask a question about the codebase |
| `GET` | `/files/tree` | Get full file tree of indexed project |
| `GET` | `/files/read?path=` | Read a file's content |
| `POST` | `/files/write` | Write/create a file |
| `DELETE` | `/files/delete?path=` | Delete a file |
| `POST` | `/files/rename` | Rename/move a file |
| `POST` | `/generate` | Generate a new project (streaming NDJSON) |

Full interactive docs at **http://localhost:8000/docs**

---

## 🧩 How RAG Works

1. **Indexing** — Your project files are loaded, split using language-aware chunkers (separate strategies for Python, JS, Go, Java, etc.), embedded with `all-MiniLM-L6-v2`, and stored in a local FAISS index.

2. **Retrieval** — When you ask a question, it's embedded and compared against all chunks using L2 similarity. The top 8 most relevant chunks are retrieved. If the best match score is too high (semantically unrelated), a "not found" response is returned before even calling the LLM — preventing hallucination.

3. **Generation** — The retrieved chunks are injected into a strict system prompt that prohibits the LLM from guessing or inventing code not present in the context. The LLM synthesizes an answer citing actual file names.

4. **Memory** — Chat history is maintained across turns, so follow-up questions like *"and where is that called?"* work correctly.

---

## 🪟 Windows Notes

- Use `python` not `python3` in PowerShell
- Use full paths with forward slashes or escaped backslashes: `C:/Users/you/project` or `C:\\Users\\you\\project`
- `faiss-cpu` is used instead of ChromaDB — no Microsoft Visual C++ Build Tools needed
- The embedding model (`all-MiniLM-L6-v2`) downloads ~90MB on first run to `~/.cache/huggingface`

---

## 🤝 Contributing

Contributions are welcome! Here are some ideas:

- [ ] Syntax highlighting in the editor (CodeMirror / Monaco)
- [ ] Re-index on file save (hot reload vector store)
- [ ] Support for more models (Mistral, CodeLlama, DeepSeek Coder)
- [ ] Dark/light theme toggle
- [ ] Export chat as markdown
- [ ] Multi-project support (switch between indexed projects)
- [ ] VS Code extension

```bash
# Fork the repo, then:
git clone https://github.com/your-username/AI-Codebase-Assistant
cd AI-Codebase-Assistant
pip install -r requirements.txt
python main.py
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built with ❤️ by [pratikdevelop](https://github.com/pratikdevelop)

⭐ Star this repo if you found it useful!

</div>
