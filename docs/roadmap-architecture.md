# NotebookAI long-term architecture (archived planning baseline)

> This is the original, unimplemented long-term plan. See [current architecture](architecture.md) for the working MVP. The current user request takes precedence: one backend, no authentication, and Docker only for PostgreSQL.

## Status and architectural decision

This document describes the agreed target architecture, not an already implemented system. The repository currently contains documentation and empty `front-end/`, `back-end/`, and `ai/` directories. Implementation should adopt `frontend/` and `backend/` as the canonical names; this documentation update does not rename directories.

NotebookAI is a NotebookLM-inspired application for organizing sources into notebooks, asking grounded questions, and generating downloadable reports and quizzes. It uses a monorepo with three independently deployable components: a Next.js frontend, a FastAPI business backend, and a FastAPI AI component. A directory describes source organization; it does not need a `-service` suffix to represent a deployable service.

## Target repository layout

```text
notebookeai/
├── frontend/                       # Next.js + TypeScript
│   ├── src/app/                    # Pages, layouts, and UI routing
│   ├── src/components/
│   └── package.json
├── backend/
│   ├── src/notebook_backend/       # Importable Python package
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI application
│   │   ├── api/
│   │   ├── services/               # Business use cases
│   │   ├── models/                 # PostgreSQL persistence models
│   │   ├── repositories/
│   │   ├── storage/                # Object-storage interface/adapters
│   │   └── core/                   # Configuration and authentication
│   ├── migrations/
│   ├── tests/
│   └── pyproject.toml
├── ai/
│   ├── src/notebook_ai/            # Importable Python package
│   │   ├── __init__.py
│   │   ├── main.py                 # Internal FastAPI application
│   │   ├── api/
│   │   ├── rag/
│   │   │   ├── ingestion/          # Parsing, cleaning, chunking
│   │   │   ├── indexing/           # Embeddings and Qdrant writes
│   │   │   ├── retrieval/          # Search, filtering, reranking
│   │   │   └── evaluation/         # Datasets and experiment runners
│   │   ├── generation/             # Answers, reports, quizzes
│   │   ├── providers/              # LLM and embedding provider adapters
│   │   └── core/
│   ├── tests/
│   └── pyproject.toml
├── packages/
│   └── contracts/
│       ├── src/notebook_contracts/ # Shared Pydantic request/response DTOs
│       ├── tests/
│       └── pyproject.toml
├── infrastructure/
│   ├── docker/                    # Images and local Compose setup
│   └── terraform/                 # Provisioned deployment resources
├── docs/
│   └── architecture.md
└── README.md
```

In the Python components, `src/` contains packages; `notebook_backend` and `notebook_ai` are importable packages. For example, code imports `notebook_backend.services`, not `src.notebook_backend.services`. This is an established Python packaging layout, not a requirement imposed by FastAPI. It separates installed application code from repository-root files. The Next.js `app/` directory has a different role: it defines frontend routes.

## Service boundaries

| Component | Owns | Boundary |
| --- | --- | --- |
| Frontend | Notebook workspace, source uploads, chat, citation navigation, job status, artifact downloads | Calls the backend; receives no database or model-provider credentials |
| Backend | Authentication and authorization, notebook/source lifecycle, chat history, artifact metadata, durable job state, storage access | Public application API; coordinates AI operations without implementing RAG |
| AI | Parsing and chunking, embedding/indexing, retrieval/reranking, grounded generation, provider integration, evaluation | Internal API; accepts authenticated requests scoped to authorized notebooks and sources |
| Contracts | Pydantic DTOs, identifiers, enums, citation/error/job schemas | Shared transport contracts, not ORM models or business logic |
| Infrastructure | Containers, networks, storage provisioning, secrets integration, deployment configuration | Operational configuration rather than application behavior |

The backend is the public trust boundary. The AI component must also validate service credentials and request scope; network isolation alone is insufficient. It does not query backend database tables directly. Both Python components depend on the contracts package. TypeScript clients/types can be generated from the backend OpenAPI schema; the frontend does not import Python DTOs.

Version APIs and evolve DTOs compatibly so independently deployed services can coexist during rollouts. Validate structured AI outputs against contracts before returning or persisting them.

## Data ownership

| Store | Owner and authoritative data | Access rules |
| --- | --- | --- |
| PostgreSQL | Backend: users/access grants, notebooks, source metadata and versions, conversations/messages, citations attached to answers, jobs, artifact metadata | Backend reads/writes; AI receives required metadata through contracts |
| Qdrant | AI: vectors, chunk text or text references, retrieval metadata, source locations, embedding/index versions | AI reads/writes; every operation scopes by tenant/owner and notebook, plus source/version when relevant |
| Object storage | Backend controls the object namespace and lifecycle: original uploads, captured URL content, generated report/quiz files, and optional parsed intermediates | Backend grants short-lived, object-scoped access to AI and authorized clients |

