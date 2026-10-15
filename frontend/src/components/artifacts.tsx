"use client";
import { RetrievalSummary } from "./retrieval-summary";
import { useEffect, useState, type FormEvent } from "react";
import {
  request,
  notebookPath,
  message,
  artifactDownloadUrl,
  type Artifact,
  type RetrievalMethod,
} from "@/lib/api";

export function Artifacts({
  notebookId,
  sourceIds,
  method,
}: {
  notebookId: string;
  sourceIds: string[];
  method: RetrievalMethod;
}) {
  const path = `${notebookPath(notebookId)}/artifacts`;
  const [items, setItems] = useState<Artifact[]>([]);
  const [active, setActive] = useState<Artifact | null>(null);
  const [kind, setKind] = useState<"report" | "quiz">("report");
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(5);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    request<Artifact[]>(path)
      .then((data) => {
        if (live) setItems(data);
      })
      .catch((e) => {
        if (live) setError(message(e));
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [path]);
  async function generate(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const item = await request<Artifact>(path, {
        method: "POST",
        body: JSON.stringify({
          kind,
          topic,
          question_count: count,
          source_ids: sourceIds,
          retrieval_method: method,
        }),
      });
      setItems((old) => [item, ...old]);
      setActive(item);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="artifact-studio">
      <p>
        Turn {sourceIds.length} selected sources into a report or a short-answer
        quiz with an answer key. Retrieval:{" "}
        {method === "normal" ? "Normal" : "Reranking"}.
      </p>
      <form onSubmit={generate}>
        <label>
          Artifact type
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as "report" | "quiz")}
            disabled={busy}
          >
            <option value="report">Report</option>
            <option value="quiz">Quiz + answer key</option>
          </select>
        </label>
        <label>
          Topic or learning objective
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            required
            maxLength={2000}
            placeholder="e.g. Explain how photosynthesis works"
            disabled={busy}
          />
        </label>
        {kind === "quiz" && (
          <label>
            Number of questions
            <input
              type="number"
              min={3}
              max={10}
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
              required
              disabled={busy}
            />
          </label>
        )}
        <button
          className="primary"
          disabled={busy || !sourceIds.length || !topic.trim()}
        >
          {busy ? "Generating from sources…" : "Generate artifact"}
        </button>
        {!sourceIds.length && (
          <p>Select indexed sources in the notebook first.</p>
        )}
      </form>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <h3>Saved artifacts</h3>
      {loading ? (
        <p role="status">Loading artifacts…</p>
      ) : (
        !items.length && <p>No artifacts yet.</p>
      )}
      <div className="artifact-list">
        {items.map((item) => (
          <button
            className="secondary"
            key={item.id}
            onClick={() => setActive(item)}
            aria-pressed={active?.id === item.id}
          >
            {item.title} · {item.kind} · {item.retrieval_method}
          </button>
        ))}
      </div>
      {active && (
        <article className="artifact-preview">
          <h2>{active.title}</h2>
          <RetrievalSummary stats={active.retrieval_stats} />
          <p>
            Generated from retrieved source passages. Review the evidence before
            use.
          </p>
          <div className="artifact-downloads">
            <a
              className="secondary"
              href={artifactDownloadUrl(notebookId, active.id, "markdown")}
            >
              Download Markdown
            </a>
            <a
              className="secondary"
              href={artifactDownloadUrl(notebookId, active.id, "html")}
            >
              Download printable HTML
            </a>
          </div>
          {active.content.sections?.map((section, i) => (
            <section key={i}>
              <h3>{section.heading}</h3>
              {section.claims.map((claim, j) => (
                <p key={j}>
                  {claim.text}{" "}
                  {claim.citations
                    .map(
                      (id) =>
                        `[${active.citations.findIndex((c) => c.chunk_id === id) + 1}]`,
                    )
                    .join(" ")}
                </p>
              ))}
            </section>
          ))}
          {active.content.questions && (
            <>
              <h3>Questions</h3>
              <ol>
                {active.content.questions.map((q, i) => (
                  <li key={i}>{q.question}</li>
                ))}
              </ol>
              <details>
                <summary>Answer key</summary>
                <ol>
                  {active.content.questions.map((q, i) => (
                    <li key={i}>
                      {q.answer.text}{" "}
                      {q.answer.citations
                        .map(
                          (id) =>
                            `[${active.citations.findIndex((c) => c.chunk_id === id) + 1}]`,
                        )
                        .join(" ")}
                    </li>
                  ))}
                </ol>
              </details>
            </>
          )}
          <h3>Sources and evidence</h3>
          {active.citations.map((c, i) => (
            <details key={i}>
              <summary>
                [{i + 1}] {c.source_title} · {c.location}
              </summary>
              <p>{c.excerpt}</p>
            </details>
          ))}
        </article>
      )}
    </div>
  );
}
