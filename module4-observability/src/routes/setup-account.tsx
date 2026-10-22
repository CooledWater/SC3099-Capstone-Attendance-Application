import { FormEvent, useEffect, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { api } from "@/lib/api";

export const Route = createFileRoute("/setup-account")({
  head: () => ({
    meta: [
      { title: "Set up your attendance account" },
      { name: "referrer", content: "no-referrer" },
      { name: "robots", content: "noindex,nofollow" },
    ],
  }),
  component: SetupAccount,
});

function SetupAccount() {
  const token = useRef("");
  const [email, setEmail] = useState("");
  const [checking, setChecking] = useState(true);
  const [valid, setValid] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [completed, setCompleted] = useState(false);

  useEffect(() => {
    let cancelled = false;
    token.current =
      token.current || new URLSearchParams(window.location.hash.slice(1)).get("token") || "";
    // Keep the secret in memory only: out of browser history and HTTP referrers.
    window.history.replaceState(null, "", window.location.pathname);
    async function validate() {
      try {
        if (!token.current)
          throw new Error("This invitation link is missing or invalid. Request a new invitation.");
        const result = await api.request<{ email: string }>("/auth/invitations/validate", {
          method: "POST",
          body: JSON.stringify({ token: token.current }),
        });
        if (!cancelled) {
          setEmail(result.email);
          setValid(true);
        }
      } catch (failure) {
        if (!cancelled)
          setError(failure instanceof Error ? failure.message : "Could not check this invitation.");
      } finally {
        if (!cancelled) setChecking(false);
      }
    }
    void validate();
    return () => {
      cancelled = true;
    };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (lock.current) return;
    setError("");
    setMessage("");
    if (valid && password !== confirmation) {
      setError("Passwords do not match.");
      return;
    }
    if (valid && new TextEncoder().encode(password).length > 72) {
      setError("Use a password of at most 72 UTF-8 bytes.");
      return;
    }
    lock.current = true;
    setBusy(true);
    try {
      if (!valid) {
        const result = await api.request<{ message: string }>("/auth/invitations/request", {
          method: "POST",
          body: JSON.stringify({ email: email.trim() }),
        });
        setMessage(result.message);
      } else {
        await api.request("/auth/invitations/complete", {
          method: "POST",
          body: JSON.stringify({ token: token.current, password }),
        });
        token.current = "";
        setCompleted(true);
        try {
          await api.login(email, password);
          try {
            sessionStorage.removeItem("saiv.dashboard.signed-out");
          } catch {
            /* Storage is optional. */
          }
          window.location.assign(import.meta.env.BASE_URL);
        } catch {
          try {
            sessionStorage.setItem("saiv.dashboard.signed-out", "true");
          } catch {
            /* Storage is optional. */
          }
          setMessage("Your password has been set. Sign in to continue.");
        }
        setPassword("");
        setConfirmation("");
      }
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not set up your account.");
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen grid place-items-center bg-background p-6 text-foreground">
      <section className="grid w-full max-w-md gap-5 rounded-3xl border border-border bg-glass p-8 shadow-[var(--shadow-glass)]">
        <span className="text-xs uppercase tracking-widest text-primary">CCDS ATTENDANCE</span>
        <h1 className="text-2xl font-semibold">Set up your account</h1>
        {checking ? (
          <p role="status">Checking your invitation...</p>
        ) : (
          <>
            {error && (
              <div
                className="rounded-lg border border-border bg-secondary/40 p-3 text-sm"
                role="alert"
              >
                {error}
              </div>
            )}
            {message && (
              <div
                className="rounded-lg border border-border bg-secondary/40 p-3 text-sm"
                role="status"
              >
                {message}
              </div>
            )}
            {completed ? (
              <a
                className="rounded-xl bg-primary px-4 py-3 text-center font-medium text-primary-foreground disabled:opacity-60"
                href={`${import.meta.env.BASE_URL}auth`}
              >
                Go to sign in
              </a>
            ) : (
              <form className="grid gap-4" onSubmit={(event) => void submit(event)}>
                {valid ? (
                  <>
                    <p>{email}</p>
                    <label className="grid gap-2 text-sm">
                      Password
                      <input
                        className="w-full min-w-0 rounded-lg border border-border bg-secondary/40 px-3 py-2 text-foreground"
                        type="password"
                        autoComplete="new-password"
                        minLength={8}
                        maxLength={72}
                        required
                        value={password}
                        disabled={busy}
                        onChange={(event) => setPassword(event.target.value)}
                      />
                      <small>At least 8 characters.</small>
                    </label>
                    <label className="grid gap-2 text-sm">
                      Confirm password
                      <input
                        className="w-full min-w-0 rounded-lg border border-border bg-secondary/40 px-3 py-2 text-foreground"
                        type="password"
                        autoComplete="new-password"
                        minLength={8}
                        maxLength={72}
                        required
                        value={confirmation}
                        disabled={busy}
                        onChange={(event) => setConfirmation(event.target.value)}
                      />
                    </label>
                    <button
                      className="rounded-xl bg-primary px-4 py-3 text-center font-medium text-primary-foreground disabled:opacity-60"
                      disabled={busy}
                    >
                      {busy ? "Setting up..." : "Set password and sign in"}
                    </button>
                  </>
                ) : (
                  <>
                    <p>
                      Request another setup link using the email address your instructor enrolled.
                    </p>
                    <label className="grid gap-2 text-sm">
                      Email address
                      <input
                        className="w-full min-w-0 rounded-lg border border-border bg-secondary/40 px-3 py-2 text-foreground"
                        type="email"
                        autoComplete="email"
                        required
                        value={email}
                        disabled={busy}
                        onChange={(event) => setEmail(event.target.value)}
                      />
                    </label>
                    <button
                      className="rounded-xl bg-primary px-4 py-3 text-center font-medium text-primary-foreground disabled:opacity-60"
                      disabled={busy}
                    >
                      {busy ? "Requesting..." : "Request a new invitation"}
                    </button>
                  </>
                )}
              </form>
            )}
          </>
        )}
        <a href={`${import.meta.env.BASE_URL}auth`}>Back to sign in</a>
      </section>
    </main>
  );
}
