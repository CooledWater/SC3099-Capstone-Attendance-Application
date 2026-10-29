import { api } from "./api";
import { parseSingaporeDateTimeLocal } from "./time";

export type AuditRow = {
  id: string;
  timestamp: string;
  user_id: string | null;
  user_email: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  success: boolean;
  severity: string;
  details: Record<string, unknown> | null;
  ip_address?: string | null;
  user_agent?: string | null;
  device_id?: string | null;
};
export type AuditPage = { items: AuditRow[]; total: number; limit: number; offset: number };
export type AuditFilters = {
  userId: string;
  action: string;
  resourceType: string;
  resourceId: string;
  success: string;
  startDate: string;
  endDate: string;
};
export const emptyAuditFilters: AuditFilters = {
  userId: "",
  action: "",
  resourceType: "",
  resourceId: "",
  success: "",
  startDate: "",
  endDate: "",
};
export const auditActions = [
  "login_success",
  "login_failed",
  "logout",
  "user_created",
  "user_updated",
  "checkin_attempted",
  "checkin_approved",
  "checkin_flagged",
  "checkin_rejected",
  "checkin_appealed",
  "checkin_reviewed",
  "session_created",
  "session_updated",
  "session_deleted",
  "enrollment_added",
  "enrollment_removed",
  "device_registered",
  "face_enrolled",
  "data_exported",
  "security_violation",
] as const;

const detailLabels: Record<string, string> = {
  is_active: "Active",
  is_trusted: "Trusted",
  automatic: "Automatic update",
  bulk: "Bulk operation",
  fields: "Updated fields",
  previous_status: "Previous status",
};
const enumDetails = new Set([
  "reason",
  "event",
  "change",
  "role",
  "status",
  "previous_status",
  "decision",
  "type",
  "signal_type",
]);
function readableDetailKey(key: string) {
  const words = key
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/_/g, " ")
    .replace(/\bid\b/gi, "ID")
    .replace(/\bta\b/gi, "TA")
    .replace(/\bip\b/gi, "IP");
  return detailLabels[key] ?? words.charAt(0).toUpperCase() + words.slice(1);
}

/** Render structured audit metadata as readable points without changing API/export data. */
export function auditDetailPoints(details: Record<string, unknown> | null): string[] {
  const points: string[] = [];
  function valueText(value: unknown, key: string): string {
    if (value == null) return "Not provided";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (value === "") return "Empty";
    return typeof value === "string" && (enumDetails.has(key) || key === "fields")
      ? readableDetailKey(value)
      : String(value);
  }
  function visit(value: unknown, label: string, key: string) {
    if (Array.isArray(value)) {
      if (!value.length) points.push(`${label}: None`);
      else if (value.every((item) => item === null || typeof item !== "object")) {
        points.push(`${label}: ${value.map((item) => valueText(item, key)).join(", ")}`);
      } else value.forEach((item, index) => visit(item, `${label} · Item ${index + 1}`, key));
    } else if (value !== null && typeof value === "object") {
      const record = value as Record<string, unknown>;
      const keys = Object.keys(record);
      if (
        keys.length === 2 &&
        keys.includes("from") &&
        keys.includes("to") &&
        [record["from"], record["to"]].every((item) => item === null || typeof item !== "object")
      ) {
        points.push(
          `${label} changed from ${valueText(record["from"], key)} to ${valueText(record["to"], key)}.`,
        );
      } else if (!keys.length) points.push(`${label}: None`);
      else
        Object.entries(record).forEach(([child, item]) =>
          visit(item, `${label} · ${readableDetailKey(child)}`, child),
        );
    } else points.push(`${label}: ${valueText(value, key)}`);
  }
  Object.entries(details ?? {}).forEach(([key, value]) =>
    visit(value, readableDetailKey(key), key),
  );
  return points;
}

export function auditFilterError(filters: AuditFilters): string {
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (filters.userId.trim() && !uuid.test(filters.userId.trim())) return "Choose a valid user.";
  if (filters.resourceId.trim() && !uuid.test(filters.resourceId.trim()))
    return "Enter a valid resource UUID.";
  const start = filters.startDate ? parseSingaporeDateTimeLocal(filters.startDate) : null;
  const end = filters.endDate ? parseSingaporeDateTimeLocal(filters.endDate) : null;
  if (filters.startDate && !start) return "Enter a valid start date and time.";
  if (filters.endDate && !end) return "Enter a valid end date and time.";
  if (start && end && start > end) return "Start must be before or equal to end.";
  return "";
}

function filterParams(filters: AuditFilters) {
  const error = auditFilterError(filters);
  if (error) throw new Error(error);
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries({
    user_id: filters.userId,
    action: filters.action,
    resource_type: filters.resourceType,
    resource_id: filters.resourceId,
    success: filters.success,
  })) {
    if (value.trim()) params.set(key, value.trim());
  }
  if (filters.startDate)
    params.set("start_date", parseSingaporeDateTimeLocal(filters.startDate)!.toISOString());
  if (filters.endDate)
    params.set("end_date", parseSingaporeDateTimeLocal(filters.endDate)!.toISOString());
  return params;
}

export function fetchAuditPage(
  filters: AuditFilters,
  limit: number,
  offset: number,
  signal?: AbortSignal,
) {
  const params = filterParams(filters);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return api.request<AuditPage>(`/audit/?${params}`, { signal: signal ?? null });
}

export async function fetchAuditExport(filters: AuditFilters, signal?: AbortSignal) {
  const params = filterParams(filters);
  // Keep new events from pushing older rows between offset pages during export.
  if (!params.has("end_date")) params.set("end_date", new Date().toISOString());
  params.set("limit", "1000");
  const rows = new Map<string, AuditRow>();
  let offset = 0;
  while (true) {
    params.set("offset", String(offset));
    const page = await api.request<AuditPage>(`/audit/?${params}`, { signal: signal ?? null });
    page.items.forEach((row) => rows.set(row.id, row));
    offset += page.items.length;
    if (!page.items.length || offset >= page.total) return [...rows.values()];
  }
}

export function auditCsv(rows: AuditRow[]) {
  const cell = (value: string) => {
    // Quote CSV values and stop spreadsheet applications interpreting formulas.
    const safe = /^[=+@\-\t\r\n]/.test(value) ? `'${value}` : value;
    return `"${safe.replace(/"/g, '""')}"`;
  };
  return (
    "\uFEFF" +
    [
      ["timestamp", "user_email", "action", "severity", "details"],
      ...rows.map((row) => [
        row.timestamp,
        row.user_email ?? "",
        row.action,
        row.severity,
        row.details ? JSON.stringify(row.details) : "",
      ]),
    ]
      .map((row) => row.map(cell).join(","))
      .join("\r\n")
  );
}
