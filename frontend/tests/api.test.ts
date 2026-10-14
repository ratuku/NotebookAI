import { afterEach, expect, it, vi } from "vitest";
import { request } from "../src/lib/api";
afterEach(() => vi.unstubAllGlobals());
it("surfaces backend validation messages", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ detail: "Files must be 10 MB or smaller." }),
          { status: 413 },
        ),
      ),
  );
  await expect(request("/notebooks")).rejects.toThrow(
    "Files must be 10 MB or smaller.",
  );
});
it("gives a useful connection error", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
  );
  await expect(request("/notebooks")).rejects.toThrow(
    "Cannot reach the server",
  );
});
it("does not set multipart headers, so the browser supplies its boundary", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response("{}"));
  vi.stubGlobal("fetch", fetch);
  const body = new FormData();
  body.append("file", new Blob(["text"]));
  await request("/notebooks/1/sources/upload", { method: "POST", body });
  expect(fetch.mock.calls[0][1].headers).not.toHaveProperty("Content-Type");
});
it("accepts an empty delete response", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
  );
  await expect(
    request("/notebooks/1", { method: "DELETE" }),
  ).resolves.toBeUndefined();
});
