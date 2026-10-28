import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const extensionRoot = path.resolve(process.cwd(), "../extension");

type Answer = { label: string; value: string; aliases?: string[] };

async function fillFixture(page: Page, fields: [string, string, string[]?][], answers: Answer[]) {
  await page.goto("data:text/html,<html><body></body></html>");
  await page.setContent(`<form>
    ${fields.map(([id, question, options]) => `<label for="${id}">${question}</label>${options
      ? `<button id="${id}" type="button" aria-haspopup="listbox">Select One</button>`
      : `<textarea id="${id}"></textarea>`}`).join("")}
  </form>`);
  await page.evaluate(({ fields, answers }) => {
    (window as typeof window & { chrome: unknown }).chrome = {
      runtime: {
        onMessage: { addListener() {} },
        getURL: (value: string) => value,
        getManifest: () => ({ version: "test" }),
        sendMessage: (message: { type: string }, callback: (reply: unknown) => void) => {
          callback(message.type === "answers"
            ? { ok: true, items: answers }
            : { ok: true, work: [], education: [] });
        },
      },
    };
    for (const [id, , values] of fields) {
      if (!values) continue;
      document.getElementById(id)?.addEventListener("click", () => {
        document.querySelector("#fixture-options")?.remove();
        const menu = document.createElement("div");
        menu.id = "fixture-options";
        menu.setAttribute("role", "listbox");
        for (const value of values) {
          const option = document.createElement("div");
          option.setAttribute("role", "option");
          option.textContent = value;
          option.addEventListener("click", () => {
            document.getElementById(id)!.textContent = value;
            menu.remove();
          });
          menu.appendChild(option);
        }
        document.body.appendChild(menu);
      });
    }
  }, { fields, answers });
  await page.addScriptTag({ path: path.join(extensionRoot, "fields.js") });
  await page.addScriptTag({ path: path.join(extensionRoot, "memory.js") });
  await page.addScriptTag({ path: path.join(extensionRoot, "content.js") });
  await expect.poll(() => page.evaluate(() => Boolean(document.querySelector(".ace-root")))).toBe(true);
  await page.evaluate(() => document.dispatchEvent(new KeyboardEvent("keydown", {
    key: "a", altKey: true, bubbles: true,
  })));
}

test("Meijer first page keeps consent and company histories separate", async ({ page }) => {
  await fillFixture(page, [
    ["authorized", "Are you legally authorized to work in the country in which this position is located?", ["Yes", "No"]],
    ["sponsorship", "Do you now or will you in the future need employer immigration sponsorship for work authorization?", ["Yes", "No"]],
    ["age", "Please indicate your current age range.", ["Under 18", "18 years or older"]],
    ["texts", "I authorize enabling text messages for candidate invitations and notifications. I understand standard data or text charges may apply.", ["Yes", "No"]],
    ["contracted", "Have you previously been contracted with Meijer, Fresh Thyme, or Serv-u-Success?", ["Yes", "No"]],
    ["worked", "Have you previously worked for Meijer or Fresh Thyme?", ["Yes", "No"]],
  ], [
    { label: "Work authorisation", value: "Yes" },
    { label: "Need sponsorship in future", value: "No" },
    { label: "At least 18 years old", value: "Yes" },
    { label: "Consent to recruiting text messages", value: "No" },
    { label: "Previously contracted with Meijer group", value: "Yes" },
    { label: "Previously worked for Meijer or Fresh Thyme", value: "No" },
    { label: "Previously employed by this company", value: "Yes" },
  ]);
  for (const [id, value] of Object.entries({
    authorized: "Yes", sponsorship: "No", age: "18 years or older",
    texts: "No", contracted: "Yes", worked: "No",
  })) await expect(page.locator(`#${id}`)).toHaveText(value);
});

test("adult status does not guess an age band", async ({ page }) => {
  await fillFixture(page, [
    ["age", "Please indicate your current age range.", ["18-24", "25-34"]],
    ["authorized", "Are you legally authorized to work in the United States?", ["Yes", "No"]],
    ["sponsorship", "Will you now or in the future need sponsorship?", ["Yes", "No"]],
    ["worked", "Have you previously worked for Meijer or Fresh Thyme?", ["Yes", "No"]],
  ], [
    { label: "At least 18 years old", value: "Yes" },
    { label: "Work authorisation", value: "Yes" },
  ]);
  await expect(page.locator("#age")).toHaveText("Select One");
});

