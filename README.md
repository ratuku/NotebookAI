# NotebookAI

NotebookAI is a NotebookLM-inspired application that turns a user's sources into a notebook workspace for cited questions and answers, reports, and quizzes. Its goal is to make document-based learning and research easier while keeping answers traceable to the original evidence.

**Status:** initial repository scaffold and architecture planning. The features below are requirements and roadmap items, not implemented capabilities. The current component directories are `front-end/`, `back-end/`, and `ai/`; the target architecture uses `frontend/`, `backend/`, and `ai/`.

## Goals and required capabilities

| Requirement | Intended outcome / completion evidence |
| --- | --- |
| Multiple notebooks | Create and manage separate notebooks, each with its own sources, chat, and artifacts |
| Source ingestion | Upload PDF, PPTX, and TXT files and ingest a single-page URL; expose processing status and useful errors |
| Cited RAG answers | Ask questions across selected notebook sources; answers cite resolvable pages, slides, or text locations and acknowledge insufficient evidence |
| Reports | Generate a source-grounded report and download the result |
| Quizzes and answer keys | Generate quizzes with correct answer keys and explanations, with downloadable output |
| Storage abstraction | Support local and S3-compatible object-storage adapters through one application interface |
| Documentation and deployment | Provide architecture, setup/configuration, API, and deployment instructions with a reproducible deployed demo |
| RAG comparison | Compare at least two configurations on a fixed evaluation set, reporting grounding, citations, retrieval quality, latency, and cost |

These requirements form the project's rubric-aligned delivery checklist. They are not a claim of a rubric score or completed implementation.

## Planned technology stack

| Area | Technology and responsibility |
| --- | --- |
| Frontend | Next.js and TypeScript: notebooks, sources, chat, citation navigation, artifact downloads |
| Business backend | FastAPI and Python, packaged as `src/notebook_backend`: authorization, metadata, workflows, public API |
| AI component | FastAPI and Python, packaged as `src/notebook_ai`: RAG ingestion/indexing/retrieval/evaluation, generation, LLM and embedding provider adapters |
| Shared contracts | Pydantic DTOs in `packages/contracts`; OpenAPI-derived TypeScript types can support the frontend |
| Application database | PostgreSQL, owned by the backend |
| Vector database | Qdrant, owned by the AI component |
| Object storage | Local filesystem for development and S3-compatible storage through an abstraction |
| Infrastructure | Docker for containers/local services; Terraform for deployment provisioning |

The model provider, authentication provider, durable queue, hosting platform, and export formats will be selected during implementation.

## Architecture and repository layout

```text
notebookeai/
├── frontend/          # Next.js + TypeScript (target name)
├── backend/           # FastAPI; src/notebook_backend (target name)
├── ai/                # FastAPI; src/notebook_ai
├── packages/contracts/# Shared Pydantic DTOs
├── infrastructure/    # Docker and Terraform
├── docs/              # Design, setup, deployment, evaluation
└── README.md
```

The frontend calls the backend, which owns access control and coordinates work with the internal AI API. The backend owns PostgreSQL metadata and object-storage lifecycle; AI owns the derived Qdrant index. Original sources and generated files live in object storage. Both Python services use shared transport contracts without sharing database models.

See [the architecture plan](docs/architecture.md) for the detailed layout, service boundaries, data ownership, ingestion/chat/artifact flows, development and deployment approach, security, evaluation, and tradeoffs.

## Development roadmap

1. **Foundation:** adopt the canonical folder names, scaffold the Next.js and Python packages, define DTOs and configuration, and add local infrastructure and CI.
2. **Notebooks and storage:** implement authentication/authorization, notebook/source metadata, migrations, and local/S3-compatible storage adapters.
3. **Ingestion:** deliver PDF ingestion end to end with durable job status, then PPTX, TXT, and guarded single-page URL ingestion; preserve citation locations and source versions.
4. **Grounded chat:** implement scoped indexing/retrieval, provider integration, cited answers, insufficient-evidence behavior, chat persistence, and isolation tests.
5. **Artifacts:** generate reports and quizzes with answer keys, validate structured output, and provide authorized downloads.
6. **Evaluation:** build a held-out dataset, compare RAG configurations, review citation/answer quality, and document measured results and limitations.
7. **Deployment and handoff:** finish Docker/Terraform configuration, security and recovery checks, deployment/setup documentation, and an end-to-end demo against the requirements above.

## Development setup

There is no runnable application or dependency/container manifest yet. Setup commands will be added with the foundation milestone rather than presented as working today.

The intended workflow is to install frontend dependencies, install the backend/AI/contracts Python packages in development environments, start PostgreSQL/Qdrant and object storage locally, apply database migrations, configure server-side provider credentials, and start all three application components. Exact runtime versions and commands will be pinned in the component manifests and setup documentation.

Keep secrets out of Git. The existing ignore rules exclude `.idea/`, `.venv/`, and common Python caches; add secret environment-file exclusions and safe example configuration when scaffolding configuration files.

## Validation and project documentation

Completion requires a demonstrated flow from source ingestion through cited chat to downloadable reports/quizzes, plus notebook isolation, failure handling, and storage-adapter checks. RAG comparisons should use the same sources and held-out questions, record configuration/model versions, and report quality alongside latency and cost.

- [Architecture plan](docs/architecture.md) — agreed design and implementation decisions.
- Setup/API/deployment guides and a RAG comparison report — planned deliverables as implementation progresses.
