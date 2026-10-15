# Container deployment

`compose.deploy.yaml` packages Next.js, FastAPI with the AI module, PostgreSQL 18, and an Nginx gateway. The existing `compose.yaml` remains available for host-based development with only PostgreSQL in Docker.

## Start

From the repository root:

```sh
cp .env.deploy.example .env.deploy
# Edit .env.deploy: set POSTGRES_PASSWORD and GROQ_API_KEY.
# Use a URL-safe PostgreSQL password, e.g. output from: openssl rand -hex 24
docker compose --env-file .env.deploy -f compose.deploy.yaml up --build -d --wait
```

Open `http://localhost:8080`. The browser uses the same origin for `/api/v1/...`; there is no localhost backend URL embedded in the deployed frontend. Only the gateway publishes a port. Backend, frontend and PostgreSQL stay on the Compose network. The frontend image uses Next.js standalone output, and application processes run as non-root users. `.dockerignore` excludes secrets, local databases/model caches and host dependencies.

The migration service waits for PostgreSQL health, runs `alembic upgrade head`, and must succeed before the API starts. The gateway waits for healthy backend and frontend services. Restart the stack after configuration changes. Use one backend worker because embedded Qdrant permits one owning process.

The application still has one shared admin account. For public deployment, place the loopback gateway behind an HTTPS reverse proxy with access control, or implement application authentication. Set `BIND_ADDRESS` only for the intended network; changing it to `0.0.0.0` exposes the shared workspace to that network. TLS, domain setup, provider secrets and a hosting destination are deployment configuration, not included cloud infrastructure.

## Persistence and operations

A configurable host directory retains PostgreSQL data; named volumes retain model downloads and Qdrant vectors. This deployment uses its own project/volumes; it does not automatically import the development database. Back up PostgreSQL using `pg_dump` and restore into the target database when migrating existing notebooks. Backups include source originals, chat history and artifacts. Rebuild the vector index after restoring or changing the embedding model. Never run `down -v` on valuable data.

```sh
docker compose --env-file .env.deploy -f compose.deploy.yaml logs --tail=100 backend migrate
docker compose --env-file .env.deploy -f compose.deploy.yaml exec backend alembic check
docker compose --env-file .env.deploy -f compose.deploy.yaml down
```

First RAG ingestion downloads the local embedding model, requiring outbound access to its host. Groq requires outbound HTTPS. For a warm deployment, run a small upload before accepting traffic. Nginx allows a 10 MB application file upload plus multipart overhead and waits up to 300 seconds for synchronous requests. Large rebuilds can outlive that timeout; use smaller notebook scopes and retry safely. This setup is a single-host deployment, not a multi-replica or queued ingestion architecture.

The deployment environment file stays untracked. Secrets are supplied at runtime, never image build arguments. For a managed host, supply the same environment values through its secret store. Use versioned image tags/digests for release promotion; the supplied `:local` tags are for local builds.

## Checks

PR CI builds both images, starts the stack with `AI_MODE=extractive`, checks migrations and runs `python3 deploy/smoke.py` through the gateway. This verifies routing, UI delivery, upload, answers, history and cleanup without Groq credentials. AI-specific behavior is covered separately with deterministic provider doubles and actual Qdrant. The default deployment remains `AI_MODE=rag`.

Compose health/ordering follows the [Docker startup-order documentation](https://docs.docker.com/compose/how-tos/startup-order/).

## Per-application PostgreSQL paths

PostgreSQL now uses a configurable **bind mount**, not a named volume:

```dotenv
# App A environment file
COMPOSE_PROJECT_NAME=notebookai-a
POSTGRES_DATA_PATH=/srv/apps/notebookai-a/postgres18
APP_PORT=8080
```

For another application use a separate environment file, `COMPOSE_PROJECT_NAME=notebookai-b`, `POSTGRES_DATA_PATH=/srv/apps/notebookai-b/postgres18`, and `APP_PORT=8081`. Start each with its own `--env-file`. Distinct project names also separate networks and the remaining model/vector named volumes. Never point two PostgreSQL servers at the same data directory. Paths are host paths; for an EC2 Docker host, place them on a persistently mounted disk. This Compose configuration targets a Docker host, not automatic ECS/EKS orchestration.

Defaults: `./data/deploy/postgres18` for deployment and `./data/postgres18` for development. Both are ignored by Git and Docker builds. The host directory mounts at `/var/lib/postgresql`; PostgreSQL 18 stores its cluster under `18/docker` within it, as specified by the [official image](https://hub.docker.com/_/postgres).

Changing the path **does not move old data**. Existing named volumes are retained. Before replacing a valuable existing container, export its database, start the new path-backed database, and restore the dump; verify notebook counts and source/artifact contents before retiring the old storage. No existing development data was deleted or silently migrated by this change.

Example logical backup for one running app (create the backup directory first):

```sh
docker compose --env-file .env.app-a -f compose.deploy.yaml exec -T postgres \
  pg_dump -U notebook -d notebook -Fc > /srv/backups/notebookai-a.dump
```

Use separate filenames/directories per app and check command success. A clearly named path aids operations, but copying a live PostgreSQL directory is not by itself a consistent backup: use `pg_dump`, a PostgreSQL-aware physical backup, or stop PostgreSQL before a filesystem copy. See [PostgreSQL backup guidance](https://www.postgresql.org/docs/18/backup-file.html). Back up the full database, not individual files from `18/docker`.
