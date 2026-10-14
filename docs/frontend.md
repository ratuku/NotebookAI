# Frontend

## Implementation

`frontend/` is a Next.js App Router app using TypeScript, React, Lucide icons, and a shared CSS stylesheet. It runs locally on port 3000. No application container is required.

- `src/app/page.tsx`: notebook library, search, grid/list views, empty/loading/error states, and creation dialog.
- `src/app/notebooks/[id]/page.tsx`: dynamic notebook route, passing the route ID to the interactive workspace.
- `src/components/workspace.tsx`: selected source state, source reader, question history, cited answers, rename/delete dialogs, and manual transcription for images/scans.
- `src/components/add-source.tsx`: multipart upload or pasted-text source creation, with validation and progress/error feedback.
- `src/components/dialog.tsx`: native modal dialog with browser-managed focus and Escape handling.
- `src/lib/api.ts`: typed HTTP client, request/response interfaces, common error handling, and file URLs.
- `src/app/globals.css`: neutral/blue visual system, reusable panels/forms/cards, responsive library and workspace layouts, focus states, reduced-motion support.

The home page is a notebook-card library with search and grid/list views. The supplied Google Notebook screenshots guide the neutral background, rounded cards and panels, blue actions, and spacious typography. A notebook opens a sources/chat/reader workspace. The desktop layout has three columns; narrow layouts stack the panels. The right panel provides a working source reader; the full Google Studio suite and featured public notebooks are outside this basic milestone.

Sources can be independently selected. The composer is disabled without ready sources. Clicking a citation opens its source in the reader, with the cited page/paragraph label visible in the answer. It does not automatically scroll to an exact PDF coordinate. Deleted sources keep historical quotes but opening them shows the API error. Images and scans offer a transcription form and an “Open original” link.

## Backend connection

Copy `.env.example` to `.env.local`:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

The public variable contains only the backend origin, never a credential. Restart Next.js after changing it; production builds embed it. The client appends `/api/v1` and sends JSON for metadata/questions and `FormData` for file uploads. Do not manually supply multipart `Content-Type`; the browser provides its boundary. Files open from the notebook-scoped backend file endpoint.

API state persists in PostgreSQL. React state only manages transient UI state, search, and current source selection; source selection resets to all ready sources after refresh. The UI never fabricates notebooks or answers when the server is unavailable. It displays a retry action or error instead.

Use `http://localhost:3000` to match the default backend CORS origin. For another frontend address, configure `CORS_ORIGINS` on the backend.

## Commands and tests

```sh
npm ci
npm run dev
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Vitest tests verify notebook filtering, creation/navigation, recoverable API errors, multipart headers, and empty deletion responses. Playwright runs desktop and mobile flows against the real FastAPI backend: create notebook, upload text, ask a question, read a citation, reload history, deselect sources, and delete the notebook. Keep FastAPI and PostgreSQL running before launching browser tests. Playwright starts Next.js automatically when it is not already running.

The CSS uses system fonts and has no external font requests. Authentication, generative AI, source editing beyond transcription, and model/settings controls are intentionally absent.
