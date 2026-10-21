import { api } from "./api";

export type RosterStudent = {
  id: string;
  student_id: string;
  student_name: string;
  student_email: string;
  enrolled_at: string;
  is_active: boolean;
};
export type Roster = {
  course_id: string;
  course_code: string;
  total_enrolled: number;
  total_records: number;
  active_count: number;
  inactive_count: number;
  matching_count: number;
  students: RosterStudent[];
};
export type BulkResult = {
  enrolled: number;
  already_enrolled: number;
  not_found: number;
  created: number;
  details: {
    email: string;
    status: string;
    error?: string;
    invitation_status?: string;
    invitation_pending?: boolean;
    invitation_error?: string;
  }[];
};

export function parseEnrollmentEmails(text: string) {
  const emails = [
    ...new Set(
      text
        .split(/[\n,;]+/)
        .map((email) => email.trim())
        .filter(Boolean),
    ),
  ];
  const invalid = emails.filter((email) => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email));
  return { emails, invalid };
}

export function fetchRoster(
  courseId: string,
  status: string,
  search: string,
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({ is_active: status, search });
  return api.request<Roster>(`/enrollments/course/${encodeURIComponent(courseId)}?${params}`, {
    signal: signal ?? null,
  });
}
export const enrollStudent = (courseId: string, studentId: string) =>
  api.request("/enrollments/", {
    method: "POST",
    body: JSON.stringify({ course_id: courseId, student_id: studentId.trim() }),
  });
export const bulkEnroll = (courseId: string, emails: string[], createAccounts: boolean) =>
  api.request<BulkResult>("/enrollments/bulk", {
    method: "POST",
    body: JSON.stringify({
      course_id: courseId,
      student_emails: emails,
      create_accounts: createAccounts,
    }),
  });
export const removeEnrollment = (enrollmentId: string) =>
  api.request<void>(`/enrollments/${encodeURIComponent(enrollmentId)}`, { method: "DELETE" });

export type InvitationResult = {
  email: string;
  invitation_status: string;
  invitation_pending: boolean;
  invitation_error?: string | null;
};
export const fetchInvitations = (courseId: string) =>
  api.request<{ items: InvitationResult[] }>(
    `/enrollments/course/${encodeURIComponent(courseId)}/invitations`,
  );
export const resendInvitation = (courseId: string, email: string) =>
  api.request(`/enrollments/invitations/resend`, {
    method: "POST",
    body: JSON.stringify({ course_id: courseId, email }),
  });
