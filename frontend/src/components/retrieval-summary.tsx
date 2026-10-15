import type { RetrievalStats } from "@/lib/api";
export function RetrievalSummary({ stats }: { stats?: RetrievalStats | null }) {
  if (!stats) return null;
  return (
    <details className="retrieval-summary">
      <summary>
        {stats.chunks_found} chunks found · {stats.chunks_selected} selected ·{" "}
        {(stats.retrieval_ms / 1000).toFixed(3)} s retrieval
      </summary>
      <p>
        {stats.candidates_count} unique-text candidates kept after filtering and
        deduplication. Reranking: {(stats.reranking_ms / 1000).toFixed(3)} s.
      </p>
      <p>
        Retrieval includes question embedding, search, fusion and optional
        reranking. It excludes answer generation, database waits and network
        time to your browser. First-use model loading can make retrieval slower.
        More chunks do not necessarily mean a better answer.
      </p>
    </details>
  );
}