Original source objects and their PostgreSQL metadata are the durable source of truth. Qdrant indexes are derived data and must be rebuildable. Store page numbers for PDFs, slide numbers for PPTX, and stable section/line or captured-page anchors for TXT/URLs so citations can resolve to evidence.

Use an object-storage abstraction with operations such as put, get, delete, and temporary access. Start with a local filesystem adapter and add an S3-compatible adapter without changing business use cases. A local development adapter may use an authenticated download endpoint or a shared volume; it must not assume that one container's local path exists in another. Store opaque object keys in PostgreSQL, not machine-specific absolute paths or permanent public URLs.

Deletion is coordinated by the backend: revoke user access immediately, mark the resource as deleting, then retry cleanup of vectors, source objects, and artifacts until complete. There is no cross-store transaction. Use source versions, idempotent job identifiers, and reconciliation to handle partial failures and prevent old ingestion jobs from reviving deleted data.

## API and processing flows

The routes below illustrate the intended contract; they are not implemented endpoints. Public routes use a versioned prefix such as `/api/v1`; internal AI routes use a separately secured prefix such as `/internal/v1`.

### Source ingestion

1. The frontend creates/selects a notebook and submits a PDF, PPTX, TXT file, or a single-page URL through the backend's notebook-scoped sources endpoint.
2. The backend checks authorization, file type/size or URL policy, creates source metadata, stores the original file (or schedules a guarded URL fetch), and creates a durable ingestion job. URL content is captured as a versioned object; linked pages are not recursively crawled.
3. The backend dispatches an internal ingestion request with the job ID, authorized scope, source version, and narrowly scoped object access. It returns `202 Accepted` with a job identifier for long-running work.
4. AI extracts text and source locations, cleans and chunks it, generates embeddings through its provider adapter, and upserts scoped vectors into Qdrant. Record parser, chunking, embedding, and index versions. Scanned PDFs without usable text should return an explicit unsupported/OCR-needed result until OCR is implemented.
5. An authenticated result callback or backend polling updates the authoritative job/source state in PostgreSQL. States include queued, processing, ready, and failed, with retryable errors distinguished from invalid inputs. Chat searches only ready source versions.

A durable worker/queue implementation is a deployment decision to make during the ingestion milestone. Production must use persisted jobs and recoverable dispatch (for example, a database outbox), rather than relying solely on in-process background tasks. Repeated delivery must not duplicate chunks or change completed job results.

### Cited notebook chat

1. The frontend submits a question to the backend with a notebook and optional source selection.
2. The backend authorizes the notebook and selected sources, records the user message, and sends an internal chat request with only the allowed source versions and relevant conversation context.
3. AI embeds the question, retrieves within that scope, optionally reranks, and builds a prompt containing evidence and citation identifiers. Source text is treated as untrusted content.
4. The model generates an answer grounded in that evidence. AI validates citation identifiers against retrieved chunks and returns the answer with structured source references. If evidence is insufficient, the answer says so rather than inventing support. Identifier validation alone does not establish that a claim is supported; evaluation must measure grounding.
5. The backend persists the answer and citation metadata and returns them to the frontend. Citation navigation and source downloads require the same authorization checks as the original source.

Streaming can be added after the complete request/response path is reliable; define how partial output and final citations are handled before enabling it.

### Reports and quizzes

1. The frontend requests an artifact for an authorized notebook/source selection, specifying report or quiz and supported generation options.
2. The backend creates a durable artifact job and sends its authorized source scope to AI.
3. AI retrieves supporting evidence and generates a structured report or quiz. Quiz output includes questions, answer keys, and explanations; reports and quiz explanations retain source citations where applicable.
4. AI validates the output and renders downloadable files, then writes through narrowly scoped object-storage access. The backend records artifact type, source versions, generation configuration, object keys, and job outcome. Exact export formats are an implementation decision; downloadable reports and quizzes with answer keys are required.
5. The frontend displays status and requests an authorized download from the backend, which streams the file or issues a short-lived download URL. A separate learner quiz and answer-key download can be offered without changing the underlying structured artifact.

## Development and deployment

Develop all components in the monorepo, with separate dependency manifests, lockfiles, tests, and container images. Install the Python services and shared contracts as packages (editable installs during development). After scaffolding, the FastAPI application entry points will be `notebook_backend.main:app` and `notebook_ai.main:app`.

Local Compose should provide PostgreSQL, Qdrant, and optionally S3-compatible storage alongside the application services. Document environment variables in example files without secrets: database connection, Qdrant address, backend/AI URLs, storage adapter settings, and model/embedding configuration. The repository does not yet contain these manifests, commands, or configuration files.

