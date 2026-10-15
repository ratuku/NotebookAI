"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowUp,
  BookOpen,
  Check,
  FileText,
  Image as ImageIcon,
  MessageSquare,
  Plus,
  Sparkles,
  Trash2,
  X,
  ExternalLink,
  Pencil,
} from "lucide-react";
import { Brand, Avatar } from "./brand";
import { Dialog } from "./dialog";
import { AddSource } from "./add-source";
import {
  request,
  isSourceReady,
  notebookPath,
  sourceFileUrl,
  message,
  type Notebook,
  type Source,
  type SourceDetail,
  type Question,
} from "@/lib/api";

export function Workspace({ id }: { id: string }) {
  const path = notebookPath(id);
  const router = useRouter();
  const [notebook, setNotebook] = useState<Notebook | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [reader, setReader] = useState<SourceDetail | null>(null);
  const [reading, setReading] = useState(false);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");
  const [transcription, setTranscription] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState<Source | "notebook" | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const readVersion = useRef(0);
  async function load() {
    setLoading(true);
    setError("");
    try {
      const [n, s, q] = await Promise.all([
        request<Notebook>(path),
        request<Source[]>(`${path}/sources`),
        request<Question[]>(`${path}/questions`),
      ]);
      setNotebook(n);
      setTitle(n.title);
      setSources(s);
      setQuestions(q);
      setSelected(s.filter((s) => isSourceReady(s)).map((s) => s.id));
    } catch (e) {
      setError(message(e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load(); /* id is fixed for this mounted workspace */
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [questions, asking]);
  async function openSource(sourceId: string) {
    const version = ++readVersion.current;
    setReading(true);
    setError("");
    try {
      const source = await request<SourceDetail>(`${path}/sources/${sourceId}`);
      if (version === readVersion.current) {
        setReader(source);
        setTranscription(source.text);
      }
    } catch (e) {
      if (version === readVersion.current) setError(message(e));
    } finally {
      if (version === readVersion.current) setReading(false);
    }
  }
  async function ask(event: FormEvent) {
    event.preventDefault();
    if (!question.trim() || !selected.length || asking) return;
    setAsking(true);
    setError("");
    try {
      const q = await request<Question>(`${path}/questions`, {
        method: "POST",
        body: JSON.stringify({ question, source_ids: selected }),
      });
      setQuestions((qs) => [...qs, q]);
      setQuestion("");
    } catch (e) {
      setError(message(e));
    } finally {
      setAsking(false);
    }
  }
  async function rename(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setNotebook(
        await request<Notebook>(path, {
          method: "PATCH",
          body: JSON.stringify({
            title,
            description: notebook?.description || "",
          }),
        }),
      );
      setEditing(false);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (!deleting) return;
    setBusy(true);
    setError("");
    try {
      await request(
        deleting === "notebook" ? path : `${path}/sources/${deleting.id}`,
        { method: "DELETE" },
      );
      if (deleting === "notebook") {
        router.push("/");
        return;
      }
      setSources((ss) => ss.filter((s) => s.id !== deleting.id));
      setSelected((ids) => ids.filter((i) => i !== deleting.id));
      if (reader?.id === deleting.id) setReader(null);
      setDeleting(null);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function saveTranscription(event: FormEvent) {
    event.preventDefault();
    if (!reader) return;
    setBusy(true);
    setError("");
    try {
      const updated = await request<SourceDetail>(
        `${path}/sources/${reader.id}/text`,
        {
          method: "PUT",
          body: JSON.stringify({
            title: reader.title.slice(0, 160),
            text: transcription,
          }),
        },
      );
      setReader(updated);
      setSources((ss) => ss.map((s) => (s.id === updated.id ? updated : s)));
      setSelected((ids) =>
        isSourceReady(updated)
          ? [...new Set([...ids, updated.id])]
          : ids.filter((id) => id !== updated.id),
      );
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function retryIngestion() {
    if (!reader) return;
    setBusy(true);
    setError("");
    try {
      const source = await request<Source>(
        `${path}/sources/${reader.id}/ingest`,
        {
          method: "POST",
          body: JSON.stringify({ force: false, reextract: false }),
        },
      );
      setSources((ss) => ss.map((s) => (s.id === source.id ? source : s)));
      setReader((current) => (current ? { ...current, ...source } : null));
      if (isSourceReady(source))
        setSelected((ids) => [...new Set([...ids, source.id])]);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  const ready = sources.filter((s) => isSourceReady(s));
  if (loading || !notebook)
    return (
      <>
        <header className="topbar">
          <Brand />
          <Avatar />
        </header>
        <main className="home">
          <Link href="/" className="back-link">
            <ArrowLeft size={16} /> All notebooks
          </Link>
          {loading ? (
            <p role="status">Opening notebook…</p>
          ) : (
            <div role="alert" className="error-panel">
              <p>{error}</p>
              <button className="secondary" onClick={load}>
                Try again
              </button>
            </div>
          )}
        </main>
      </>
    );
  return (
    <div className="workspace-shell">
      <header className="topbar notebook-topbar">
        <div className="title-left">
          <Link href="/" className="icon-button" aria-label="All notebooks">
            <ArrowLeft size={21} />
          </Link>
          <span className="notebook-header-icon">
            <BookOpen size={24} />
          </span>
          <h1>{notebook.title}</h1>
          <button
            className="icon-button"
            aria-label="Rename notebook"
            onClick={() => {
              setTitle(notebook.title);
              setEditing(true);
            }}
          >
            <Pencil size={17} />
          </button>
        </div>
        <div className="account">
          <Link className="header-link" href="/">
            <Plus size={20} /> Notebooks
          </Link>
          <button
            className="icon-button danger"
            aria-label="Delete notebook"
            onClick={() => setDeleting("notebook")}
          >
            <Trash2 size={18} />
          </button>
          <Avatar />
        </div>
      </header>
      {error && (
        <div className="workspace-error" role="alert">
          {error}
          <button
            className="icon-button"
            aria-label="Dismiss error"
            onClick={() => setError("")}
          >
            <X size={16} />
          </button>
        </div>
      )}
      <main className="workspace">
        <aside className="sources-panel panel">
          <div className="panel-heading">
            <h2>
              <BookOpen size={17} /> Sources
            </h2>
            <span className="count">{sources.length}</span>
          </div>
          <div className="sources-inner">
            <button className="secondary full" onClick={() => setAdding(true)}>
              <Plus size={17} /> Add sources
            </button>
            {sources.length > 0 && (
              <label className="select-all">
                <input
                  type="checkbox"
                  checked={ready.length > 0 && selected.length === ready.length}
                  disabled={!ready.length}
                  onChange={(e) =>
                    setSelected(e.target.checked ? ready.map((s) => s.id) : [])
                  }
                />{" "}
                Select all sources
              </label>
            )}
            <div className="source-list">
              {sources.map((source) => (
                <div
                  className={`source-row ${reader?.id === source.id ? "active" : ""}`}
                  key={source.id}
                >
                  <input
                    type="checkbox"
                    aria-label={`Select ${source.title}`}
                    disabled={!isSourceReady(source)}
                    checked={selected.includes(source.id)}
                    onChange={(e) =>
                      setSelected((ids) =>
                        e.target.checked
                          ? [...ids, source.id]
                          : ids.filter((i) => i !== source.id),
                      )
                    }
                  />
                  <button
                    className="source-open"
                    onClick={() => openSource(source.id)}
                  >
                    {source.kind === "image" ? (
                      <ImageIcon size={19} />
                    ) : (
                      <FileText size={19} />
                    )}
                    <span>
                      <strong>{source.title}</strong>
                      <small>
                        {source.status === "needs_text"
                          ? "Needs transcription"
                          : source.index_status === "failed"
                            ? "Indexing failed · open to retry"
                            : source.index_status === "pending"
                              ? "Needs indexing"
                              : source.kind.toUpperCase()}
                      </small>
                    </span>
                  </button>
                  <button
                    className="icon-button source-delete"
                    aria-label={`Delete ${source.title}`}
                    onClick={() => setDeleting(source)}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
            {!sources.length && (
              <div className="empty-sources">
                <div className="empty-icon">
                  <FileText size={26} strokeWidth={1.3} />
                </div>
                <h3>Saved sources will appear here</h3>
                <p>
                  Add files or paste text. Then ask questions based on those
                  sources.
                </p>
              </div>
            )}
          </div>
          <div className="source-foot">
            <Check size={14} />
            <span>Questions use only selected sources</span>
          </div>
        </aside>
        <section className="chat-panel panel" aria-label="Notebook chat">
          <div className="panel-heading">
            <h2>
              <MessageSquare size={17} /> Chat
            </h2>
            <span className="mode-tag">Source-grounded chat</span>
          </div>
          <div className="chat-scroll" aria-live="polite">
            {!questions.length && (
              <div className="chat-welcome">
                <span className="welcome-icon" aria-hidden="true">
                  {sources.length ? "📚" : "👋"}
                </span>
                <h2>
                  {sources.length
                    ? notebook.title
                    : "Let’s start your notebook."}
                </h2>
                {sources.length > 0 && (
                  <p className="notebook-meta">
                    {sources.length}{" "}
                    {sources.length === 1 ? "source" : "sources"} ·{" "}
                    {new Date(notebook.created_at).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </p>
                )}
                <p>
                  {sources.length
                    ? notebook.description ||
                      "Your sources are ready to explore. Select the ones you want to use, then ask a question to find relevant passages and their original context."
                    : "This is your space to understand, learn, and connect ideas. Start by adding your documents or notes."}
                </p>
                <h3>
                  {sources.length
                    ? "What would you like to understand?"
                    : "What would you like to explore?"}
                </h3>
                <div className="welcome-actions">
                  <button className="secondary" onClick={() => setAdding(true)}>
                    <Plus size={18} />
                    {sources.length
                      ? "Add another source"
                      : "Add your first source"}
                  </button>
                  {sources.length > 0 && (
                    <span>
                      Select sources on the left to focus your questions.
                    </span>
                  )}
                </div>
              </div>
            )}
            {questions.map((q) => (
              <article className="exchange" key={q.id}>
                <div className="user-question">{q.question}</div>
                <div className="answer-heading">
                  <span className="mini-mark">
                    <Sparkles size={14} />
                  </span>{" "}
                  NotebookAI{" "}
                  <span>
                    · {q.mode === "rag" ? "AI answer" : "Cited passages"}
                  </span>
                </div>
                <p className="answer-text">{q.answer}</p>
                <div className="citations">
                  {q.citations.map((c, index) => (
                    <button
                      key={`${c.source_id}-${index}`}
                      className="citation"
                      onClick={() => openSource(c.source_id)}
                      title={c.excerpt}
                    >
                      <span>{index + 1}</span>
                      {c.source_title}
                      <small>{c.location}</small>
                    </button>
                  ))}
                </div>
              </article>
            ))}
            {asking && (
              <p className="thinking" role="status">
                <Sparkles size={15} /> Searching sources and composing an
                answer…
              </p>
            )}
            <div ref={bottom} />
          </div>
          <div className="composer-wrap">
            <form className="composer" onSubmit={ask}>
              <textarea
                aria-label="Ask a question"
                rows={2}
                maxLength={2000}
                placeholder={
                  selected.length
                    ? "What would you like to understand?"
                    : "Add and select a source to begin…"
                }
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                disabled={!selected.length || asking}
              />
              <div className="composer-bottom">
                <span>
                  {selected.length}{" "}
                  {selected.length === 1 ? "source" : "sources"} selected
                </span>
                <button
                  className="send-button"
                  aria-label="Send question"
                  disabled={!selected.length || !question.trim() || asking}
                >
                  <ArrowUp size={20} />
                </button>
              </div>
            </form>
            <p className="composer-note">
              Answers use your selected sources. Follow citations to check the
              evidence.
            </p>
          </div>
        </section>
        <aside className="reader-panel panel" aria-label="Source reader">
          <div className="panel-heading">
            <h2>
              <FileText size={17} /> Source guide
            </h2>
            {reader && (
              <button
                className="icon-button"
                aria-label="Close source"
                onClick={() => {
                  ++readVersion.current;
                  setReading(false);
                  setReader(null);
                }}
              >
                <X size={16} />
              </button>
            )}
          </div>
          {reading ? (
            <p className="reader-content" role="status">
              Opening source…
            </p>
          ) : reader ? (
            <div className="reader-content">
              <span className="eyebrow">{reader.kind.toUpperCase()}</span>
              <h3>{reader.title}</h3>
              <a
                className="file-link"
                href={sourceFileUrl(id, reader.id)}
                target="_blank"
                rel="noreferrer"
              >
                Open original <ExternalLink size={13} />
              </a>
              {reader.status === "ready" && !isSourceReady(reader) && (
                <div className="notice">
                  <p>
                    {reader.index_error ||
                      "Index this source to use it in questions."}
                  </p>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={retryIngestion}
                  >
                    {busy ? "Indexing…" : "Retry indexing"}
                  </button>
                </div>
              )}
              {reader.status === "needs_text" ? (
                <form onSubmit={saveTranscription}>
                  <div className="notice">
                    This source needs a transcription. Paste its text below to
                    include it in questions.
                  </div>
                  <label>
                    Transcription
                    <textarea
                      required
                      maxLength={200000}
                      value={transcription}
                      onChange={(e) => setTranscription(e.target.value)}
                      rows={10}
                    />
                  </label>
                  <button
                    className="primary full"
                    disabled={busy || !transcription.trim()}
                  >
                    {busy ? "Saving…" : "Save transcription"}
                  </button>
                </form>
              ) : (
                reader.segments.map((segment, index) => (
                  <section className="segment" key={index}>
                    <small>{segment.location}</small>
                    <p>{segment.text}</p>
                  </section>
                ))
              )}
            </div>
          ) : (
            <div className="reader-empty">
              <span className="reader-illustration">
                <BookOpen size={42} strokeWidth={1} />
              </span>
              <h3>Explore your sources</h3>
              <p>
                Open a source or follow a citation to read the original context.
              </p>
              <div className="reader-tip">
                <Sparkles size={16} />
                <p>
                  Ask a specific question and select the sources you want to
                  explore.
                </p>
              </div>
            </div>
          )}
        </aside>
      </main>
      {adding && (
        <AddSource
          notebookId={id}
          onClose={() => setAdding(false)}
          onAdded={(source) => {
            setSources((ss) => [...ss, source]);
            if (isSourceReady(source))
              setSelected((ids) => [...ids, source.id]);
            else void openSource(source.id);
          }}
        />
      )}
      {editing && (
        <Dialog
          title="Rename notebook"
          onClose={() => {
            if (!busy) setEditing(false);
          }}
        >
          <form onSubmit={rename}>
            <label>
              Name
              <input
                required
                autoFocus
                maxLength={160}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            <button className="primary full" disabled={busy || !title.trim()}>
              Save changes
            </button>
          </form>
        </Dialog>
      )}
      {deleting && (
        <Dialog
          title={
            deleting === "notebook" ? "Delete notebook?" : "Delete source?"
          }
          onClose={() => {
            if (!busy) setDeleting(null);
          }}
        >
          <p>
            {deleting === "notebook"
              ? "This permanently deletes the notebook, its sources, and question history."
              : `Remove “${deleting.title}”? Previous answers keep their quoted passages, but this source will no longer open.`}
          </p>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <div className="dialog-actions">
            <button
              className="secondary"
              disabled={busy}
              onClick={() => setDeleting(null)}
            >
              Keep it
            </button>
            <button
              className="primary destructive"
              disabled={busy}
              onClick={remove}
            >
              {busy ? "Deleting…" : "Delete"}
            </button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
