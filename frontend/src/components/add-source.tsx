"use client";
import { useState, type FormEvent } from "react";
import { Upload, FileText, Plus, Link as LinkIcon } from "lucide-react";
import { Dialog } from "./dialog";
import { request, notebookPath, message, type Source } from "@/lib/api";
export function AddSource({
  notebookId,
  onClose,
  onAdded,
}: {
  notebookId: string;
  onClose: () => void;
  onAdded: (source: Source) => void;
}) {
  const [tab, setTab] = useState<"file" | "text" | "url">("file");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      let source: Source;
      if (tab === "text")
        source = await request<Source>(
          `${notebookPath(notebookId)}/sources/text`,
          { method: "POST", body: JSON.stringify({ title, text }) },
        );
      else if (tab === "url")
        source = await request<Source>(
          `${notebookPath(notebookId)}/sources/url`,
          { method: "POST", body: JSON.stringify({ url }) },
        );
      else {
        if (!file) throw new Error("Choose a file first.");
        if (file.size > 10 * 1024 * 1024)
          throw new Error("Files must be 10 MB or smaller.");
        const form = new FormData();
        form.append("file", file);
        source = await request<Source>(
          `${notebookPath(notebookId)}/sources/upload`,
          { method: "POST", body: form },
        );
      }
      onAdded(source);
      onClose();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title="Add a source"
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <p className="muted">Give your notebook something to think with.</p>
      <div className="tabs">
        <button
          aria-pressed={tab === "file"}
          onClick={() => setTab("file")}
          disabled={busy}
        >
          <Upload size={16} /> Upload a file
        </button>
        <button
          aria-pressed={tab === "text"}
          onClick={() => setTab("text")}
          disabled={busy}
        >
          <FileText size={16} /> Paste text
        </button>
        <button
          aria-pressed={tab === "url"}
          onClick={() => setTab("url")}
          disabled={busy}
        >
          <LinkIcon size={16} /> Website
        </button>
      </div>
      <form onSubmit={submit}>
        {tab === "file" ? (
          <>
            <label className="upload-zone">
              <Upload size={30} />
              <strong>{file ? file.name : "Choose a source file"}</strong>
              <span>PDF, PPTX, TXT, PNG, JPG, or WEBP · Up to 10 MB</span>
              <input
                aria-label="Source file"
                type="file"
                accept=".pdf,.pptx,.txt,.png,.jpg,.jpeg,.webp"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </label>
            <p className="hint">
              Images and scanned PDFs need a text transcription before you can
              ask questions.
            </p>
          </>
        ) : tab === "url" ? (
          <label>
            Page URL
            <input
              required
              type="url"
              maxLength={2048}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/article"
            />
            <p className="hint">
              Imports this page only. Pages requiring sign-in or JavaScript may
              not contain readable text.
            </p>
          </label>
        ) : (
          <>
            <label>
              Source title
              <input
                autoFocus
                required
                maxLength={160}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Research notes"
              />
            </label>
            <label>
              Source text
              <textarea
                required
                maxLength={200000}
                rows={8}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste your notes, article, or reference text here…"
              />
            </label>
          </>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <button
          className="primary full"
          disabled={
            busy ||
            (tab === "file"
              ? !file
              : tab === "url"
                ? !url.trim()
                : !title.trim() || !text.trim())
          }
        >
          <Plus size={17} />
          {busy ? "Extracting and indexing…" : "Add source"}
        </button>
      </form>
    </Dialog>
  );
}