CI should run formatting/static checks, unit tests for business behavior, API/DTO compatibility checks, and integration tests for scoped retrieval and storage adapters. Add an end-to-end path covering upload, ingestion readiness, cited chat, generation, and download. Keep paid provider evaluation separate or explicitly budgeted; deterministic provider doubles support routine CI.

Deploy frontend, backend, and AI independently using Docker images. Terraform should provision environment-specific networking, managed or self-hosted PostgreSQL/Qdrant, object storage, secret access, and runtime resources. Keep databases, Qdrant, and AI off the public internet. Run database migrations as a controlled deployment step, maintain backups and restore procedures, and coordinate embedding/index migrations rather than mixing incompatible vector dimensions.

Propagate request/job IDs and observe latency, failures, queue age, retrieval quality, and provider usage/cost. Avoid logging full documents, prompts, or private answers by default. Scale AI workers independently from interactive API traffic; apply timeouts, bounded retries, and concurrency limits to provider calls.

## Security

- Authenticate users and authorize notebook, source, chat, artifact, and download operations. Never accept client-provided tenant IDs as proof of access.
- Enforce tenant/notebook filters in every AI retrieval and mutation. Test cross-notebook and cross-user isolation, including malicious source selections.
- Validate actual file contents as well as extensions; limit size, parsing time, archive expansion, page/slide count, and extracted text. Isolate risky parsers and handle malformed inputs safely.
- Guard URL ingestion against SSRF: allow only supported HTTP(S) URLs, reject private/loopback/link-local and metadata-service destinations, revalidate redirects and resolved addresses, and bound response sizes/timeouts. Do not forward user or service credentials to source URLs.
- Treat source text and model output as untrusted. Documents cannot override system instructions or trigger privileged actions. Escape rendered output and prevent generated content from executing code.
- Keep provider keys and service credentials server-side, use TLS in deployment, restrict storage permissions, and set expiry on temporary URLs. Define retention/deletion policy and disclose that selected content may be sent to the configured external model provider.
- Apply per-user upload/generation limits, rate limits, and spending controls. Select an authentication mechanism and document its session, CSRF, and CORS requirements before implementation.

## RAG evaluation and comparison

Maintain a versioned evaluation set of representative sources, questions, expected evidence, and reference answers. Include PDF/PPTX/TXT/URL cases, multi-source synthesis, unanswerable questions, prompt injection, and isolation tests. Separate tuning data from held-out evaluation data.

Compare at least two RAG configurations on the same corpus and held-out questions. A useful baseline is fixed-size chunks plus dense vector retrieval; a candidate can change chunking, retrieval depth, or add reranking. Change one factor at a time where possible, and keep the generation model/prompt fixed when comparing retrieval. Hybrid retrieval is an optional experiment, not an assumed Qdrant setup.

Record retrieval recall@k and ranking metrics when evidence labels exist; answer correctness/relevance; faithfulness to evidence; citation correctness/coverage; appropriate abstention; latency; and token/embedding cost. Evaluate reports for source coverage and factual support, and quizzes for question clarity, correct answer keys, and grounded explanations. Combine reproducible automated checks with a documented human review rubric; model judges are supplementary and have limitations.

Save corpus version, source hashes, parser/chunking settings, embedding/generation model versions, prompts, index configuration, and per-question results. Publish the comparison methodology and findings under `docs/`, including failure examples and the chosen configuration's quality/cost tradeoffs. Define acceptance thresholds before selecting a winner rather than claiming an unmeasured improvement.

## Benefits and tradeoffs

| Decision | Benefit | Cost or mitigation |
| --- | --- | --- |
| Monorepo, independent services | Shared contracts and coordinated changes; separate deployment/scaling | Requires clear ownership, compatible releases, and component-specific CI |
| Backend/AI separation | Business rules stay independent of RAG experiments and provider changes | Adds network calls and distributed failures; use durable jobs and observability |
| Python `src/` packages | Explicit imports and package boundaries | Requires package installation and correct tooling configuration |
| PostgreSQL + Qdrant + object storage | Each store serves its intended workload | Cross-store consistency, backups, and deletion require coordination |
| Storage/provider interfaces | Local development and replaceable infrastructure/vendors | Avoid overly generic interfaces; implement only required operations |
| Asynchronous ingestion/generation | Handles large documents and long model calls | Adds job/worker complexity and eventual consistency visible in the UI |

Start with the smallest complete vertical slice, then add formats, artifact generation, operational hardening, and measured RAG improvements. Authentication provider, model vendor, queue technology, hosting platform, OCR, and final export formats remain implementation choices; they do not change these service boundaries.
