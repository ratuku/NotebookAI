# NotebookAI

A small NotebookLM-inspired workspace built with **Next.js**, **FastAPI**, and **PostgreSQL 18**. Create notebooks, add sources, select which sources to question, and follow citations back to their text.

## What works

- Notebook library with search, creation, renaming, and deletion.
- Three-panel notebook workspace: sources, questions, and source reader; responsive mobile layout.
- Pasted text, UTF-8 `.txt`, PDF, PPTX, PNG/JPEG/WEBP uploads, and single-page URLs.
- Source selection, grounded AI answers with page/slide/paragraph citations, and persistent question history.
- Images and scanned PDFs can be uploaded and manually transcribed before asking questions.
- One seeded `admin` user; no sign-in; Groq credentials power generated answers.

**RAG uses local FastEmbed embeddings, Qdrant, hybrid semantic/BM25 retrieval, reciprocal rank fusion, and diversity selection.** Groq generates cited answers with `openai/gpt-oss-20b` by default. Reports and quizzes with answer keys can be saved and downloaded. OCR and authentication remain future work.

## Run in containers

See [deployment setup](docs/deployment.md). Copy `.env.deploy.example` to `.env.deploy`, set the PostgreSQL password and Groq key, then run:

```sh
docker compose --env-file .env.deploy -f compose.deploy.yaml up --build -d --wait
```

Open `http://localhost:8080` locally. On the shared EC2 server, set `APP_PORT=8081` in the server environment file to avoid the existing application. Public hosting requires HTTPS and access control for the shared admin workspace.

## Run locally

Requirements: Node.js 24+, Python 3.12+, Docker with Compose. Only PostgreSQL runs in Docker. The Next.js and FastAPI processes run on your host.

From the repository root:

```sh
docker compose up -d --wait
```

PostgreSQL listens on **localhost:5433** (5432 is often occupied). PostgreSQL 18 data is persisted by mounting `/var/lib/postgresql`. To change the host port, set `POSTGRES_PORT` and update `DATABASE_URL` accordingly.

Backend, in a terminal:

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.lock
pip install --no-deps -e ../ai -e .
cp .env.example .env
# Set GROQ_API_KEY in .env before asking AI questions.
alembic upgrade head
uvicorn notebook_backend.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend, in a second terminal:

```sh
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open [NotebookAI](http://localhost:3000). API documentation is at [FastAPI Swagger UI](http://localhost:8000/docs). Start a notebook, add a text source containing “Plants convert sunlight into energy through photosynthesis,” then ask “How does photosynthesis use sunlight?”

The development password in Compose is local-only. No authentication is implemented: anyone who can reach the backend has access to the admin workspace. Keep these processes bound to localhost.

Stop the database with `docker compose stop`; its configured host data directory keeps notebooks and sources. Existing named volumes are not automatically moved; see the deployment guide before changing an existing database mount.

## Tests

Backend (from `backend/`, with the virtual environment active):

```sh
ruff check . ../ai
ruff format --check . ../ai
pytest tests ../ai/tests -q
# PostgreSQL integration run after alembic upgrade head:
TEST_DATABASE_URL=postgresql+psycopg://notebook:local_notebook_password@localhost:5433/notebook pytest tests ../ai/tests -q
alembic check
```

The PostgreSQL tests use transactions that roll back. The default test run uses isolated, in-memory SQLite databases. Both execute the same API behavior tests.

Frontend (from `frontend/`):

```sh
npm run typecheck
npm test
npm run build
npx playwright install chromium
# Run the backend with AI_MODE=extractive for credential-free browser tests.
# Playwright starts the frontend when needed.
npm run test:e2e
```

Browser tests run on desktop and mobile viewports against the real API. They create and clean up their own notebooks. GitHub Actions runs on pull requests and pushes to `main`/`master`, with PostgreSQL 18, migrations, backend tests, frontend checks/build, and browser tests.

## Modules and documentation

```text
frontend/                 Next.js App Router, React, TypeScript
backend/                  FastAPI MVC app, SQLAlchemy, Alembic, pytest
ai/                       Extraction, embeddings, Qdrant, retrieval, Groq
compose.yaml              PostgreSQL 18 only
docs/architecture.md      Current architecture and Mermaid ER diagram
docs/frontend.md          UI structure and frontend/backend communication
docs/backend.md           Models, controllers, views, API and persistence
docs/progress.md          Implementation checkpoint and remaining work
```

- [Current architecture and entity diagram](docs/architecture.md)
- [Reports, quizzes and retrieval comparison](docs/artifacts-and-retrieval.md)
- [Container deployment](docs/deployment.md)
- [Frontend guide](docs/frontend.md)
- [Backend guide](docs/backend.md)
- [Implemented RAG pipeline and ingestion API](docs/vector-indexing.md)
- [Implementation checkpoint](docs/progress.md)
- [Original long-term architecture](docs/roadmap-architecture.md), retained as a roadmap, not a description of the MVP.

The original empty `front-end/` and `back-end/` folders are unused. See [AI configuration and limitations](docs/vector-indexing.md) for operational details.
