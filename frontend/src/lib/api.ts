export type Notebook = {
  id: string;
  title: string;
  description: string;
  created_at: string;
  source_count: number;
};
export type Source = {
  id: string;
  notebook_id: string;
  title: string;
  kind: "text" | "pdf" | "pptx" | "url" | "image";
  status: "ready" | "needs_text";
  index_status:
    "pending" | "processing" | "ready" | "failed" | "needs_text" | "disabled";
  index_error: string | null;
  chunk_count: number;
  url: string | null;
  created_at: string;
};
export type SourceDetail = Source & {
  text: string;
  segments: { location: string; text: string }[];
};
export type Citation = {
  chunk_id?: string;
  source_id: string;
  source_title: string;
  location: string;
  excerpt: string;
};
export type RetrievalStats = {
  chunks_found: number;
  candidates_count: number;
  chunks_selected: number;
  retrieval_ms: number;
  reranking_ms: number;
};
export type Question = {
  id: string;
  question: string;
  answer: string;
  source_ids: string[];
  citations: Citation[];
  mode: string;
  retrieval_method: "normal" | "reranking";
  retrieval_stats?: RetrievalStats | null;
  created_at: string;
};
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/v1${path}`, {
      ...options,
      headers: {
        ...(options?.body && !(options.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...options?.headers,
      },
    });
  } catch {
    throw new Error(
      "Cannot reach the server. Check that the backend is running and try again.",
    );
  }
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      typeof error?.detail === "string"
        ? error.detail
        : "That request could not be completed. Check your input and try again.",
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
export const notebookPath = (id: string) =>
  `/notebooks/${encodeURIComponent(id)}`;
export const sourceFileUrl = (notebookId: string, sourceId: string) =>
  `${API_URL}/api/v1${notebookPath(notebookId)}/sources/${encodeURIComponent(sourceId)}/file`;
export function message(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Something went wrong. Try again.";
}

export function isSourceReady(source: Source) {
  return (
    source.status === "ready" &&
    ["ready", "disabled"].includes(source.index_status)
  );
}

export type RetrievalMethod = "normal" | "reranking";
export type Artifact = {
  id: string;
  title: string;
  kind: "report" | "quiz";
  topic: string;
  retrieval_method: RetrievalMethod;
  retrieval_stats?: RetrievalStats | null;
  created_at: string;
  citations: Citation[];
  content: {
    sections?: {
      heading: string;
      claims: { text: string; citations: string[] }[];
    }[];
    questions?: {
      question: string;
      answer: { text: string; citations: string[] };
    }[];
  };
};
export const artifactDownloadUrl = (
  notebookId: string,
  artifactId: string,
  format: "markdown" | "html",
) =>
  `${API_URL}/api/v1${notebookPath(notebookId)}/artifacts/${encodeURIComponent(artifactId)}/download?format=${format}`;
