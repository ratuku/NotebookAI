import { test, expect } from "@playwright/test";
test("create, upload, ask, follow citation, reload, and delete", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Create a notebook", exact: true })
    .click();
  await page.getByLabel("Notebook name").fill(`Research ${Date.now()}`);
  await page
    .getByRole("button", { name: "Create notebook", exact: true })
    .click();
  await expect(page).toHaveURL(/\/notebooks\//);
  const id = page.url().split("/").pop();
  try {
    await page
      .getByRole("button", { name: "Add sources", exact: true })
      .click();
    await page
      .getByLabel("Source file")
      .setInputFiles({
        name: "biology.txt",
        mimeType: "text/plain",
        buffer: Buffer.from(
          "Plants convert sunlight into energy through photosynthesis.",
        ),
      });
    await page.getByRole("button", { name: "Add source", exact: true }).click();
    await expect(
      page.getByRole("checkbox", { name: "Select biology.txt" }),
    ).toBeChecked();
    await page
      .getByRole("textbox", { name: "Ask a question" })
      .fill("How does photosynthesis use sunlight?");
    await page.getByRole("button", { name: "Send question" }).click();
    await expect(page.locator(".answer-text")).toContainText(
      "Plants convert sunlight",
    );
    await page
      .getByRole("button", { name: /biology.txt.*Paragraph 1/ })
      .click();
    await expect(
      page
        .getByRole("complementary", { name: "Source reader" })
        .getByText(
          "Plants convert sunlight into energy through photosynthesis.",
          { exact: true },
        ),
    ).toBeVisible();
    await page.reload();
    await expect(page.locator(".answer-text")).toContainText(
      "Plants convert sunlight",
    );
    await page.getByRole("checkbox", { name: "Select biology.txt" }).uncheck();
    await expect(
      page.getByRole("button", { name: "Send question" }),
    ).toBeDisabled();
    await expect(
      page.getByRole("textbox", { name: "Ask a question" }),
    ).toBeDisabled();
    await page
      .getByRole("button", { name: "Delete notebook", exact: true })
      .click();
    await page.getByRole("button", { name: "Delete", exact: true }).click();
    await expect(page).toHaveURL("http://localhost:3000/");
  } finally {
    await page.request.delete(`http://localhost:8000/api/v1/notebooks/${id}`);
  }
});
