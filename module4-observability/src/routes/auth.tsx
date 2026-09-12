import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";

export const Route = createFileRoute("/auth")({
  head: () => ({
    meta: [
      { title: "Sign in — Veridian Attendance Console" },
      {
        name: "description",
        content:
          "Sign in to the Veridian attendance console to monitor sessions, check-in rates and flagged items.",
      },
      { property: "og:title", content: "Sign in — Veridian Attendance Console" },
      {
        property: "og:description",
        content: "Secure access to live attendance observability for instructors.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: AuthPage,
});

function AuthPage() {
  const navigate = useNavigate();
  const { session, loading } = useAuth();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [desiredRole, setDesiredRole] = useState<"student" | "ta" | "instructor">("student");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && session) navigate({ to: "/" });
  }, [loading, session, navigate]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      if (mode === "signin") {
        await api.login(email, password);
        navigate({ to: "/" });
      } else {
        await api.register({ email, password, full_name: fullName, role: desiredRole });
        await api.login(email, password);
        navigate({ to: "/" });
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-background font-sans text-foreground antialiased">
      <div className="pointer-events-none absolute -top-40 left-1/2 h-[520px] w-[900px] -translate-x-1/2 rounded-full bg-primary/25 blur-[150px]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[380px] w-[520px] rounded-full bg-accent/10 blur-[130px]" />

      <section className="relative z-10 flex min-h-screen items-center justify-center px-6 py-16">
        <div className="w-full max-w-md">
          <div className="mb-7 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-primary to-accent font-display text-sm font-bold text-primary-foreground shadow-lg shadow-primary/30">
                V
              </div>
              <span className="font-display text-lg font-semibold tracking-tight text-card-foreground">
                Veridian
              </span>
            </div>
            <span className="text-xs text-muted-foreground">v2.4 · Secured</span>
          </div>

          <div className="rounded-3xl border border-border bg-glass p-8 shadow-[var(--shadow-glass)] backdrop-blur-xl">
            <div className="mb-7">
              <h1 className="font-display text-2xl font-semibold tracking-tight text-card-foreground">
                {mode === "signin" ? "Welcome back" : "Create your account"}
              </h1>
              <p className="mt-1.5 text-sm text-muted-foreground">
                {mode === "signin"
                  ? "Sign in to your attendance console."
                  : "Register to monitor your sessions."}
              </p>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="space-y-4">
                {mode === "signup" && (
                  <div>
                    <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Full name
                    </label>
                    <input
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      className="w-full rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground outline-none transition focus:border-primary/60 focus:ring-2 focus:ring-primary/20"
                      placeholder="Dana Whitfield"
                      required
                    />
                  </div>
                )}
                {mode === "signup" && (
                  <div>
                    <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      I am a
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      {(
                        [
                          ["student", "Student"],
                          ["ta", "Teaching assistant"],
                          ["instructor", "Instructor"],
                        ] as const
                      ).map(([value, label]) => (
                        <button
                          key={value}
                          type="button"
                          onClick={() => setDesiredRole(value)}
                          className={`rounded-xl border px-3 py-2.5 text-xs transition ${
                            desiredRole === value
                              ? "border-primary/60 bg-primary/15 text-primary"
                              : "border-border bg-background/60 text-muted-foreground hover:text-foreground"
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                <div>
                  <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Work email
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground outline-none transition focus:border-primary/60 focus:ring-2 focus:ring-primary/20"
                    placeholder="dana@veridian.edu"
                    required
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Password
                  </label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-foreground outline-none transition focus:border-primary/60 focus:ring-2 focus:ring-primary/20"
                    placeholder="••••••••••"
                    minLength={6}
                    required
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={busy}
                className="mt-6 w-full rounded-xl bg-gradient-to-r from-primary to-accent px-4 py-3 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/25 transition hover:brightness-110 active:scale-[.99] disabled:opacity-60"
              >
                {busy ? "Working…" : mode === "signin" ? "Sign in to console" : "Create account"}
              </button>
            </form>

            <p className="mt-6 text-center text-xs text-muted-foreground">
              {mode === "signin" ? "New to Veridian? " : "Already registered? "}
              <button
                type="button"
                onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
                className="cursor-pointer text-primary transition hover:text-card-foreground"
              >
                {mode === "signin" ? "Request access" : "Sign in"}
              </button>
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
