"""
CodebaseIndexer: loads code files, splits them into chunks,
embeds them with a local sentence-transformers model (no Ollama needed),
and stores everything in ChromaDB.

Embedding model: all-MiniLM-L6-v2
  - Downloads once (~90 MB) from HuggingFace on first run
  - Runs entirely on CPU, no GPU required
  - Fast and accurate for code retrieval
"""

import os
import shutil
import asyncio
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter, Language
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# ── Language-aware chunking map ───────────────────────────────────────────────
LANGUAGE_MAP = {
    ".py":   Language.PYTHON,
    ".js":   Language.JS,
    ".ts":   Language.JS,
    ".jsx":  Language.JS,
    ".tsx":  Language.JS,
    ".go":   Language.GO,
    ".java": Language.JAVA,
    ".cpp":  Language.CPP,
    ".c":    Language.CPP,
    ".rs":   Language.RUST,
    ".rb":   Language.RUBY,
    ".md":   Language.MARKDOWN,
    ".html": Language.HTML,
}

TEXT_EXTENSIONS = {".txt", ".json", ".yaml", ".yml", ".env.example", ".sh", ".sql", ".css", ".scss"}
IGNORE_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".next", "vendor"}

FAISS_PATH = "./faiss_index"

# Embedding model — downloaded once from HuggingFace Hub, then cached locally
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass
class IndexStatus:
    indexed: bool = False
    project_name: Optional[str] = None
    file_count: int = 0
    chunk_count: int = 0


class CodebaseIndexer:
    def __init__(self):
        self._status = IndexStatus()
        self._vectorstore: Optional[Chroma] = None
        # Loads the model on first init (~90 MB download, then cached)
        print("[indexer] Loading embedding model (first run may download ~90 MB)...")
        self._embeddings = HuggingFaceEmbeddings(
            model_name=EMBED_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        print("[indexer] Embedding model ready.")

    def is_indexed(self) -> bool:
        return self._status.indexed

    def get_status(self) -> dict:
        return {
            "indexed": self._status.indexed,
            "project_name": self._status.project_name,
            "file_count": self._status.file_count,
            "chunk_count": self._status.chunk_count,
        }

    def get_vectorstore(self) -> Optional[FAISS]:
        return self._vectorstore

    async def index(self, path: str, github_token: Optional[str] = None) -> dict:
        """Index a local directory or GitHub repo into ChromaDB."""
        if path.startswith("https://github.com") or path.startswith("git@github.com"):
            local_path = await self._clone_repo(path, github_token)
        else:
            local_path = Path(path)
            if not local_path.exists():
                raise ValueError(f"Path does not exist: {path}")

        project_name = local_path.name
        docs = self._load_documents(local_path)

        if not docs:
            raise ValueError("No supported code files found in the project.")

        chunks = self._split_documents(docs)

        # Rebuild the vector store from scratch
        if os.path.exists(FAISS_PATH):
            shutil.rmtree(FAISS_PATH)

        self._vectorstore = FAISS.from_documents(
            documents=chunks,
            embedding=self._embeddings,
        )
        self._vectorstore.save_local(FAISS_PATH)

        self._status = IndexStatus(
            indexed=True,
            project_name=project_name,
            file_count=len(set(d.metadata.get("source", "") for d in docs)),
            chunk_count=len(chunks),
        )

        return {
            "message": f"Successfully indexed '{project_name}'",
            "project_name": project_name,
            "file_count": self._status.file_count,
            "chunk_count": self._status.chunk_count,
        }

    def _load_documents(self, base_path: Path) -> list:
        docs = []
        for fpath in base_path.rglob("*"):
            if any(part in IGNORE_DIRS for part in fpath.parts):
                continue
            if not fpath.is_file():
                continue
            suffix = fpath.suffix.lower()
            if suffix not in LANGUAGE_MAP and suffix not in TEXT_EXTENSIONS:
                continue
            try:
                loader = TextLoader(str(fpath), encoding="utf-8")
                file_docs = loader.load()
                for doc in file_docs:
                    doc.metadata["language"] = suffix.lstrip(".")
                    doc.metadata["filename"] = fpath.name
                docs.extend(file_docs)
            except Exception:
                pass
        return docs

    def _split_documents(self, docs: list) -> list:
        chunks = []
        for doc in docs:
            suffix = "." + doc.metadata.get("language", "txt")
            lang = LANGUAGE_MAP.get(suffix)
            if lang:
                splitter = RecursiveCharacterTextSplitter.from_language(
                    language=lang, chunk_size=1500, chunk_overlap=200
                )
            else:
                splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
            chunks.extend(splitter.split_documents([doc]))
        return chunks

    async def _clone_repo(self, url: str, token: Optional[str]) -> Path:
        import tempfile
        tmp = tempfile.mkdtemp()
        if token:
            url = url.replace("https://", f"https://{token}@")
        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth=1", url, tmp,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"git clone failed: {stderr.decode()}")
        return Path(tmp)

    def clear(self):
        if os.path.exists(FAISS_PATH):
            shutil.rmtree(FAISS_PATH)
        self._vectorstore = None
        self._status = IndexStatus()