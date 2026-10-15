# Artifacts and retrieval comparison

## Two retrieval methods

`POST /api/v1/notebooks/{id}/questions` accepts `retrieval_method`:

| Value | Process |
| --- | --- |
| `normal` (default) | Dense search + BM25, reciprocal rank fusion, diversity selection and deduplication; take top-k. |
| `reranking` | Build the same candidate pool (up to 30), ask Groq to score each passage's relevance to the question, sort by score, then take top-k. |

This compares the existing hybrid baseline with **LLM reranking**. It is not a cross-encoder or a pure vector-only baseline. Both methods share embeddings, source/version filters, candidate construction, top-k, answer model and citation validation. Reranking adds one Groq call and can increase cost/latency. It must return each candidate ID exactly once; duplicates, missing/foreign IDs and provider failures produce an error rather than silently switching methods. Equal relevance scores preserve supplied order. `AI_MODE=extractive` supports only `normal` and is not part of the RAG comparison.

```json
{
  "question": "How do plants convert sunlight into energy?",
  "source_ids": ["SOURCE_ID"],
  "retrieval_method": "reranking"
}
```

The frontend selector appears above the question box. Every saved answer includes its method label, retained after reload. To compare fairly, submit exactly the same questions with the same sources using each mode; do not edit/reindex sources between runs. Judge answer correctness, citation support, missing relevant facts and latency across a fixed set of questions. Include paraphrases, exact identifiers, distractor passages and unanswerable questions. Do not infer a quality improvement from the technique name alone. The tests establish algorithm selection and isolation, not real-world superiority.

## Reports and quizzes

Use **Reports & quizzes** in the notebook header. Select indexed sources, choose the retrieval method, enter a topic/learning objective, and choose Report or Quiz + answer key. Quizzes support 3–10 short-answer questions. Generated items are saved and can be reopened after refreshing the notebook.

The generator retrieves topic-relevant evidence and calls Groq with a strict schema. Reports contain titled sections with cited claims. Quizzes contain distinct questions and model answers, each with supporting citations. Insufficient evidence, invalid citation IDs or an incorrect question count fail without saving an artifact. Reports cover retrieved passages; they do not promise exhaustive coverage of all uploaded content. Citation checks enforce provenance, not logical entailment: review factual claims and answer keys against the supplied excerpts.

Downloads:

- Markdown (`.md`) with headings, question numbering, a separate answer-key section and evidence appendix.
- Printable HTML (`.html`) with readable typography and print styles. Open the downloaded file in a browser and print/save to PDF if needed. There is no native PDF exporter.

Model text is escaped in both formats. HTML cannot execute model-generated markup/scripts. Citations retain source title, page/slide/paragraph, excerpt, chunk ID and version, so downloads survive source edits or deletion. Notebook deletion removes its artifacts.

## API

All paths below start with `/api/v1/notebooks/{notebook_id}`.

| Method | Path | Result |
| --- | --- | --- |
| POST | `/artifacts` | Generate and save an artifact (201). |
| GET | `/artifacts` | Saved artifacts, newest first, including structured content/citations. |
| GET | `/artifacts/{id}/download?format=markdown` | Markdown attachment (default). |
| GET | `/artifacts/{id}/download?format=html` | Printable HTML attachment. |
| DELETE | `/artifacts/{id}` | Delete one artifact (204). |

Example generation body:

```json
{
  "kind": "quiz",
  "topic": "Photosynthesis and energy conversion",
  "question_count": 5,
  "source_ids": ["SOURCE_ID"],
  "retrieval_method": "reranking"
}
```

For reports set `kind` to `report`; `question_count` is ignored. Authentication remains the existing shared admin scope. Cross-notebook source or artifact IDs are rejected. Generation requires RAG mode and a configured Groq key. Failed source indexing returns 409; provider/grounding-validation failures return 503 with a retryable message. Generation is synchronous.

Schema migration `2d519c617a30` adds artifacts and saved question retrieval methods. Existing answers are labelled `normal` because they used the original hybrid pipeline. The implementation uses [Groq structured outputs](https://console.groq.com/docs/structured-outputs); schema compliance does not itself ensure factual accuracy.

## Retrieval measurements

RAG question and artifact responses include `retrieval_stats`, persisted with the result and displayed beneath answers/previews:

```json
{
  "chunks_found": 20,
  "candidates_count": 15,
  "chunks_selected": 6,
  "retrieval_ms": 1234.0,
  "reranking_ms": 800.0
}
```

These numbers are illustrative, not benchmark results.

- `chunks_found`: distinct chunk IDs in the union of dense and BM25 candidate lists, before text deduplication. Each list is capped at 30, so this is at most 60; it is not a count of every potentially relevant chunk in the database.
- `candidates_count`: the capped, deduplicated pool after fusion/diversity selection, at most 30. Reranking scores this pool.
- `chunks_selected`: final passages sent to generation, at most configured top-k. Citations may reference only some of them.
- `retrieval_ms`: monotonic elapsed time for embedding, search, fusion and optional reranking, measured after acquiring the pipeline lock. Excludes database/lock waiting, answer generation, persistence and browser network time.
- `reranking_ms`: reranker call plus response validation/ordering; a subset of retrieval time, zero for normal retrieval or no candidates.

Cold model loading is included when it occurs. Compare warm runs on the same sources/configuration and repeat measurements; network/provider load affects reranking. Chunk counts and latency complement correctness/citation-support evaluation, not replace it. Historical and extractive-mode results have `retrieval_stats: null` instead of invented zero timings.
