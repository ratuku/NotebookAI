import { beforeEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import Home from "../src/app/page";
const mocks = vi.hoisted(() => ({ request: vi.fn(), push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  request: mocks.request,
}));
beforeEach(() => {
  mocks.request.mockReset();
  mocks.push.mockReset();
});
it("filters notebooks and links to their workspaces", async () => {
  mocks.request.mockResolvedValue([
    {
      id: "one",
      title: "Botany",
      description: "Plants",
      source_count: 2,
      created_at: "2026-01-01",
    },
    {
      id: "two",
      title: "Music",
      description: "",
      source_count: 0,
      created_at: "2026-01-01",
    },
  ]);
  render(<Home />);
  expect(await screen.findByRole("link", { name: /Botany/ })).toHaveAttribute(
    "href",
    "/notebooks/one",
  );
  fireEvent.change(screen.getByRole("textbox", { name: "Search notebooks" }), {
    target: { value: "plants" },
  });
  expect(screen.queryByRole("link", { name: /Music/ })).not.toBeInTheDocument();
});
it("creates a notebook and navigates to it", async () => {
  mocks.request
    .mockResolvedValueOnce([])
    .mockResolvedValueOnce({ id: "created" });
  render(<Home />);
  await screen.findByText(/Your library is a blank page/);
  fireEvent.click(screen.getByRole("button", { name: "Create a notebook" }));
  fireEvent.change(screen.getByLabelText("Notebook name"), {
    target: { value: "New research" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create notebook" }));
  await waitFor(() =>
    expect(mocks.push).toHaveBeenCalledWith("/notebooks/created"),
  );
  expect(JSON.parse(mocks.request.mock.calls[1][1].body).title).toBe(
    "New research",
  );
});
it("shows a recoverable loading error", async () => {
  mocks.request
    .mockRejectedValueOnce(new Error("Server offline"))
    .mockResolvedValueOnce([]);
  render(<Home />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Server offline");
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  await screen.findByText(/Your library is a blank page/);
});
