import type { CurrentUser } from "@/lib/api";

export type AppRole = "student" | "ta" | "instructor" | "admin";

const rank: Record<AppRole, number> = { student: 0, ta: 1, instructor: 2, admin: 3 };

export function useRole(user: CurrentUser | null) {
  const role = user?.role ?? "student";
  return { role, roles: [role], loading: false };
}

export const roleLabel: Record<AppRole, string> = {
  student: "Student",
  ta: "Teaching assistant",
  instructor: "Instructor",
  admin: "Administrator",
};
