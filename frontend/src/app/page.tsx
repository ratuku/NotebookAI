"use client";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  Plus,
  Search,
  ArrowUpRight,
  BookOpen,
  ArrowRight,
  Library,
  LayoutGrid,
  List,
} from "lucide-react";
import { Brand, Avatar } from "@/components/brand";
import { Dialog } from "@/components/dialog";
import { request, message, type Notebook } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [view, setView] = useState<"grid" | "list">("grid");
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  async function load() {
    setLoading(true);
    setError("");
    try {
      setNotebooks(await request<Notebook[]>("/notebooks"));
    } catch (e) {
      setError(message(e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFormError("");
    try {
      const notebook = await request<Notebook>("/notebooks", {
        method: "POST",
        body: JSON.stringify({ title, description }),
      });
      router.push(`/notebooks/${notebook.id}`);
    } catch (e) {
      setFormError(message(e));
      setBusy(false);
    }
  }
  const filtered = notebooks.filter((n) =>
    `${n.title} ${n.description}`.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <header className="topbar library-topbar">
        <Brand />
        <div className="library-tools">
          <label className="search">
            <Search size={20} />
            <input
              aria-label="Search notebooks"
              placeholder="Search notebooks"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          <div className="view-toggle" role="group" aria-label="Notebook view">
            <button
              aria-label="Grid view"
              aria-pressed={view === "grid"}
              onClick={() => setView("grid")}
            >
              <LayoutGrid size={20} />
            </button>
            <button
              aria-label="List view"
              aria-pressed={view === "list"}
              onClick={() => setView("list")}
            >
              <List size={21} />
            </button>
          </div>
          <Avatar />
        </div>
      </header>
      <main className="home">
        <section aria-labelledby="notebooks-heading" className="library">
          <div className="section-heading">
            <div>
              <h1 id="notebooks-heading">Recent notebooks</h1>
              <p>All your sources. A place to make sense of them.</p>
            </div>
            <button
              className="primary"
              aria-label="Create a notebook"
              onClick={() => setCreating(true)}
            >
              <Plus size={21} /> New notebook
            </button>
          </div>
          {error ? (
            <div className="error-panel" role="alert">
              <p>{error}</p>
              <button className="secondary" onClick={load}>
                Try again
              </button>
            </div>
          ) : loading ? (
            <div className="loading" role="status">
              Opening your library…
            </div>
          ) : (
            <div
              className={view === "grid" ? "notebook-grid" : "notebook-list"}
            >
              {filtered.map((notebook) => (
                <Link
                  href={`/notebooks/${notebook.id}`}
                  key={notebook.id}
                  className="notebook-card"
                >
                  <div className="card-top">
                    <span className="notebook-symbol">
                      <BookOpen size={34} strokeWidth={1.6} />
                    </span>
                    <ArrowUpRight size={20} />
                  </div>
                  <div className="card-copy">
                    <h2>{notebook.title}</h2>
                    {notebook.description && <p>{notebook.description}</p>}
                    <div className="card-bottom">
                      <span>
                        {new Date(notebook.created_at).toLocaleDateString(
                          "en-US",
                          { month: "short", day: "numeric", year: "numeric" },
                        )}
                      </span>
                      <span>·</span>
                      <span>
                        {notebook.source_count}{" "}
                        {notebook.source_count === 1 ? "source" : "sources"}
                      </span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
          {!loading && !error && search && !filtered.length && (
            <p className="muted no-results">No notebooks match “{search}”.</p>
          )}
          {!loading && !error && !notebooks.length && (
            <div className="first-note">
              <span className="empty-library-icon">
                <Library size={36} strokeWidth={1.4} />
              </span>
              <h2>Your ideas start here</h2>
              <p>
                Your library is a blank page. Add your first notebook to make it
                yours.
              </p>
              <p>
                Bring together documents, research, and notes.
                <br />
                Then ask questions grounded in your sources.
              </p>
              <button className="secondary" onClick={() => setCreating(true)}>
                <Plus size={18} /> Create your first notebook
              </button>
            </div>
          )}
        </section>
        <footer className="home-footer">
          <span>NotebookAI</span>
          <span>Personal workspace · admin</span>
        </footer>
      </main>
      {creating && (
        <Dialog
          title="Create a notebook"
          onClose={() => {
            if (!busy) setCreating(false);
          }}
        >
          <form onSubmit={create}>
            <p className="muted">Give your next idea a place to grow.</p>
            <label>
              Notebook name
              <input
                autoFocus
                required
                maxLength={160}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. The science of better sleep"
              />
            </label>
            <label>
              Description <span className="muted">(optional)</span>
              <textarea
                maxLength={2000}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What are you exploring?"
                rows={3}
              />
            </label>
            {formError && (
              <p role="alert" className="error">
                {formError}
              </p>
            )}
            <button className="primary full" disabled={busy || !title.trim()}>
              {busy ? "Creating…" : "Create notebook"}
              <ArrowRight size={17} />
            </button>
          </form>
        </Dialog>
      )}
    </>
  );
}
