"use client";

import Link from "next/link";
import Script from "next/script";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const API_BASE = (process.env.MYSPACE_PUBLIC_BACKEND_URL ?? "").replace(/\/$/, "");

type GoogleIdentity = {
  initialize: (options: { client_id: string; nonce: string; callback: (result: { credential: string }) => void }) => void;
  renderButton: (element: HTMLElement, options: { theme: string; size: string; text: string }) => void;
};

declare global {
  interface Window { google?: { accounts: { id: GoogleIdentity } } }
}

function safeNext(value: string | null) {
  try {
    const url = new URL(value || "/workspace", "https://app.local");
    return url.origin === "https://app.local" && url.pathname !== "/login"
      ? `${url.pathname}${url.search}${url.hash}` : "/workspace";
  } catch { return "/workspace"; }
}

function authError(payload: unknown): string {
  const detail = (payload as { detail?: { message?: string } } | null)?.detail;
  return detail?.message ?? "We could not sign you in. Please try again.";
}

export function LoginClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = safeNext(searchParams.get("next"));
  const button = useRef<HTMLDivElement>(null);
  const [scriptReady, setScriptReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/api/auth/me`, { credentials: "include" })
      .then((response) => { if (active && response.ok) router.replace(next); })
      .catch(() => { if (active) setError("Unable to reach the sign-in service. Please try again."); })
      .finally(() => { if (active) setCheckingSession(false); });
    return () => { active = false; };
  }, [next, router]);

  useEffect(() => {
    if (!scriptReady || checkingSession) return;
    let active = true;
    const container = button.current;
    async function setup() {
      try {
        const response = await fetch(`${API_BASE}/api/auth/google/config`, { credentials: "include", cache: "no-store" });
        const config = await response.json();
        if (!response.ok) throw new Error(authError(config));
        if (!active || !container || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: config.client_id,
          nonce: config.nonce,
          callback: async ({ credential }) => {
            if (!active) return;
            setLoading(true);
            setError("");
            try {
              const result = await fetch(`${API_BASE}/api/auth/google`, {
                method: "POST", credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ credential }),
              });
              const payload = await result.json();
              if (!result.ok) throw new Error(authError(payload));
              router.replace(next);
            } catch (caught) {
              if (active) setError(caught instanceof Error ? caught.message : "Sign-in failed. Please try again.");
            } finally { if (active) setLoading(false); }
          },
        });
        container.replaceChildren();
        window.google.accounts.id.renderButton(container, { theme: "outline", size: "large", text: "continue_with" });
      } catch (caught) {
        if (active) setError(caught instanceof Error ? caught.message : "Unable to load Google sign-in.");
      }
    }
    void setup();
    return () => { active = false; container?.replaceChildren(); };
  }, [scriptReady, checkingSession, next, router]);

  return (
    <>
      <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive"
        onReady={() => setScriptReady(true)} onError={() => setError("Google sign-in could not load. Check your connection and reload.")} />
    <main className="auth-page">
      <Link className="auth-brand" href="/" aria-label="YourSpace home">
        <img src="/yourspace-logo.png" alt="" />
        <strong>YourSpace</strong>
      </Link>

      <section className="auth-shell">
        <div className="auth-copy">
          <span className="eyebrow">Your private design studio</span>
          <h1>Every room, revision, and recommendation stays with your account.</h1>
          <p>Sign in once to return to previous projects, continue each project chat, and keep furniture decisions separate for every room.</p>
          <div className="auth-proof-list" aria-label="Account benefits">
            <div><span>01</span><p><strong>One project per room</strong>Your photos, brief, generated images, and product plan stay together.</p></div>
            <div><span>02</span><p><strong>Saved design history</strong>Reopen a project and revise it without starting again.</p></div>
            <div><span>03</span><p><strong>Private account session</strong>Your identity is held by the server, not editable browser storage.</p></div>
          </div>
        </div>

        <div className="auth-card">
          <div className="auth-card-heading">
            <h2>Your home starts here</h2>
            <p>Sign in or create your YourSpace account with Google.</p>
          </div>
          <div ref={button} aria-label="Continue with Google" hidden={loading} />
          {checkingSession || !scriptReady || loading ? <p role="status">{loading ? "Signing you in..." : "Loading sign-in..."}</p> : null}
          {error ? <p className="auth-error" role="alert">{error}</p> : null}
          <p className="auth-privacy">Google verifies your identity. YourSpace never receives your Google password. Your session stays in an HttpOnly cookie.</p>
        </div>
      </section>
    </main>
    </>
  );
}
