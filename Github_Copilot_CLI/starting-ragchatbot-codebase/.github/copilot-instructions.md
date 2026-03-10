# Copilot Instructions

## Build, Run, and Test
- **Install dependencies**: Run `uv sync` from the repo root (Python ≥ 3.13). Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`; `backend/config.py` loads it via `python-dotenv` at import time, so restart the server after editing secrets.
- **Backend dev server**: `cd backend && uv run uvicorn app:app --reload --port 8000`. Launching from `backend/` is critical because `app.py` resolves `../docs` for ingestion and `./chroma_db` for Chroma persistence relative to the current working directory.
- **Quick-start script**: From the root run `./run.sh` (use Git Bash on Windows). It ensures `docs/` exists, `cd`s into `backend/`, and starts uvicorn with `uv run`.
- **Rebuilding embeddings**: Add `.txt/.docx/.pdf` files under `docs/` before boot or open a REPL (`cd backend && uv run python`) and call `rag_system.add_course_folder("../docs", clear_existing=True)`; deleting `backend/chroma_db` or invoking `VectorStore.clear_all_data()` also forces a clean slate.
- **Testing (pytest template)**: Tests aren’t included yet, but once `pytest` is added to `pyproject.toml`, run `uv run pytest` for the suite or `uv run pytest tests/test_file.py -k test_case` for an individual test.

## Architecture Overview

### Backend service
- `backend/app.py` builds the FastAPI app, layers TrustedHost + permissive CORS, mounts `frontend/` via `StaticFiles`, and exposes `POST /api/query` plus `GET /api/courses` (Pydantic models define the payloads).
- A startup hook looks for `../docs` and invokes `rag_system.add_course_folder`, so course ingestion happens automatically whenever the server boots from inside `backend/`.
- The backend lives in the root `pyproject.toml` and should always be run through `uv run` so dependencies resolve via `uv.lock`.

### RAG pipeline
- `RAGSystem` composes five collaborators: `DocumentProcessor`, `VectorStore`, `AIGenerator`, `SessionManager`, and a `ToolManager` that currently registers a single `CourseSearchTool`.
- `DocumentProcessor` assumes every source file begins with `Course Title`, `Course Link`, and `Course Instructor` lines followed by `Lesson N:` blocks (optional `Lesson Link` on the next line). It chunkifies lesson text (size 800, overlap 100 from `config`) and prefixes chunks with lesson context so retrieval snippets are self-contained.
- `VectorStore` manages two ChromaDB collections backed by a SentenceTransformer embedding (`all-MiniLM-L6-v2`): `course_catalog` stores metadata (title, instructor, serialized lesson list) and `course_content` stores chunk payloads. Course titles double as IDs, so re-ingesting identical titles is treated as a duplicate unless you clear the store.
- `CourseSearchTool` resolves fuzzy course names through the catalog, applies optional `lesson_number` filters, formats results as `[Course - Lesson]` passages, and captures a simple `sources` list that `rag_system.query` returns to the UI before `tool_manager.reset_sources()` clears it.
- `AIGenerator` wraps Anthropic Claude (`claude-sonnet-4-20250514`) with a strict system prompt that enforces “one search per query”. When Anthropic requests `tool_use`, it delegates to `ToolManager.execute_tool`, appends the tool results as a user message, then issues a follow-up call (without `tools`) to produce the final answer.
- `SessionManager` issues sequential IDs (`session_#`) and stores up to `MAX_HISTORY` exchanges (default 2) per session in memory; everything is lost on restart, so long-term context must be re-hydrated externally if needed.

### Frontend
- `frontend/index.html` / `style.css` / `script.js` are static assets (no bundler) served by FastAPI. The page imports the `marked` CDN to render Markdown answers, wires click/keypress listeners, POSTs to `/api/query` (passing any cached `session_id`), and GETs `/api/courses` to populate the sidebar.
- Source display relies on the backend returning a `sources` array, so backend changes should keep the `CourseSearchTool` output aligned with the `<details>` UI.

## Key Conventions
- Use `uv` for installs, scripts, and REPLs so you stay within the locked environment; mixing in `pip`/system Python can desync `uv.lock`.
- Always start uvicorn from `backend/` (or via `run.sh`, which `cd`s for you) to keep the relative `../docs` and `./chroma_db` paths valid.
- Centralized settings live in `backend/config.py` (API key, Claude model, embedding model, chunk size/overlap, max history, Chroma path). Update values there rather than scattering new constants.
- Course documents must live in `docs/` and use the expected header/lesson structure; only `.txt/.docx/.pdf` files are processed, and lesson headers (`Lesson N:` plus optional `Lesson Link:`) drive chunk labeling.
- Because course titles are treated as unique IDs in Chroma, renaming a course requires clearing the collections (e.g., delete `backend/chroma_db` or call `VectorStore.clear_all_data()`) before re-ingesting to avoid duplicates or stale metadata.
- Frontend UX depends on concise Markdown answers and short `sources` labels; keep backend responses tight and continue returning the source list so the collapsible UI stays meaningful.
- Any new tools must implement `Tool.get_tool_definition()` + `execute()` and be registered with `ToolManager`. Manage per-tool state (like `last_sources`) and reset it inside `rag_system.query` to prevent leaking context across requests.
- Sessions are ephemeral and capped by `config.MAX_HISTORY`; features that rely on prior turns should tolerate histories being trimmed or reset on process restart.
