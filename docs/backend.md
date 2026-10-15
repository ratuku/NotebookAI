# Backend

## Layout and MVC

The FastAPI application is packaged as `notebook_backend` under `backend/src/`. Install the package before running it.

```text
src/notebook_backend/
  main.py                    App, CORS, health endpoint
  config.py                  Environment settings
  database.py                Engine, base class, request-scoped session
  models/entities.py         User, Notebook, Source, Question
  views/schemas.py            Pydantic input/output representations
  controllers/notebooks.py   HTTP actions, admin scope, transactions
  services/sources.py        AI package extraction adapter
  services/ingestion.py      Index publication, retry, deletion
  controllers/ingestion.py   Source retry and full rebuild endpoints
  services/answers.py        Scoped lexical retrieval and cited passages
migrations/                  Alembic schema history and admin seed
tests/                       API integration and validation tests
```

Controllers accept validated views, enforce notebook/source ownership, call services, and commit model changes. FastAPI serializes output through Pydantic response schemas. The single seeded admin is resolved server-side; clients cannot choose a user ID. This prepares an ownership boundary for future authentication, but is **not authentication**: every current caller is admin.

## Configuration

Copy `.env.example` to `.env` from the backend directory. Environment variables override this file.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://notebook:local_notebook_password@localhost:5433/notebook` | PostgreSQL connection |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | JSON array of permitted browser origins |
| `MAX_UPLOAD_BYTES` | `10485760` | Upload read limit (10 MB) |
| `TEST_DATABASE_URL` | unset | Optional PostgreSQL target for rollback-only tests |

The database schema is managed explicitly with `alembic upgrade head`; startup never creates tables implicitly. The migration seeds admin once; rerunning it does not duplicate users. `alembic check` detects differences between current model metadata and migrated schema. Use `alembic revision --autogenerate -m "description"` for subsequent changes, review the generated migration, then apply it. Never downgrade a database containing useful data just to rerun setup.

## API

All paths below start with `/api/v1/notebooks`. Open `/docs` on port 8000 for executable OpenAPI documentation.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/` (without trailing slash preferred) | List admin notebooks and source counts |
| POST | `/` | Create notebook from title and optional description |
| GET | `/{id}` | Fetch one notebook |
| PATCH | `/{id}` | Rename/update; accepts title and description |
| DELETE | `/{id}` | Delete notebook, sources, and question history |
| GET | `/{id}/sources` | List source metadata |
| POST | `/{id}/sources/text` | Create source from title and text |
| POST | `/{id}/sources/upload` | Multipart file upload, field `file` |
| GET | `/{id}/sources/{source_id}` | Text and location-preserving segments |
| PUT | `/{id}/sources/{source_id}/text` | Save manual transcription (title and text) |
| GET | `/{id}/sources/{source_id}/file` | Return original upload or pasted text |
| DELETE | `/{id}/sources/{source_id}` | Remove source; retain past citation snapshots |
| GET | `/{id}/questions` | Chronological question/answer history |
| POST | `/{id}/questions` | Ask using question and non-empty source_ids |

`GET /health` checks database connectivity. Missing resources return 404, invalid content 422, unsupported files 415, oversize uploads 413, and an uninitialized admin/database 503 where applicable. Database connection errors outside health may still return 500; the client presents a recoverable generic error.

Example question body:

```json
{"question": "How does photosynthesis use sunlight?", "source_ids": ["source-uuid"]}
```

The response contains `id`, `question`, `answer`, `source_ids`, `mode: "rag"` (or explicit `extractive` mode), `created_at`, and citations with `source_id`, `source_title`, `location`, and `excerpt`.

## Ingestion and storage

- Text: pasted or UTF-8 `.txt`; reject empty input, binary NULs in files, and content over 200,000 characters.
- PDF: validate signature, reject encryption, enforce 100-page/200,000-character limits, extract text through pypdf, and retain page numbers. PDFs without extracted text become `needs_text`.
- Image: verify actual image bytes with Pillow; allow PNG, JPEG, and WEBP. Stored as `needs_text` until a manual transcription is supplied. No OCR or image understanding is claimed.
- All file uploads: read at most the configured limit plus one byte; store originals in PostgreSQL `bytea`, with metadata and segments in the same transaction. The original filename is a display label, never a filesystem path.

For this local MVP, parsing runs synchronously in a worker thread. A multipart body may be spooled before the bounded application read; this is not an ingress-wide resource limit. Production requires gateway request limits, authenticated access, isolated/time-bounded parsers, and background jobs before accepting public uploads.

## Answer behavior

In optional extractive mode, the retrieval service removes common stop words, scores shared terms by inverse document frequency, and returns up to three verbatim segments from the selected sources. It acknowledges no lexical match rather than making up an answer. It does not do embeddings, reasoning, or conversational follow-up resolution. Citation snapshots retain the evidence even after source deletion or later transcription changes.

RAG is now the default; the preceding lexical behavior is available only with `AI_MODE=extractive`. See [the AI guide](vector-indexing.md) for configuration, upload-time indexing, rebuild endpoints, hybrid retrieval, and citation validation. Keep provider credentials server-side and preserve notebook/source filters, no-evidence behavior, and citation validation. Authentication should replace the controller’s `admin_id` lookup with a real session identity.

## Tests

`pytest tests ../ai/tests -q` runs fast in-memory SQLite tests with foreign keys enabled. Setting `TEST_DATABASE_URL` runs the same API suite against PostgreSQL 18 with migrations applied. Each integration test uses an outer transaction and nested savepoints; application commits never persist test data. Tests cover notebook lifecycle, title validation, citation/history persistence, missing evidence, source selection, cross-notebook and future-user isolation, cascading deletes, file validation, PDF page references, image transcription, and CORS.

GitHub Actions migrates PostgreSQL 18 before testing and checks for schema drift. No provider calls or credentials are needed in CI.

PPTX uploads extract slide text and tables, preserving slide locations. `POST /api/v1/notebooks/{id}/sources/url` accepts `{"url":"https://example.com/page"}` and saves a single-page snapshot. Upload, pasted text, URL, and transcription endpoints index synchronously in RAG mode. Inspect `index_status`, `index_error`, and `chunk_count` in the source response; successful source persistence does not imply successful indexing.

See [artifacts and retrieval comparison](artifacts-and-retrieval.md) for saved reports/quizzes, download endpoints and the `retrieval_method` selector. See [deployment](deployment.md) for the production container stack.
