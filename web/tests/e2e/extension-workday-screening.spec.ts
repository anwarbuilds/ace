import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const extensionRoot = path.resolve(process.cwd(), "../extension");

async function loadExtension(page: Page, items: { label: string; value: string; aliases?: string[] }[]) {
  await page.evaluate((bank) => {
    (window as typeof window & { chrome: unknown }).chrome = {
      runtime: {
        onMessage: { addListener() {} },
        getURL: (value: string) => value,
        getManifest: () => ({ version: "test" }),
        sendMessage: (message: { type: string }, callback: (reply: unknown) => void) => {
          callback(message.type === "answers"
            ? { ok: true, items: bank }
            : { ok: true, work: [], education: [] });
        },
      },
    };
  }, items);
  await page.addScriptTag({ path: path.join(extensionRoot, "fields.js") });
  await page.addScriptTag({ path: path.join(extensionRoot, "memory.js") });
  await page.addScriptTag({ path: path.join(extensionRoot, "content.js") });
  await expect.poll(() => page.evaluate(() => Boolean(document.querySelector(".ace-root")))).toBe(true);
  await page.evaluate(() => document.dispatchEvent(new KeyboardEvent("keydown", {
    key: "a", altKey: true, bubbles: true,
  })));
}

test("Workday Field of Study commits the matching catalogue choice", async ({ page }) => {
  await page.goto("data:text/html,<html><body></body></html>");
  await page.setContent(`
    <form>
      <label for="first">First Name</label><input id="first" value="Example">
      <label for="email">Email</label><input id="email" value="example@example.test">
      <section>
        <label for="school">School or University</label><input id="school" value="Example University">
        <label for="degree">Degree</label><input id="degree" value="M.S.">
        <div data-automation-id="multiSelectContainer" id="major-picker">
          <label for="major">Field of Study</label>
          <input id="major" data-automation-id="promptSearchInput">
        </div>
      </section>
      <label for="resume">Resume/CV</label><input id="resume" type="file">
    </form>
  `);
  await page.evaluate(() => {
    const field = document.querySelector<HTMLInputElement>("#major")!;
    field.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      document.querySelector("#major-options")?.remove();
      const menu = document.createElement("div");
      menu.id = "major-options";
      for (const value of ["Computer and Information Science", "Computer Science and Engineering", "Mathematics"]) {
        const option = document.createElement("div");
        option.setAttribute("role", "option");
        option.setAttribute("data-automation-id", "promptOption");
        option.setAttribute("data-automation-label", value);
        option.textContent = value;
        option.addEventListener("click", () => {
          const pill = document.createElement("div");
          pill.setAttribute("data-automation-id", "selectedItem");
          pill.textContent = value;
          document.querySelector("#major-picker")?.appendChild(pill);
          field.value = "";
          menu.remove();
        });
        menu.appendChild(option);
      }
      document.body.appendChild(menu);
    });
  });

  await loadExtension(page, [
    { label: "Field of study", value: "Computer Science" },
    { label: "Email", value: "example@example.test" },
  ]);
  await expect(page.locator('#major-picker [data-automation-id="selectedItem"]'))
    .toHaveText("Computer and Information Science");
  await expect(page.locator("#major")).toHaveValue("");
});

