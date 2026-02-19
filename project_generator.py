"""
ProjectGenerator: generates a complete project in two phases.

Phase 1 — Plan: ask LLM for a file list (small JSON, never truncated)
Phase 2 — Generate: ask LLM to write each file individually

This avoids the "unterminated JSON" error caused by hitting max_tokens
when trying to generate all files in a single response.
"""

import os
import json
import re
from pathlib import Path
from openai import AsyncOpenAI

DOCKER_MODEL_BASE_URL = os.getenv(
    "DOCKER_MODEL_BASE_URL",
    "http://localhost:12434/engines/llama.cpp/v1",
)
DOCKER_MODEL_NAME = os.getenv("DOCKER_MODEL_NAME", "ai/llama3.2")

# ── Phase 1: get file plan ────────────────────────────────────────────────────
PLAN_SYSTEM = """You are a software architect. Given a project description,
return ONLY a JSON object listing the files to create. No explanation, no markdown.

Schema:
{
  "project_name": "snake_case_name",
  "description": "one sentence",
  "tech_stack": "comma separated stack",
  "files": [
    { "path": "relative/path/file.ext", "purpose": "what this file does" }
  ]
}

Rules:
- project_name must be snake_case, no spaces
- 5 to 20 files maximum
- paths use forward slashes, no leading slash
- Include: main source files, config, package/dependency file, Dockerfile, .gitignore, README.md
"""

# ── Phase 2: generate individual file ────────────────────────────────────────
FILE_SYSTEM = """You are an expert developer. Write the COMPLETE content for a single source file.
Return ONLY the raw file content — no markdown fences, no explanation, no commentary.
The output will be written directly to disk exactly as you return it.
Write real, working, production-quality code. Do not use placeholder comments like 'add code here'.
"""


def _clean_json(raw: str) -> str:
    """Strip markdown fences and find the JSON object."""
    raw = raw.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    # Find first { to last }
    start = raw.find('{')
    end = raw.rfind('}')
    if start != -1 and end != -1:
        raw = raw[start:end+1]
    return raw.strip()


class ProjectGenerator:
    def __init__(self):
        self._client = AsyncOpenAI(
            base_url=DOCKER_MODEL_BASE_URL,
            api_key="docker-model-runner",
        )

    async def _chat(self, system: str, user: str, max_tokens: int = 2048) -> str:
        resp = await self._client.chat.completions.create(
            model=DOCKER_MODEL_NAME,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            temperature=0.2,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()

    async def generate(self, description: str, output_dir: str):
        """
        Two-phase generation:
        1. Get a file plan (small JSON)
        2. Generate each file individually (never truncated)
        """
        output_path = Path(output_dir)

        # ── Phase 1: Plan ─────────────────────────────────────────────────────
        yield {"type": "status", "message": "Planning project structure..."}

        plan_raw = await self._chat(
            PLAN_SYSTEM,
            f"Project: {description}",
            max_tokens=1024,
        )

        try:
            plan = json.loads(_clean_json(plan_raw))
        except json.JSONDecodeError as e:
            raise ValueError(f"Could not parse project plan: {e}\nRaw: {plan_raw[:300]}")

        if "files" not in plan or not plan["files"]:
            raise ValueError("LLM returned no files in the project plan.")

        project_name = re.sub(r'[^\w\-]', '-', plan.get("project_name", "new-project")).strip('-')
        project_dir  = (output_path / project_name).resolve()
        project_dir.mkdir(parents=True, exist_ok=True)

        files_list = plan["files"]
        total = len(files_list)

        yield {"type": "plan", "project_name": project_name,
               "description": plan.get("description", description),
               "tech_stack": plan.get("tech_stack", ""),
               "total_files": total,
               "project_path": str(project_dir)}

        # ── Phase 2: Generate each file ───────────────────────────────────────
        written = []
        for i, f in enumerate(files_list):
            rel_path = f.get("path", "").lstrip("/").lstrip("\\")
            purpose  = f.get("purpose", "")
            if not rel_path:
                continue

            yield {"type": "generating", "file": rel_path, "index": i+1, "total": total}

            try:
                content = await self._chat(
                    FILE_SYSTEM,
                    f"""Project: {description}
Tech stack: {plan.get('tech_stack', '')}
Project name: {project_name}

Write the complete content for this file:
Path: {rel_path}
Purpose: {purpose}

All other files in this project:
{chr(10).join(x['path'] for x in files_list)}
""",
                    max_tokens=2048,
                )

                # Write to disk
                full_path = (project_dir / rel_path).resolve()
                if not str(full_path).startswith(str(project_dir)):
                    continue  # block traversal
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding="utf-8")
                written.append(rel_path)
                yield {"type": "file_done", "file": rel_path}

            except Exception as e:
                yield {"type": "file_error", "file": rel_path, "error": str(e)}

        yield {
            "type": "done",
            "project_name": project_name,
            "project_path": str(project_dir),
            "description": plan.get("description", description),
            "files_created": written,
            "file_count": len(written),
        }