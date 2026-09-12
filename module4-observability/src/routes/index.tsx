import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { useRole, roleLabel, type AppRole } from "@/hooks/useRole";
import { StudentView } from "@/components/dashboard/StudentView";
import { TaView } from "@/components/dashboard/TaView";
import { InstructorView } from "@/components/dashboard/InstructorView";
import { AdminView } from "@/components/dashboard/AdminView";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Attendance Console — Veridian Observability" },
      {
        name: "description",
        content:
          "Role-aware attendance console: students track their own history, TAs review sessions they assist, instructors get course analytics and admins see system-wide metrics.",
      },
      { property: "og:title", content: "Attendance Console — Veridian Observability" },
      {
        property: "og:description",
        content:
          "Monitor sessions, check-in rates and flagged check-ins in real time from one role-aware console.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Dashboard,
});

const headline = {
  student: {
    eyebrow: "My attendance",
    title: "Your check-in history",
    blurb: "Everything recorded against your account.",
  },
  ta: {
    eyebrow: "Assistant console",
    title: "Sessions you assist",
    blurb: "Check-ins for the courses you support.",
  },
  instructor: {
    eyebrow: "Attendance console",
    title: "Instructor overview",
    blurb: "Course analytics and student-level detail.",
  },
  admin: {
    eyebrow: "System console",
    title: "Institution overview",
    blurb: "System-wide metrics across every course.",
  },
} as const;

function Dashboard() {
  const navigate = useNavigate();
  const { session, user, loading } = useAuth();
  const { role, loading: roleLoading } = useRole(user);
  const [now, setNow] = useState(() => Date.now());
  const [viewAs, setViewAs] = useState<AppRole>("admin");

  useEffect(() => {
    if (!loading && !session) navigate({ to: "/auth" });
  }, [loading, session, navigate]);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(t);
  }, []);

  if (loading || !session || roleLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-background text-sm text-muted-foreground">
        Loading console…
      </div>
    );
  }

  const activeRole = role === "admin" ? viewAs : role;
  const copy = headline[activeRole];

  return (
    <div className="relative min-h-screen overflow-hidden bg-background font-sans text-foreground antialiased">
      <div className="pointer-events-none absolute -top-40 left-1/2 h-[520px] w-[900px] -translate-x-1/2 rounded-full bg-primary/25 blur-[150px]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[380px] w-[520px] rounded-full bg-accent/10 blur-[130px]" />

      <section className="relative z-10 mx-auto max-w-7xl px-6 py-10 pb-24">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-primary">{copy.eyebrow}</p>
            <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight text-card-foreground">
              {copy.title}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {copy.blurb} Signed in as {user?.email}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {role === "admin" && (
              <div className="flex items-center gap-1 rounded-full border border-border bg-glass p-1">
                <span className="px-2 text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                  View as
                </span>
                {(["admin", "instructor", "ta", "student"] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => setViewAs(r)}
                    className={`rounded-full px-2.5 py-1 text-xs transition ${
                      viewAs === r
                        ? "bg-primary/20 text-primary"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {roleLabel[r]}
                  </button>
                ))}
              </div>
            )}
            <span className="rounded-full border border-primary/40 bg-primary/15 px-3 py-1.5 text-xs text-primary">
              {roleLabel[activeRole]}
            </span>
            <span className="flex items-center gap-2 rounded-full border border-border bg-glass px-3 py-1.5 text-xs text-foreground">
              <span className="size-1.5 rounded-full bg-accent" />
              Live · refreshed {new Date(now).toLocaleTimeString()}
            </span>
            <button
              onClick={() => api.logout().then(() => navigate({ to: "/auth" }))}
              className="rounded-full border border-border bg-glass px-3 py-1.5 text-xs text-muted-foreground transition hover:text-foreground"
            >
              Sign out
            </button>
          </div>
        </div>

        {activeRole === "admin" && <AdminView />}
        {activeRole === "instructor" && <InstructorView />}
        {activeRole === "ta" && user && <TaView userId={user.id} />}
        {activeRole === "student" && <StudentView />}
      </section>
    </div>
  );
}
