import { expect, test } from "@playwright/test";
import { pinClock, resetDb } from "./support/app";

/* auth0-users — a new user before setup (home status `not_set_up`): the
   snapshot invites the setup chat and analyzes nothing. */

test.beforeAll(() => {
  resetDb({ fresh: true });
});

test.beforeEach(async ({ page }) => {
  await pinClock(page);
});

test("a new user is invited to the setup chat, with no analysis", async ({ page }) => {
  await page.goto("/");
  const snapshot = page.getByTestId("snapshot-message");
  await expect(snapshot.getByTestId("setup-invitation")).toBeVisible();
  await expect(snapshot).toContainText("Let's set up your budget");
  await expect(snapshot).not.toContainText("I've updated your month");
  await expect(snapshot).not.toContainText("€");
  // The snapshot is the invitation; the nudge would repeat it.
  await expect(page.getByText("Finish setting up")).toHaveCount(0);

  await snapshot.getByRole("link", { name: "Start the setup chat" }).click();
  await expect(page).toHaveURL(/\/onboarding$/);
});
