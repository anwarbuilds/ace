"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import { useApp } from "@/components/shell/AppProvider";
import { csrfHeader, RequestError, sendJson } from "@/lib/client";

export interface AccountProfile {
  display_name: string;
  first_name: string;
  last_name: string;
  phone_number: string;
  avatar_updated_at: string | null;
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
  const fileInput = useRef<HTMLInputElement>(null);
  const [profile, setProfile] = useState(account);
  const [first, setFirst] = useState(account.first_name);
  const [last, setLast] = useState(account.last_name);
  const [phone, setPhone] = useState(account.phone_number);
  const [busy, setBusy] = useState(false);
  const [photoBusy, setPhotoBusy] = useState(false);
  const [error, setError] = useState("");
  const [photoError, setPhotoError] = useState("");
  const [emailOpen, setEmailOpen] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [emailBusy, setEmailBusy] = useState(false);
  const [emailError, setEmailError] = useState("");
  const changed = first !== profile.first_name || last !== profile.last_name || phone !== profile.phone_number;

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const updated = await sendJson<AccountProfile>("PATCH", "/api/auth/account",
        { first_name: first, last_name: last, phone_number: phone });
      setProfile(updated);
      setFirst(updated.first_name);
      setLast(updated.last_name);
      setPhone(updated.phone_number);
      toast("Profile saved");
      router.refresh();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }

  async function uploadPhoto(file: File | undefined) {
    if (!file) return;
    setPhotoError("");
    if (file.size > 2 * 1024 * 1024) {
      setPhotoError("Choose a JPG, PNG or WebP photo smaller than 2 MB.");
      return;
    }
    setPhotoBusy(true);
    try {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch("/api/auth/account/avatar",
        { method: "PUT", headers: csrfHeader(), body });
      if (!response.ok) {
        const detail = (await response.json().catch(() => null))?.detail;
        throw new Error(detail?.message ?? "Could not save the photo. Try again.");
      }
      setProfile(await response.json() as AccountProfile);
      toast("Profile photo updated");
      router.refresh();
    } catch (caught) {
      setPhotoError(caught instanceof Error ? caught.message : "Could not save the photo. Try again.");
    } finally {
      setPhotoBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function removePhoto() {
    setPhotoBusy(true);
    setPhotoError("");
    try {
      setProfile(await sendJson<AccountProfile>("DELETE", "/api/auth/account/avatar"));
      toast("Profile photo removed");
      router.refresh();
    } catch (caught) {
      setPhotoError(message(caught));
    } finally {
      setPhotoBusy(false);
    }
  }

  async function startEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setEmailBusy(true);
    setEmailError("");
    try {
      await sendJson("POST", "/api/auth/account/email/start",
        { email: newEmail, current_password: password });
      setPassword("");
      setCodeSent(true);
      toast("Verification code sent");
    } catch (caught) {
      setEmailError(message(caught));
    } finally {
      setEmailBusy(false);
    }
  }

  async function confirmEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setEmailBusy(true);
    setEmailError("");
    try {
      await sendJson("POST", "/api/auth/account/email/confirm",
        { email: newEmail, code }, { redirectOn401: false });
      // Clear all client state after the server revokes this browser session.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/login?email_changed=1");
    } catch (caught) {
      setEmailError(message(caught));
      setEmailBusy(false);
    }
  }

  return <section className="sect account-settings" id="account">
    <div className="section-head"><div><p className="eyebrow">My account</p>
      <h2 className="st-h2">Your ACE identity</h2></div>
      <span className="account-role">Workspace owner</span></div>
    <div className="account-grid">
      <div className="account-profile-card">
        <div className="account-photo-row">
          <div className="account-avatar">
            {profile.avatar_updated_at
              ? <Image src={`/api/auth/account/avatar?v=${encodeURIComponent(profile.avatar_updated_at)}`}
                  alt="Your profile photo" width={76} height={76} unoptimized />
              : (profile.first_name || profile.display_name || profile.email).slice(0, 1).toUpperCase()}
          </div>
          <div><strong>Profile photo</strong><p className="why">JPG, PNG or WebP, up to 2 MB.</p>
            <div className="account-photo-actions">
              <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp"
                className="account-file-input" aria-label="Choose a profile photo"
                onChange={(event) => void uploadPhoto(event.target.files?.[0])} />
              <button type="button" className="btn btn-sm" disabled={photoBusy}
                onClick={() => fileInput.current?.click()}>
                {photoBusy ? "Saving" : profile.avatar_updated_at ? "Change photo" : "Upload photo"}
              </button>
              {profile.avatar_updated_at ? <button type="button" className="link-btn"
                disabled={photoBusy} onClick={() => void removePhoto()}>Remove</button> : null}
            </div>
            {photoError ? <p className="auth-err" role="alert">{photoError}</p> : null}
          </div>
        </div>
        <form className="account-fields" onSubmit={save}>
          <div className="account-field-grid">
            <div><label htmlFor="account-first">First name</label>
              <input id="account-first" autoComplete="given-name" maxLength={80}
                value={first} onChange={(event) => setFirst(event.target.value)} required /></div>
            <div><label htmlFor="account-last">Last name</label>
              <input id="account-last" autoComplete="family-name" maxLength={80}
                value={last} onChange={(event) => setLast(event.target.value)} required /></div>
            <div className="account-field-full"><label htmlFor="account-phone">Phone number</label>
              <input id="account-phone" type="tel" autoComplete="tel" maxLength={32}
                value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="Optional" /></div>
          </div>
          <div className="account-save-row"><span className="why">Your name appears throughout ace.</span>
            <button className="btn btn-primary btn-sm" type="submit" disabled={busy || !changed}>
              {busy ? "Saving" : "Save profile"}</button></div>
          {error ? <p className="auth-err" role="alert">{error}</p> : null}
        </form>
      </div>
      <div className="account-details">
        <dl><div><dt>Sign-in email</dt><dd>{profile.email}</dd></div>
          <div><dt>Google sign-in</dt><dd>{profile.google_connected ? "Connected" : "Not connected"}</dd></div>
          <div><dt>Account created</dt><dd>{joined}</dd></div></dl>
        <button type="button" className="link-btn account-email-toggle"
          onClick={() => {
            if (emailOpen) {
              setCodeSent(false);
              setCode("");
              setPassword("");
              setNewEmail("");
            }
            setEmailOpen(!emailOpen);
            setEmailError("");
          }}>
          {emailOpen ? "Cancel email change" : "Change sign-in email"}</button>
        {emailOpen ? <div className="account-email-change">
          <p className="why">This changes your ACE sign-in address. We will verify the new address and sign you out. Gmail inbox connection is separate.</p>
          {!codeSent ? <form onSubmit={startEmail}>
            <label htmlFor="account-new-email">New email address</label>
            <input id="account-new-email" type="email" autoComplete="email"
              value={newEmail} onChange={(event) => setNewEmail(event.target.value)} required />
            <label htmlFor="account-current-password">Current password</label>
            <input id="account-current-password" type="password" autoComplete="current-password"
              value={password} onChange={(event) => setPassword(event.target.value)} required />
            <button className="btn btn-primary btn-sm" type="submit" disabled={emailBusy}>
              {emailBusy ? "Sending" : "Send verification code"}</button>
          </form> : <form onSubmit={confirmEmail}>
            <p className="why">Enter the code sent to {newEmail}.</p>
            <label htmlFor="account-email-code">Verification code</label>
            <input id="account-email-code" inputMode="numeric" autoComplete="one-time-code"
              value={code} onChange={(event) => setCode(event.target.value)} required />
            <button className="btn btn-primary btn-sm" type="submit" disabled={emailBusy}>
              {emailBusy ? "Verifying" : "Verify and change email"}</button>
          </form>}
          {emailError ? <p className="auth-err" role="alert">{emailError}</p> : null}
        </div> : null}
      </div>
    </div>
  </section>;
}
