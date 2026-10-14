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
  kind: "text" | "pdf" | "image";
  status: "ready" | "needs_text";
  created_at: string;
};
export type SourceDetail = Source & {
  text: string;
  segments: { location: string; text: string }[];
};
export type Citation = {
  source_id: string;
  source_title: string;
  location: string;
  excerpt: string;
};
export type Question = {
  id: string;
  question: string;
  answer: string;
  source_ids: string[];
  citations: Citation[];
  mode: string;
  created_at: string;
};
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
