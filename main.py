"""
AI Personal Codebase Assistant — main.py
"""

import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from indexer import CodebaseIndexer
from assistant import CodebaseAssistant
from file_manager import FileManager
from project_generator import ProjectGenerator

app = FastAPI(title="AI Codebase Assistant", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

indexer   = CodebaseIndexer()
assistant = CodebaseAssistant(indexer)
fm        = FileManager()
generator = ProjectGenerator()


# ── Models ────────────────────────────────────────────────────────────────────

class IndexRequest(BaseModel):
    path: str
    github_token: Optional[str] = None

class QueryRequest(BaseModel):
    question: str
    chat_history: Optional[list] = []

class WriteRequest(BaseModel):
    path: str
    content: str

class RenameRequest(BaseModel):
    old_path: str
    new_path: str

class GenerateRequest(BaseModel):
    description: str
    output_dir: str


# ── Core ──────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "AI Codebase Assistant API v2"}

@app.get("/status")
def get_status():
    return indexer.get_status()

@app.post("/index")
async def index_codebase(req: IndexRequest):
    try:
        result = await indexer.index(req.path, req.github_token)
        fm.set_root(req.path)
        assistant.reset_chain()   # ← rebuild chain on new index
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query")
async def query_codebase(req: QueryRequest):
    if not indexer.is_indexed():
        raise HTTPException(status_code=400, detail="No codebase indexed yet.")
    try:
        return await assistant.query(req.question, req.chat_history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/index")
def clear_index():
    indexer.clear()       # wipes FAISS store from disk + memory
    fm.clear_root()       # forgets the project path
    assistant.reset_chain()  # drops the LangChain chain so it rebuilds next time
    return {"message": "Index cleared", "indexed": False}


# ── File Manager ──────────────────────────────────────────────────────────────

@app.get("/files/tree")
def get_tree():
    try:
        return fm.list_tree()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/files/read")
def read_file(path: str):
    try:
        return fm.read_file(path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/files/write")
def write_file(req: WriteRequest):
    try:
        return fm.write_file(req.path, req.content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/files/delete")
def delete_file(path: str):
    try:
        return fm.delete_file(path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/files/rename")
def rename_file(req: RenameRequest):
    try:
        return fm.rename_file(req.old_path, req.new_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Project Generator ─────────────────────────────────────────────────────────

from fastapi.responses import StreamingResponse as FastAPIStreaming
import json as _json

@app.post("/generate")
async def generate_project(req: GenerateRequest):
    """Stream project generation events as NDJSON (one JSON object per line)."""
    async def stream():
        final = None
        try:
            async for event in generator.generate(req.description, req.output_dir):
                yield _json.dumps(event) + "\n"
                if event.get("type") == "done":
                    final = event
        except Exception as e:
            yield _json.dumps({"type": "error", "message": str(e)}) + "\n"
            return

        if final:
            try:
                idx = await indexer.index(final["project_path"])
                fm.set_root(final["project_path"])
                assistant.reset_chain()
                yield _json.dumps({"type": "indexed",
                    "file_count": idx["file_count"],
                    "chunk_count": idx["chunk_count"]}) + "\n"
            except Exception as e:
                yield _json.dumps({"type": "index_error", "message": str(e)}) + "\n"

    return FastAPIStreaming(stream(), media_type="application/x-ndjson")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)