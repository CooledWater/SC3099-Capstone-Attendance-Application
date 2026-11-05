import { api, type AppRole } from "./api";
import type { ApiSession, CourseRow } from "./attendance";

export type AdminUser = {
  id: string;
  email: string;
  full_name: string;
  role: AppRole;
  is_active: boolean;
};
export type Page<T> = { items: T[]; total: number; limit: number; offset: number };
export type AdminCourse = CourseRow & {
  semester: string;
  instructor_name: string | null;
  is_active: boolean;
};
export type TAAssignment = {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  is_active: boolean;
};

export function fetchUsers(params: URLSearchParams, signal?: AbortSignal) {
  return api.request<Page<AdminUser>>(`/users/?${params}`, { signal: signal ?? null });
}

// Assignment pickers must include candidates beyond the first API page.
export async function fetchStaff(role: "instructor" | "ta", signal?: AbortSignal) {
  const items: AdminUser[] = [];
  while (true) {
    const page = await fetchUsers(
      new URLSearchParams({
        role,
        is_active: "true",
        limit: "100",
        offset: String(items.length),
      }),
      signal,
    );
    items.push(...page.items);
    if (!page.items.length || items.length >= page.total) return items;
  }
}

export async function fetchAdminCourses(active: boolean, signal?: AbortSignal) {
  const items: AdminCourse[] = [];
  while (true) {
    const page = await api.request<Page<AdminCourse>>(
      `/courses/?is_active=${active}&limit=100&offset=${items.length}`,
      { signal: signal ?? null },
    );
    items.push(...page.items);
    if (!page.items.length || items.length >= page.total) return items;
  }
}

export const fetchCourseTAs = (courseId: string, signal?: AbortSignal) =>
  api.request<{ items: TAAssignment[]; total: number }>(
    `/admin/courses/${encodeURIComponent(courseId)}/tas`,
    { signal: signal ?? null },
  );

export const saveInstructor = (courseId: string, instructorId: string) =>
  api.request(`/courses/${encodeURIComponent(courseId)}`, {
    method: "PUT",
    body: JSON.stringify({ instructor_id: instructorId || null }),
  });

export const assignTA = (courseId: string, userId: string) =>
  api.request(`/admin/courses/${encodeURIComponent(courseId)}/tas`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId }),
  });

export const unassignTA = (courseId: string, userId: string) =>
  api.request(`/admin/courses/${encodeURIComponent(courseId)}/tas/${encodeURIComponent(userId)}`, {
    method: "DELETE",
  });

export async function fetchCourseSessions(courseId: string, signal?: AbortSignal) {
  const items: ApiSession[] = [];
  while (true) {
    const params = new URLSearchParams({
      course_id: courseId,
      limit: "100",
      offset: String(items.length),
    });
    const page = await api.request<Page<ApiSession>>(`/sessions/?${params}`, {
      signal: signal ?? null,
    });
    items.push(...page.items);
    if (!page.items.length || items.length >= page.total) return items;
  }
}

export type TASessionPage = {
  items: { session_id: string }[];
  total: number;
};

const taSessionsPath = (courseId: string, userId: string) =>
  `/admin/courses/${encodeURIComponent(courseId)}/tas/${encodeURIComponent(userId)}/sessions`;

export const fetchTASessions = (courseId: string, userId: string, signal?: AbortSignal) =>
  api.request<TASessionPage>(taSessionsPath(courseId, userId), { signal: signal ?? null });

export const assignTASessions = (courseId: string, userId: string, sessionIds: string[]) =>
  api.request<TASessionPage & { assigned: string[]; already_assigned: string[] }>(
    taSessionsPath(courseId, userId),
    { method: "POST", body: JSON.stringify({ session_ids: sessionIds }) },
  );

export const updateAdminUser = (userId: string, updates: { role?: AppRole; is_active?: boolean }) =>
  api.request(`/users/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });

// Module 2 distinguishes active pending approvals from rejected device-limit requests.
export const fetchPendingDeviceCount = (signal?: AbortSignal) =>
  api.request<{ total: number }>("/devices/?limit=1&offset=0&approval_status=pending", {
    signal: signal ?? null,
  });
