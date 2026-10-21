import { api } from "./api";

export const exportColumns = [
  "student_id",
  "student_name",
  "student_email",
  "session_date",
  "session_name",
  "status",
  "checked_in_at",
  "risk_score",
] as const;
export type AttendanceRecord = Record<(typeof exportColumns)[number], string | number | null>;

export function exportPath(course: string, start: string, end: string, format: "csv" | "json") {
  // Explicit inclusive instants cover the entire selected Singapore calendar day.
  const params = new URLSearchParams({
    format,
    start_date: `${start}T00:00:00+08:00`,
    end_date: `${end}T23:59:59.999999+08:00`,
  });
  return `/export/attendance/${encodeURIComponent(course)}?${params}`;
}

export function exportFilename(disposition: string | null, fallback: string, extension: string) {
  const encoded = disposition?.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const plain = disposition?.match(/filename="([^"]+)"|filename=([^;]+)/i);
  let name = plain?.[1] ?? plain?.[2]?.trim();
  try {
    if (encoded) name = decodeURIComponent(encoded);
  } catch {
    /* Use plain filename. */
  }
  return name && !/[\\/\x00-\x1f\x7f]/.test(name) && name.toLowerCase().endsWith(`.${extension}`)
    ? name
    : fallback;
}

export async function fetchExport(
  course: string,
  start: string,
  end: string,
  signal?: AbortSignal,
) {
  const response = await api.response(exportPath(course, start, end, "json"), { signal: signal ?? null });
  const records: AttendanceRecord[] = await response.json();
  if (!Array.isArray(records))
    throw new Error("The export response was invalid. Please try again.");
  return { records, disposition: response.headers.get("Content-Disposition") };
}

export function saveExport(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
