# Implementation checkpoint

## Scope

Build a basic Next.js + FastAPI MVC NotebookAI clone, single admin user, notebooks with multiple typed sources, PostgreSQL 18, host-run development and containerized deployment, tests, Mermaid entity design, module documentation, and PR CI.

## Implemented

- Canonical `frontend/` and `backend/` packages.
- Notebook library and responsive source/chat/reader workspace.
- Notebook CRUD, typed source ingestion, source selection and source reader.
- PDF/text extraction, image/scanned-PDF manual transcription.
- Credential-free cited passage retrieval and persisted question history.
- SQLAlchemy entities and Alembic initial migration with admin seed.
- PostgreSQL 18 Compose setup (port 5433, configurable persistent host directory).
- Backend API tests, frontend component/client tests, desktop/mobile end-to-end tests.
- Pull-request workflow, ER diagram, frontend/backend/setup docs.

## Validation

Previously completed application checks are recorded below. These are milestone results, not a claim that every subsequent workflow change has been deployed or tested against live AWS.

## Deliberate follow-ups

- Screenshot references received and applied to the notebook library and workspace styling. Full Studio tools remain outside this MVP.
- Groq generation, semantic retrieval, reports/quizzes and URL/PPTX ingestion are implemented.
- Authentication, OCR and durable background ingestion remain future work.
- GitHub Actions publishes ECR images and invokes the separately managed EC2 script through SSM; live rollout verification depends on the configured AWS environment.

## Resuming work

Continue from the current files and this checkpoint. Inspect `git status`, read any new user instructions, and run only the checks needed for further changes. Completed code does not need to be regenerated. Saved progress does not guarantee an interrupted process automatically restarts after a usage reset; resume this chat to continue.

## RAG milestone (supersedes earlier AI roadmap status)

Implemented `ai/` package with PDF/PPTX/TXT/URL extraction, local FastEmbed, persistent Qdrant, scoped hybrid BM25/dense retrieval, RRF and diversity selection, and Groq structured grounded answers (`openai/gpt-oss-20b`). Added upload-time ingestion, full PostgreSQL rebuild and individual retry endpoints, indexing migration and UI states. See `vector-indexing.md` for setup and limitations. AI/backend tests and CI require no provider credentials. Live Groq generation needs the user's key. Background jobs, OCR, conversational context and large-scale retrieval remain future work.

## Deployment, artifacts and retrieval comparison

Added container images and a same-origin deployment stack with PostgreSQL 18 and startup migrations. Implemented saved reports and short-answer quizzes with answer keys, citation validation, and Markdown/printable HTML downloads. Added `normal` hybrid retrieval versus Groq relevance reranking, selectable through the API/UI and saved in question history. See `deployment.md` and `artifacts-and-retrieval.md`.

Retrieval results now persist matched chunk counts, candidate/selected counts, retrieval duration and reranking duration, displayed in the UI. PostgreSQL uses `POSTGRES_DATA_PATH` for per-app bind mounts. Verified 49 backend/AI tests (including PostgreSQL), 11 frontend tests, two container-backed browser tests, image builds, deployment smoke and schema checks. Live Groq calls require a configured key and were not exercised in this verification.
