# Implementation checkpoint

## Scope

Build a basic Next.js + FastAPI MVC NotebookAI clone, single admin user, notebooks with multiple typed sources, PostgreSQL 18 in Docker, host-run apps, tests, Mermaid entity design, module documentation, and PR CI.

## Implemented

- Canonical `frontend/` and `backend/` packages.
- Notebook library and responsive source/chat/reader workspace.
- Notebook CRUD, typed source ingestion, source selection and source reader.
- PDF/text extraction, image/scanned-PDF manual transcription.
- Credential-free cited passage retrieval and persisted question history.
- SQLAlchemy entities and Alembic initial migration with admin seed.
- PostgreSQL 18 Compose setup (port 5433, persistent named volume).
- Backend API tests, frontend component/client tests, desktop/mobile end-to-end tests.
- Pull-request workflow, ER diagram, frontend/backend/setup docs.

## Validation

Validation is in progress. Update this section with actual results before handoff.

## Deliberate follow-ups

- Screenshot references received and applied to the notebook library and workspace styling. Full Studio tools remain outside this MVP.
- No AI provider was specified. Current answers are explicitly labeled local cited passages. Add a real provider, semantic retrieval, and OCR as a separate extension.
- Authentication, reports/quizzes, URL/PPTX ingestion, and cloud deployment are outside this basic milestone.

## Resuming work

Continue from the current files and this checkpoint. Inspect `git status`, read any new user instructions, and run only the checks needed for further changes. Completed code does not need to be regenerated. Saved progress does not guarantee an interrupted process automatically restarts after a usage reset; resume this chat to continue.

## RAG milestone (supersedes earlier AI roadmap status)

Implemented `ai/` package with PDF/PPTX/TXT/URL extraction, local FastEmbed, persistent Qdrant, scoped hybrid BM25/dense retrieval, RRF and diversity selection, and Groq structured grounded answers (`openai/gpt-oss-20b`). Added upload-time ingestion, full PostgreSQL rebuild and individual retry endpoints, indexing migration and UI states. See `vector-indexing.md` for setup and limitations. AI/backend tests and CI require no provider credentials. Live Groq generation needs the user's key. Background jobs, OCR, conversational context and large-scale retrieval remain future work.
