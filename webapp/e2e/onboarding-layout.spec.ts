import { expect, test, type Page } from "@playwright/test";

/* auth0-users 2.9 — the onboarding screen's layout, with the interview's
   API answered in the browser (the onboarding route has no e2e fake model):
   1. the chat fills the viewport, so after each answer the newest message and
      the answer options stay in view;
   2. the review screen opens at its top. */

type Entry = { role: "user" | "assistant"; content: string; input_kind?: string; options?: string[]; done?: boolean };

const history: Entry[] = Array.from({ length: 12 }, (_, i) => [
  { role: "assistant" as const, content: `Question ${i + 1}: tell me a bit more about your money.` },
  { role: "user" as const, content: `Answer ${i + 1}` },
]).flat();

const question = (n: number): Entry => ({
  role: "assistant",
  content: `Question ${n}: do you have a car?`,
  input_kind: "chips",
  options: ["Yes", "No"],
});

const proposal = {
  accounts: [{ name: "BBVA", type: "bank" }],
  category_groups: Array.from({ length: 8 }, (_, g) => ({
    name: `Group ${g + 1}`,
    categories: Array.from({ length: 5 }, (_, c) => ({ name: `Category ${g + 1}.${c + 1}`, icon: "tag" })),
  })),
  payers: ["Empresa"],
  payees: ["Netflix"],
  income: [],
};

const session = (transcript: Entry[], withProposal = false) => ({
  id: "s1",
  status: "active",
  prompt_version: "e2e",
  transcript,
  proposal: withProposal ? proposal : null,
});

async function mockInterview(page: Page) {
  let transcript = [...history, question(13)];
  let answers = 0;
  await page.route("**/api/onboarding/session", (route) => route.fulfill({ json: session(transcript) }));
  await page.route("**/api/onboarding/messages", async (route) => {
    const { message } = route.request().postDataJSON() as { message: string };
    answers += 1;
    if (answers === 1) {
      transcript = [...transcript, { role: "user", content: message }, question(14)];
      await route.fulfill({ json: session(transcript) });
    } else {
      transcript = [...transcript, { role: "user", content: message }, { role: "assistant", content: "All set.", done: true }];
      await route.fulfill({ json: session(transcript, true) });
    }
  });
}

test.use({ viewport: { width: 390, height: 720 } });

test("the newest message and the options stay in view, and the review opens at its top", async ({ page }) => {
  await mockInterview(page);
  await page.goto("/onboarding");

  await expect(page.getByText("Question 13: do you have a car?")).toBeInViewport();
  await expect(page.getByRole("button", { name: "Yes" })).toBeInViewport();
  await expect(page.getByPlaceholder("Type your answer…")).toBeInViewport();

  await page.getByRole("button", { name: "Yes" }).click();
  await expect(page.getByText("Question 14: do you have a car?")).toBeInViewport();
  await expect(page.getByRole("button", { name: "No" })).toBeInViewport();
  await expect(page.getByPlaceholder("Type your answer…")).toBeInViewport();

  await page.getByRole("button", { name: "No" }).click();
  await expect(page.getByRole("heading", { name: "Review your setup" })).toBeInViewport();
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
});
