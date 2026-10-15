import Link from "next/link";

import { ExtensionPairing } from "@/components/pages/ExtensionPairing";
import type { TokenRow } from "@/components/pages/SecuritySettings";
import { NavIcon } from "@/components/shell/NavIcon";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGetOr, authStatus } from "@/lib/api";
import { clock, shortDate } from "@/lib/format";
import { getPrefs } from "@/lib/prefs";
import type { Answer } from "@/lib/types";

export const metadata = { title: "Autofill Extension · ace" };

// What the extension does, whether it is paired, and the answers it
// fills from. Pairing lives here; Settings links to it.
export default async function ExtensionPage() {
  const [auth, tokens, answers, { tz }] = await Promise.all([
    authStatus(),
    apiGetOr<{ items: TokenRow[] }>("/api/extension/tokens", { items: [] }),
    apiGetOr<{ items: Answer[] }>("/api/answers", { items: [] }),
    getPrefs(),
  ]);
  const when: Record<string, string> = {};
  for (const t of tokens.items) if (t.last_used_at) when[t.last_used_at] = `${shortDate(t.last_used_at, tz)} ${clock(t.last_used_at, tz)}`;
  const filled = answers.items.filter((a) => a.value).length;
  const paired = tokens.items.length > 0;
  const signInOff = auth?.kind === "local";

  return (
    <ScrollArea>
      <div className="pg">
      <div className="page-hero">
        <div>
          <div className="eyebrow">Career tools</div>
          <h1 className="h1">Autofill Extension</h1>
          <p className="subtitle">
            Fills application forms from your answer bank. It never submits, and never overwrites a field you filled.
          </p>
        </div>
        <div className="btns">
          <Link className="btn" href="/app/answers">
            Edit answers <NavIcon name="right" size="sm" />
          </Link>
        </div>
      </div>

      <section className="kpis kpis-3" aria-label="Extension status">
        <div className="kpi">
          <div className="kpi-l">Connection</div>
          <div className="kpi-n">{signInOff ? "Local" : paired ? "Paired" : "Not paired"}</div>
          <div className={`kpi-f${paired || signInOff ? " good" : " warn"}`}>
            {signInOff ? "Sign-in is off, so no pairing is needed" : paired ? `${tokens.items.length} key active` : "Pair it below to fill forms"}
          </div>
        </div>
        <div className="kpi">
          <div className="kpi-l">Answers it can fill</div>
          <div className="kpi-n">{filled.toLocaleString("en-US")}</div>
          <div className="kpi-f">of {answers.items.length.toLocaleString("en-US")} questions in the bank</div>
        </div>
        <div className="kpi">
          <div className="kpi-l">What it can read</div>
          <div className="kpi-n kpi-n-sm">Answers and history</div>
          <div className="kpi-f">Its key reads nothing else and can be revoked</div>
        </div>
      </section>

      <div className="cards-2">
        <div className="panel">
          <h3>Pairing</h3>
          {signInOff ? (
            <p className="quiet-note">
              Sign-in is switched off (ACE_AUTH=disabled), so the extension reads ace on this computer without a key.
            </p>
          ) : (
            <ExtensionPairing tokens={tokens.items} when={when} />
          )}
        </div>
        <div className="panel">
          <h3>Set it up</h3>
          <ol className="steps">
            <li>
              <b>Load it.</b> In Chrome open chrome://extensions, turn on Developer mode, choose Load unpacked and pick the
              extension folder of the ace repository.
            </li>
            <li>
              <b>Pair it.</b> Make a code here, open the extension, Connection, and type the code.
            </li>
            <li>
              <b>Fill.</b> On an application form, open the ace panel and fill. Review every field, then submit yourself.
            </li>
          </ol>
          <p className="quiet-note">
            After updating the extension, press its reload icon at chrome://extensions; only pages opened after that use the
            new version.
          </p>
        </div>
      </div>
      </div>
    </ScrollArea>
  );
}
