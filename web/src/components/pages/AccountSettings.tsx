"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { useApp } from "@/components/shell/AppProvider";
import { RequestError, sendJson } from "@/lib/client";

export interface AccountProfile {
  display_name: string;
  email: string;
  role: string;
  created_at: string;
  google_connected: boolean;
}

function message(error: unknown): string {
  return error instanceof RequestError ? error.message : "ace did not answer. Try again in a moment.";
}

export function AccountSettings({ account, joined }: { account: AccountProfile; joined: string }) {
  const router = useRouter();
  const { toast } = useApp();
  const [name, setName] = useState(account.display_name);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const updated = await sendJson<AccountProfile>("PATCH", "/api/auth/account", { display_name: name });
      setName(updated.display_name);
      toast("Account name updated");
      router.refresh();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="sect account-settings" id="account">
      <div className="section-head">
        <div>
          <p className="eyebrow">My account</p>
          <h2 className="st-h2">Your ACE identity</h2>
        </div>
        <span className="account-role">Workspace owner</span>
      </div>
      <div className="account-grid">
        <form className="account-profile-card" onSubmit={save}>
          <div className="account-avatar" aria-hidden="true">
            {(name || account.email).slice(0, 1).toUpperCase()}
          </div>
          <div className="account-fields">
            <label htmlFor="account-name">Full name</label>
            <div className="account-name-row">
              <input
                id="account-name"
                name="display_name"
                type="text"
                autoComplete="name"
                maxLength={120}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Enter your full name"
                required
              />
              <button className="btn btn-primary btn-sm" type="submit" disabled={busy || name.trim() === account.display_name}>
                {busy ? "Saving" : "Save name"}
              </button>
            </div>
            {error ? <p className="auth-err" role="alert">{error}</p> : null}
          </div>
        </form>
        <dl className="account-details">
          <div>
            <dt>Email address</dt>
            <dd>{account.email}</dd>
          </div>
          <div>
            <dt>Google sign-in</dt>
            <dd>{account.google_connected ? "Connected" : "Not connected"}</dd>
          </div>
          <div>
            <dt>Account created</dt>
            <dd>{joined}</dd>
          </div>
        </dl>
      </div>
      <p className="why account-note">
        Your name appears in the workspace menu. Your email remains the verified address used to sign in.
      </p>
    </section>
  );
}
