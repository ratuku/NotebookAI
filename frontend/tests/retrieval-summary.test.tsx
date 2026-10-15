import { expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RetrievalSummary } from "../src/components/retrieval-summary";
it("distinguishes matched chunks, selected evidence and retrieval time", () => {
  render(
    <RetrievalSummary
      stats={{
        chunks_found: 20,
        candidates_count: 15,
        chunks_selected: 6,
        retrieval_ms: 1234,
        reranking_ms: 800,
      }}
    />,
  );
  expect(
    screen.getByText("20 chunks found · 6 selected · 1.234 s retrieval"),
  ).toBeInTheDocument();
  expect(screen.getByText(/15 unique-text candidates/)).toHaveTextContent(
    "0.800 s",
  );
});
it("does not invent timings for historical answers", () => {
  const { container } = render(<RetrievalSummary stats={null} />);
  expect(container).toBeEmptyDOMElement();
});