test("Workday screening fills only saved or logically derived answers", async ({ page }) => {
  await page.goto("data:text/html,<html><body></body></html>");
  const prompts = [
    ["auth", "Are you legally authorized to work in the United States?"],
    ["spouse", "Is your current U.S. work authorization based on your status as a spouse of an H-1B visa holder?"],
    ["sponsor", "Will you need ExampleCo to sponsor you for a visa now or in the future?"],
    ["followup", 'Did you answer "No" to Question 1 (you are not legally authorized to work in the United States) or "Yes" to Question 2 (you will need ExampleCo to sponsor you for a visa)?'],
    ["bilateral", "Are you eligible for any visa classification based on your home country's bilateral agreement with the United States?"],
    ["student", "Are you currently in the United States on an F-1 student visa?"],
    ["relocate", "Do you currently live in or are you able to relocate to the location this job is advertised in?"],
    ["onsite", "This position requires employees to work onsite at the office at least four days per week. Are you able to meet this requirement?"],
    ["minimum", "Can you confirm that you meet the minimum qualification for years of professional work experience for this role?"],
    ["bigfour", "Are you a current or former (prior 18 months) employee of EY, PwC, Deloitte or KPMG?"],
  ];
  await page.setContent(`<form>
    ${prompts.map(([id, question]) => `<label for="${id}">${question}</label><button id="${id}" type="button" aria-haspopup="listbox">Select One</button>`).join("")}
    <label for="opt">What is the maximum end date on your authorized period for optional practical training or curricular practical training?</label><input id="opt" type="date">
    <label for="today">Please acknowledge this by entering today's date.</label><input id="today" type="date">
  </form>`);
  await page.evaluate(() => {
    document.querySelectorAll<HTMLInputElement>('input[type="date"]').forEach((input) => {
      let committed = input.value;
      input.addEventListener("input", () => { committed = input.value; });
      input.addEventListener("blur", () => { input.value = committed; });
    });
    document.querySelectorAll<HTMLButtonElement>('button[aria-haspopup="listbox"]').forEach((button) => {
      button.addEventListener("click", () => {
        document.querySelector("#choices")?.remove();
        const menu = document.createElement("div");
        menu.id = "choices";
        menu.setAttribute("role", "listbox");
        for (const value of ["Yes", "No"]) {
          const option = document.createElement("div");
          option.setAttribute("role", "option");
          option.textContent = value;
          option.addEventListener("click", () => {
            button.textContent = value;
            menu.remove();
          });
          menu.appendChild(option);
        }
        document.body.appendChild(menu);
      });
    });
  });

  // Fictional fixture values deliberately differ from the screenshot.
  await loadExtension(page, [
    { label: "Work authorisation", value: "Yes" },
    { label: "Need sponsorship in future", value: "No" },
    { label: "Work authorization through spouse visa", value: "Yes" },
    { label: "Eligible for bilateral visa classification", value: "No" },
    { label: "Currently on F-1 student visa", value: "No" },
    { label: "Maximum OPT or CPT authorization end date", value: "12/31/2030" },
    { label: "Willing to relocate", value: "No" },
    { label: "Willing to work onsite", value: "Yes" },
    { label: "Big Four employment in prior 18 months", value: "Yes" },
  ]);

  for (const id of ["auth", "spouse", "sponsor", "followup", "bilateral", "student", "onsite", "bigfour"]) {
    await expect(page.locator(`#${id}`)).toHaveText("Select One");
  }
  await expect(page.locator("#relocate")).toHaveText("No");
  await expect(page.locator("#minimum")).toHaveText("Select One");
  await expect(page.locator("#opt")).toHaveValue("");
  await expect(page.locator("#today")).toHaveValue("");
});

test("broader authorization answers do not fill unsaved narrow questions", async ({ page }) => {
  await page.goto("data:text/html,<html><body></body></html>");
  await page.setContent(`<form>
    <label for="first">First Name</label><input id="first" value="Example">
    <label for="email">Email</label><input id="email" value="example@example.test">
    <label for="spouse">Is your current U.S. work authorization based on your status as a spouse of an H-1B visa holder?</label><button id="spouse" type="button" aria-haspopup="listbox">Select One</button>
    <label for="bilateral">Are you eligible for any visa classification based on your home country's bilateral agreement with the United States?</label><button id="bilateral" type="button" aria-haspopup="listbox">Select One</button>
    <label for="student">Are you currently in the United States on an F-1 student visa?</label><button id="student" type="button" aria-haspopup="listbox">Select One</button>
    <label for="bigfour">Are you a current or former (prior 18 months) employee of EY, PwC, Deloitte or KPMG?</label><button id="bigfour" type="button" aria-haspopup="listbox">Select One</button>
    <label for="opt">What is the maximum end date on your authorized period for optional practical training?</label><input id="opt" type="date">
  </form>`);
  await loadExtension(page, [
    { label: "Work authorisation", value: "Yes" },
    { label: "Need sponsorship in future", value: "Yes" },
    { label: "Previously employed by PwC", value: "No" },
  ]);
  await expect.poll(() => page.evaluate(() =>
    document.querySelector(".ace-root")?.shadowRoot?.querySelector(".ace-title")?.textContent ?? "",
  )).toMatch(/^Filled 0 fields/);
  for (const id of ["spouse", "bilateral", "student", "bigfour"]) {
    await expect(page.locator(`#${id}`)).toHaveText("Select One");
  }
  await expect(page.locator("#opt")).toHaveValue("");
});