test("Meijer second page uses distinct recruiter, contractor and footprint answers", async ({ page }) => {
  await fillFixture(page, [
    ["recruiter", "Have you spoken to any recruiters/agencies that have presented opportunities at Meijer?", ["Yes", "No"]],
    ["contractor", "Are you a current contractor at Meijer or another client?", ["Yes", "No"]],
    ["footprint", "Do you live in our footprint? [Michigan, Ohio, Indiana, Illinois, Wisconsin, Kentucky]", ["Yes", "No"]],
    ["relocate", "If not within our 6-state footprint, are you willing to relocate?", ["Yes, I am willing to relocate to footprint for Remote work", "No"]],
    ["sponsorship", "Will you now or in the future require sponsorship to continue working in the United States?", ["Yes", "No"]],
    ["visa", "Please list the type of your current visa/sponsorship."],
  ], [
    { label: "Discussed Meijer opportunities with recruiters", value: "No" },
    { label: "Current contractor at Meijer or another client", value: "Yes" },
    { label: "Live in Meijer six-state footprint", value: "No" },
    { label: "Willing to relocate", value: "Yes" },
    { label: "Need sponsorship in future", value: "Yes" },
    { label: "Current visa or sponsorship description", value: "Example status" },
  ]);
  for (const [id, value] of Object.entries({
    recruiter: "No", contractor: "Yes", footprint: "No", sponsorship: "Yes",
  })) await expect(page.locator(`#${id}`)).toHaveText(value);
  await expect(page.locator("#relocate")).toContainText("Yes, I am willing");
  await expect(page.locator("#visa")).toHaveValue("Example status");
});

test("Meijer technical questions use their own saved answers", async ({ page }) => {
  await fillFixture(page, [
    ["ai", "Do you have experience with AI-assisted engineering tools such as GitHub Copilot and context/prompt engineering?", ["Yes", "No"]],
    ["azure", "How many years of experience do you have building AI or agentic features on the Microsoft Azure stack?", ["0-1 years", "2-4 years", "5+ years"]],
    ["coding", "Do you have any experience using AI to assist with writing code? If so, which LLM(s)?"],
    ["opt", "Are you currently on an OPT Student Visa?", ["Yes", "No"]],
    ["hybrid", "Are you able to work this hybrid schedule?", ["Yes", "No"]],
  ], [
    { label: "AI-assisted engineering tools experience", value: "Yes" },
    { label: "Years building AI features on Azure", value: "2-4 years" },
    { label: "AI coding assistance tools used", value: "Example coding assistant" },
    { label: "Currently on OPT student visa", value: "No" },
    { label: "Willing to work onsite", value: "Yes" },
  ]);
  await expect(page.locator("#ai")).toHaveText("Yes");
  await expect(page.locator("#azure")).toHaveText("2-4 years");
  await expect(page.locator("#coding")).toHaveValue("Example coding assistant");
  await expect(page.locator("#opt")).toHaveText("No");
  await expect(page.locator("#hybrid")).toHaveText("Yes");
});

test("similar broad answers cannot fill unsaved Meijer questions", async ({ page }) => {
  await fillFixture(page, [
    ["contracted", "Have you previously been contracted with Meijer, Fresh Thyme, or Serv-u-Success?", ["Yes", "No"]],
    ["worked", "Have you previously worked for Meijer or Fresh Thyme?", ["Yes", "No"]],
    ["texts", "I authorize enabling text messages for candidate invitations and notifications.", ["Yes", "No"]],
    ["azure", "How many years of experience do you have building AI or agentic features on the Microsoft Azure stack?", ["0-1 years", "2-4 years", "5+ years"]],
  ], [
    { label: "Previously employed by this company", value: "No" },
    { label: "Previously employed by Meijer", value: "No" },
    { label: "Consent to AI in hiring", value: "Yes" },
    { label: "Years of experience", value: "5" },
  ]);
  for (const id of ["contracted", "worked", "texts", "azure"]) {
    await expect(page.locator(`#${id}`)).toHaveText("Select One");
  }
});

