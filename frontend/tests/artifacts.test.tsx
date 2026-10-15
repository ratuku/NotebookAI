import { beforeEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Artifacts } from "../src/components/artifacts";
const mocks = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("@/lib/api", async (original) => ({
  ...(await original<object>()),
  request: mocks.request,
}));
beforeEach(() => mocks.request.mockReset());
it("generates a quiz with selected sources and retrieval method, then offers downloads and evidence", async () => {
  mocks.request
    .mockResolvedValueOnce([])
    .mockResolvedValueOnce({
      id: "quiz1",
      title: "Plant quiz",
      kind: "quiz",
      retrieval_method: "reranking",
      citations: [
        {
          chunk_id: "c1",
          source_title: "Botany",
          location: "Page 1",
          excerpt: "Plants use sunlight.",
        },
      ],
      content: {
        questions: [
          {
            question: "What do plants use?",
            answer: { text: "Sunlight.", citations: ["c1"] },
          },
        ],
      },
    });
  render(<Artifacts notebookId="n1" sourceIds={["s1"]} method="reranking" />);
  await screen.findByText("No artifacts yet.");
  fireEvent.change(screen.getByLabelText("Artifact type"), {
    target: { value: "quiz" },
  });
  fireEvent.change(screen.getByLabelText("Topic or learning objective"), {
    target: { value: "Photosynthesis" },
  });
  fireEvent.change(screen.getByLabelText("Number of questions"), {
    target: { value: "3" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Generate artifact" }));
  expect(
    await screen.findByRole("heading", { name: "Plant quiz" }),
  ).toBeInTheDocument();
  expect(JSON.parse(mocks.request.mock.calls[1][1].body)).toMatchObject({
    kind: "quiz",
    topic: "Photosynthesis",
    question_count: 3,
    source_ids: ["s1"],
    retrieval_method: "reranking",
  });
  expect(
    screen.getByRole("link", { name: "Download printable HTML" }),
  ).toHaveAttribute(
    "href",
    expect.stringContaining("/artifacts/quiz1/download?format=html"),
  );
  expect(screen.getByText("Answer key")).toBeInTheDocument();
  expect(screen.getByText("[1] Botany · Page 1")).toBeInTheDocument();
});
it("keeps generation errors visible and offers no invented download", async () => {
  mocks.request
    .mockResolvedValueOnce([])
    .mockRejectedValueOnce(new Error("Not enough source evidence"));
  render(<Artifacts notebookId="n1" sourceIds={["s1"]} method="normal" />);
  await screen.findByText("No artifacts yet.");
  fireEvent.change(screen.getByLabelText("Topic or learning objective"), {
    target: { value: "Unknown" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Generate artifact" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Not enough source evidence",
  );
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Generate artifact" }),
    ).toBeEnabled(),
  );
  expect(
    screen.queryByRole("link", { name: /Download/ }),
  ).not.toBeInTheDocument();
});
