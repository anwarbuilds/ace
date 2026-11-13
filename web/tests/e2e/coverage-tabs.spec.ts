import { expect, type Page, type Route } from "@playwright/test";

import { test, watchErrors } from "./helpers";

// Coverage says in plain words what each tab is, and pasting a job always
// gets an answer. Every company here is fictional. The add box's answers are
// staged, because a real add reads a real board.
function answer(body: Record<string, unknown>) {
  return async (route: Route) => {
    if (route.request().method() !== "POST") return route.continue();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        company: null,
        source_type: "",
        source_account: "",
        job_count: 0,
        evidence: "",
        detail: "",
        job: null,
        linked: false,
        last_read_at: null,
        next_check_at: null,
        first_read_seconds: null,
        ...body,
      }),
    });
  };
}

async function paste(page: Page, text: string) {
  await page.getByLabel("Job link, careers page or company name").fill(text);
  await page.getByRole("button", { name: "Add", exact: true }).click();
}

test("each tab says what it is, and opens from the others", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/app/coverage");
  const tabs = page.getByRole("navigation", { name: "Coverage views" });
  await expect(tabs.getByRole("link", { name: "Scoreboard" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByText("How well is ace doing?")).toBeVisible();
  await expect(page.getByRole("heading", { name: "How ace finds jobs" })).toBeVisible();

  await tabs.getByRole("link", { name: /Leads/ }).click();
  await expect(page).toHaveURL(/tab=leads/);
  await expect(page.getByText("Which companies does ace know about?")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Found a job ace doesn’t have?" })).toBeVisible();

  await tabs.getByRole("link", { name: /Sources/ }).click();
  await expect(page).toHaveURL(/tab=sources/);
  await expect(page.getByText("Which job boards does ace really read, and are they working?")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Is ace allowed to read each site?" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("the Add button on any tab lands in the box, ready to paste", async ({ page }) => {
  await page.goto("/app/coverage?tab=sources");
  await page.getByRole("link", { name: "Add a job or company" }).click();
  await expect(page).toHaveURL(/tab=leads/);
  await expect(page.getByLabel("Job link, careers page or company name")).toBeVisible();
});

test("the ledger filters by status and search, in the URL, and explains itself", async ({ page }) => {
  await page.goto("/app/coverage?tab=leads");
  const ledger = page.locator("section", { has: page.getByRole("heading", { name: "All companies ace has heard of" }) });
  await expect(ledger.getByRole("row", { name: /Marlowe Robotics/ })).toContainText("Good board, left out");

  await ledger.getByRole("link", { name: /Site says no/ }).click();
  await expect(page).toHaveURL(/state=refused/);
  await expect(ledger.getByRole("row", { name: /Oakhollow/ })).toContainText("Robots file disallows");
  await expect(ledger.getByRole("row", { name: /Marlowe Robotics/ })).toHaveCount(0);

  await ledger.getByRole("link", { name: /^All/ }).click();
  await ledger.getByLabel("Find a company").fill("Tessellate");
  await ledger.getByRole("button", { name: "Find" }).click();
  await expect(page).toHaveURL(/q=Tessellate/);
  await expect(ledger.getByRole("row", { name: /Tessellate/ })).toBeVisible();
  await expect(ledger.getByRole("row", { name: /Oakhollow/ })).toHaveCount(0);

  await ledger.getByText("What do these statuses mean?").click();
  await expect(ledger.getByText("ace respects that. Check it by hand.")).toBeVisible();
});

test("what you added stays on record, and shows in Sources", async ({ page }) => {
  await page.goto("/app/coverage?tab=leads");
  const mine = page.locator("section", { has: page.getByRole("heading", { name: "Added by you" }) });
  await expect(mine.getByRole("row", { name: /Lumora Pay/ })).toContainText("14 jobs");
  await expect(mine.getByRole("row", { name: /Quillfeather/ })).toContainText("Teamtailor");

  await page.goto("/app/coverage?tab=sources&show=mine");
  const boards = page.locator("section", { has: page.getByRole("heading", { name: "All boards ace reads" }) });
  await expect(boards.getByRole("row", { name: /Lumora Pay/ })).toContainText("Added by you");
  await expect(boards.getByRole("row", { name: /Lumora Pay/ })).toContainText("Working");
  await expect(boards.getByRole("row")).toHaveCount(2);
});

test("Sources says in plain words whether ace keeps up", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/app/coverage?tab=sources");
  const box = page.locator("section", { has: page.getByRole("heading", { name: "Can ace keep up?" }) });
  await expect(box).toBeVisible();
  await expect(box.getByText("How much reading ace does, and how fast new jobs reach you.")).toBeVisible();
  await expect(box.getByText("Reads in the last hour")).toBeVisible();
  await expect(box.getByText(/Your boards ask for about [\d,]+ an hour/)).toBeVisible();
  await expect(box.getByText("Boards read on time")).toBeVisible();
  await expect(box.getByText(/^[\d,]+ of [\d,]+$/)).toBeVisible();
  await expect(box.getByText("New jobs reach you in")).toBeVisible();
  await expect(box.getByText(/^ace is (keeping up\.|behind: some boards are read later than planned\.)$/)).toBeVisible();
  expect(errors).toEqual([]);
});

test("Sources shows what stopped answering and which sites say no", async ({ page }) => {
  await page.goto("/app/coverage?tab=sources&show=dark");
  const boards = page.locator("section", { has: page.getByRole("heading", { name: "All boards ace reads" }) });
  await expect(boards.getByRole("row", { name: /Oakline Freight/ })).toContainText("Stopped answering");
  await expect(page.getByRole("heading", { name: /Stopped answering \(1\)/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Sites that say no \(1\)/ })).toBeVisible();
  await expect(page.getByText("ace still reads the boards it already read on these sites")).toBeVisible();
  await expect(page.getByRole("row", { name: /careers\.oakhollow\.example/ })).toContainText("Robots file disallows");
  await expect(page.getByRole("row", { name: /Eightfold/ })).toContainText("not checked yet");
});

test("adding a job says it was added, what happens next, and can be undone", async ({ page }) => {
  let undone: unknown = null;
  await page.route("**/api/sources", answer({
    status: "added",
    company: "Cinderpath",
    source_type: "ashby",
    source_account: "cinderpath",
    job_count: 14,
    linked: true,
    first_read_seconds: 900,
  }));
  await page.route("**/api/sources/undo", async (route) => {
    undone = route.request().postDataJSON();
    await route.fulfill({ status: 200, contentType: "application/json", body: '{"status":"undone"}' });
  });
  await page.goto("/app/coverage?tab=leads");
  await paste(page, "https://jobs.ashbyhq.com/cinderpath/0a1b2c3d");

  const result = page.locator(".cov-answer");
  await expect(result).toHaveAttribute("role", "status");
  await expect(result.getByRole("heading", { name: "Cinderpath added" })).toBeVisible();
  await expect(result).toContainText("It has 14 jobs today.");
  await expect(result).toContainText("Your job: ace looks for it in the first read.");
  await expect(result).toContainText("Within 15 minutes");
  await expect(result.getByRole("link", { name: "See it in Sources" })).toHaveAttribute("href", /tab=sources&show=mine/);

  await result.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByText("Taken back. ace will not read Cinderpath.")).toBeVisible();
  expect(undone).toEqual({ source_type: "ashby", source_account: "cinderpath" });
});

for (const [status, body, heading, says] of [
  ["already reading", { status: "already_known", company: "Cinderpath", last_read_at: new Date().toISOString(), linked: true, job: { id: 1, title: "Software Engineer", location: "Boston, MA", active: true, passes: true } }, "ace already reads Cinderpath", "It is in Opportunities."],
  ["no reader", { status: "saved_no_reader", company: "Quillfeather", detail: "It hires through Teamtailor, and ace has no reader for that site yet.", next_check_at: "2026-12-05T12:00:00+00:00", linked: true }, "Quillfeather saved, but ace can’t read its site yet", "Until then, check it by hand."],
  ["site says no", { status: "saved_refused", company: "Oakhollow", detail: "Its rules ask automated readers to stay off this page. ace respects that and will not try another way. Check it by hand.", linked: true }, "Oakhollow saved, but its site says no", "will not try another way"],
  ["switched off", { status: "known_off", company: "Wrenfield Talent", detail: "ace knows this board and left it out, because it looks like a staffing agency, not an employer." }, "ace knows Wrenfield Talent, and has it switched off", "staffing agency"],
  ["nothing found", { status: "saved_looking", company: "Fernhollow", detail: "ace found no job board there yet.", next_check_at: "2026-11-12T12:00:00+00:00" }, "ace found no job board for Fernhollow yet", "paste that instead"],
] as const) {
  test(`the answer is clear when: ${status}`, async ({ page }) => {
    await page.route("**/api/sources", answer(body));
    await page.goto("/app/coverage?tab=leads");
    await paste(page, "Cinderpath");
    const result = page.locator(".cov-answer");
    await expect(result.getByRole("heading", { name: heading })).toBeVisible();
    await expect(result).toContainText(says);
    await expect(result.getByRole("button", { name: "Undo" })).toHaveCount(0);
  });
}

test("an empty box and a failed request both say so, and add nothing", async ({ page }) => {
  await page.route("**/api/sources", (route) => route.fulfill({ status: 500, body: "{}" }));
  await page.goto("/app/coverage?tab=leads");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByText("Paste a link or a company name first.")).toBeVisible();
  await paste(page, "Cinderpath");
  await expect(page.getByText("Could not reach ace, so nothing was added. Try again.")).toBeVisible();
});
