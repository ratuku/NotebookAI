import Link from "next/link";
import { BookOpen } from "lucide-react";
export function Brand() {
  return (
    <Link className="brand" href="/" aria-label="NotebookAI home">
      <span className="brand-mark">
        <BookOpen size={21} strokeWidth={1.8} />
      </span>
      <span>
        Notebook<span className="brand-light">AI</span>
      </span>
    </Link>
  );
}
export function Avatar() {
  return (
    <span
      className="avatar"
      title="Local admin account"
      aria-label="Admin account"
    >
      A
    </span>
  );
}
