"""
CodebaseAssistant: wraps a ConversationalRetrievalChain over
the indexed Chroma vector store, powered by Docker Model Runner.

Docker Model Runner exposes an OpenAI-compatible REST API at:
  http://model-runner.docker.internal/engines/llama.cpp/v1  (inside container)
  http://localhost:12434/engines/llama.cpp/v1               (on host)

Setup (no Docker Compose, no Ollama needed):
  docker model pull ai/llama3.2
  python main.py
"""

import os
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import (
    PromptTemplate,
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

# ── Docker Model Runner config ────────────────────────────────────────────────
# Host mode (running backend directly on your machine):
DOCKER_MODEL_BASE_URL = os.getenv(
    "DOCKER_MODEL_BASE_URL",
    "http://localhost:12434/engines/llama.cpp/v1",
)
# Must match the model you pulled: docker model pull ai/llama3.2
DOCKER_MODEL_NAME = os.getenv("DOCKER_MODEL_NAME", "ai/llama3.2")

# ── Prompts ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a codebase analysis assistant. You answer questions STRICTLY based on the code snippets provided in the context below.

STRICT RULES — you must follow these without exception:
1. ONLY use information from the context snippets provided. Never invent, guess, or assume file names, folder structures, functions, or code that is not explicitly shown in the context.
2. If the context does not contain enough information to answer the question, respond EXACTLY with: "I could not find relevant information in the indexed codebase to answer this question. The actual files may not have been indexed, or this information may not exist in the project."
3. NEVER describe a "typical" or "common" project structure. Only describe what you can see in the actual code snippets.
4. NEVER say things like "this suggests", "it appears", "typically", "usually", or "this is a common pattern" — only state facts visible in the context.
5. Always cite the exact file name from the context when referencing code.

Context from indexed codebase (this is the ONLY source of truth):
{context}
"""

CONDENSE_PROMPT = PromptTemplate.from_template(
    """Given the following conversation and a follow up question,
rephrase the follow up question to be a standalone question that captures all necessary context.

Chat History:
{chat_history}

Follow Up Question: {question}

Standalone question:"""
)


class CodebaseAssistant:
    def __init__(self, indexer):
        self.indexer = indexer
        # ChatOpenAI works with any OpenAI-compatible endpoint.
        # Docker Model Runner speaks this protocol natively — no Ollama required.
        self._llm = ChatOpenAI(
            model=DOCKER_MODEL_NAME,
            base_url=DOCKER_MODEL_BASE_URL,
            api_key="docker-model-runner",  # required field but not validated
            temperature=0,
            streaming=False,
        )
        self._chain: Optional[ConversationalRetrievalChain] = None

    def _build_chain(self) -> ConversationalRetrievalChain:
        vs = self.indexer.get_vectorstore()
        retriever = vs.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 8},
        )

        qa_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT),
            HumanMessagePromptTemplate.from_template("{question}"),
        ])

        return ConversationalRetrievalChain.from_llm(
            llm=self._llm,
            retriever=retriever,
            condense_question_prompt=CONDENSE_PROMPT,
            combine_docs_chain_kwargs={"prompt": qa_prompt},
            return_source_documents=True,
            verbose=False,
        )

    async def query(self, question: str, chat_history: list = []) -> dict:
        """Run a question against the indexed codebase."""
        if self._chain is None:
            self._chain = self._build_chain()

        # Sanity-check: do a direct similarity search with scores first.
        # FAISS returns (doc, score) where lower L2 distance = more relevant.
        vs = self.indexer.get_vectorstore()
        scored = vs.similarity_search_with_score(question, k=4)

        # If the best match score is too high (far away), nothing relevant exists.
        # L2 distance > 1.5 means the query is semantically unrelated to all chunks.
        if scored and scored[0][1] > 1.5:
            return {
                "answer": "I could not find relevant information in the indexed codebase to answer this question. The actual files may not contain this information, or try re-indexing the project.",
                "sources": [],
            }

        # Convert [{role, content}] → [(human, ai)] tuples for LangChain
        lc_history = []
        for i in range(0, len(chat_history) - 1, 2):
            human = chat_history[i].get("content", "")
            ai = chat_history[i + 1].get("content", "") if i + 1 < len(chat_history) else ""
            lc_history.append((human, ai))

        result = await self._chain.acall({
            "question": question,
            "chat_history": lc_history,
        })

        sources = []
        seen = set()
        for doc in result.get("source_documents", []):
            src = doc.metadata.get("source", "unknown")
            fname = doc.metadata.get("filename", src)
            if src not in seen:
                seen.add(src)
                sources.append({
                    "file": fname,
                    "path": src,
                    "preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                })

        return {"answer": result["answer"], "sources": sources}

    def reset_chain(self):
        """Drop the cached chain so it rebuilds on next query."""
        self._chain = None