test("Verizon Workday questions keep each saved fact separate", async ({ page }) => {
  await fillFixture(page, [
    ["authorized", "Are you currently authorized to work for any employer in the U.S.?", ["Yes", "No"]],
    ["now", "Do you currently require sponsorship for an employment visa in order to work in the U.S.?", ["Yes, I do require sponsorship", "No, I do not"]],
    ["future", "Will you require visa sponsorship at some time in the future in order to continue work in the U.S.?", ["Yes, I will require sponsorship", "No, I will not"]],
    ["adult", "Are you at least 18 years old?", ["Yes", "No"]],
    ["employee", "Do you have any family members or persons with whom you have/had a close personal relationship who are employed by Verizon?", ["Yes", "No"]],
    ["agreement", "Have you signed or are you subject to any non-competition, employee non-solicitation, customer non-solicitation or any agreement that could restrict or prevent you from working at Verizon?", ["Yes", "No"]],
    ["government", "Are you currently employed, or have you previously been employed, by the United States Federal, State or Local government?", ["Yes", "No"]],
    ["board", "Do you have any family members who are part of Verizon Communication Inc's Board of Directors?", ["Yes", "No"]],
    ["military", "Are you currently serving or have you previously served in the U.S. Military?", ["Yes", "No"]],
    ["spouse", "Are you currently an active military spouse, or has your spouse previously served in the U.S. Military?", ["Yes", "No"]],
  ], [
    { label: "Authorized to work for any US employer", value: "No" },
    { label: "Currently require employer visa sponsorship", value: "Yes" },
    { label: "Need sponsorship in future", value: "No" },
    { label: "At least 18 years old", value: "Yes" },
    { label: "Family or close personal relationship with employee here", value: "Yes" },
    { label: "Agreement restricting work for employer", value: "No" },
    { label: "Federal state or local government employment", value: "Yes" },
    { label: "Family member on employer board", value: "No" },
    { label: "Personally served in US military", value: "Yes" },
    { label: "Spouse served in US military", value: "No" },
  ]);
  for (const [id, value] of Object.entries({
    authorized: "No", adult: "Yes", employee: "Yes", agreement: "No",
    government: "Yes", board: "No", military: "Yes", spouse: "No",
  })) await expect(page.locator(`#${id}`)).toHaveText(value);
  await expect(page.locator("#now")).toContainText("Yes, I do require");
  await expect(page.locator("#future")).toContainText("No, I will not");
});

test("broad saved answers do not fill distinct Verizon questions", async ({ page }) => {
  await fillFixture(page, [
    ["authorized", "Are you currently authorized to work for any employer in the U.S.?", ["Yes", "No"]],
    ["now", "Do you currently require sponsorship for an employment visa in order to work in the U.S.?", ["Yes", "No"]],
    ["employee", "Do you have any family members or persons with whom you have/had a close personal relationship who are employed by Verizon?", ["Yes", "No"]],
    ["agreement", "Have you signed or are you subject to any non-competition, employee non-solicitation, customer non-solicitation or any agreement that could restrict or prevent you from working at Verizon?", ["Yes", "No"]],
    ["government", "Are you currently employed, or have you previously been employed, by the United States Federal, State or Local government?", ["Yes", "No"]],
    ["board", "Do you have any family members who are part of Verizon Communication Inc's Board of Directors?", ["Yes", "No"]],
    ["military", "Are you currently serving or have you previously served in the U.S. Military?", ["Yes", "No"]],
    ["spouse", "Are you currently an active military spouse, or has your spouse previously served in the U.S. Military?", ["Yes", "No"]],
  ], [
    { label: "Work authorisation", value: "Yes" },
    { label: "Need sponsorship now", value: "Yes" },
    { label: "Related to an employee here", value: "No" },
    { label: "Bound by a non-compete", value: "No" },
    { label: "Employed by the federal government", value: "No" },
    { label: "Employed by state or local government", value: "No" },
    { label: "Veteran status", value: "No" },
  ]);
  for (const id of ["authorized", "now", "employee", "agreement", "government", "board", "military", "spouse"]) {
    await expect(page.locator(`#${id}`)).toHaveText("Select One");
  }
});
