import { useRef, useState } from "react";

import { api } from "@/lib/api";
import type { CourseRow } from "@/lib/attendance";
import { toSingaporeDateTimeLocal } from "@/lib/time";
import { exportColumns, exportFilename, exportPath, fetchExport, saveExport } from "@/lib/exports";

const input =
  "mt-2 w-full min-w-0 rounded-lg border border-border bg-secondary/40 p-3 text-sm text-foreground";
const button = "rounded-lg border px-3 py-2 text-sm disabled:opacity-50";
const today = () => toSingaporeDateTimeLocal(new Date().toISOString()).slice(0, 10);

export function ExportPanel({
  courses,
  loading,
  error,
}: {
  courses: CourseRow[];
  loading: boolean;
  error: boolean;
}) {
  const [courseId, setCourseId] = useState("");
  const course = courses.find((c) => c.id === courseId) ?? courses[0];
  const semesterStart = course?.semester_start_date ?? "";
  const [startOverride, setStart] = useState<string | null>(null);
  const start = startOverride ?? semesterStart;
  const [end, setEnd] = useState(today);
  const [format, setFormat] = useState<"csv" | "json">("csv");
  const [shortcut, setShortcut] = useState<"semester" | "month" | null>("semester");
  const semesterSelected = shortcut === "semester" && Boolean(semesterStart) && start === semesterStart && end === today();
  const monthSelected = shortcut === "month" && start === `${today().slice(0, 7)}-01` && end === today();

  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [message, setMessage] = useState("");

  const valid = Boolean(
    course && /^\d{4}-\d{2}-\d{2}$/.test(start) && /^\d{4}-\d{2}-\d{2}$/.test(end) && start <= end,
  );

  const courseName = (course?.name ?? "Course").replace(/[\\/:*?"<>|\x00-\x1f\x7f]/g, "_").trim().replace(/^\.+|\.+$/g, "") || "Course";
  const fallback = `${courseName} attendance.${format}`;
  const expectedFilename = fallback;
  async function download() {
    if (!valid || lock.current) return;
    lock.current = true;
    setBusy(true);
    setMessage("");
    try {
      if (format === "json") {
        const data = await fetchExport(course!.id, start, end);
        saveExport(
          new Blob([JSON.stringify(data.records, null, 2)], { type: "application/json" }),
          exportFilename(data.disposition, fallback, format),
        );
        setMessage(
          data.records.length
            ? "JSON download ready."
            : "No attendance records matched. Downloaded an empty JSON array.",
        );
      } else {
        const response = await api.response(exportPath(course!.id, start, end, "csv"), {
          headers: { Accept: "text/csv" },
        });
        const blob = await response.blob();
        const empty = (await blob.text()).trim() === exportColumns.join(",");
        saveExport(
          blob,
          exportFilename(response.headers.get("Content-Disposition"), fallback, format),
        );
        setMessage(
          empty ? "No attendance records matched. Downloaded a CSV with column headings only." : "CSV download ready.",
        );
      }
    } catch (failure) {
      setMessage(
        failure instanceof Error
          ? failure.message
          : "Could not download attendance. Please try again.",
      );
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  if (loading) return <p role="status">Loading courses...</p>;
  if (error) return <p role="alert">Could not load your courses. Refresh to retry.</p>;
  if (!course) return <p>No courses are assigned to your account.</p>;
  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">Export attendance</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Choose a course and date range, then download its attendance records.
        </p>
      </div>
      <div className="grid min-w-0 gap-5 lg:grid-cols-[3fr_2fr]">
        <div className="min-w-0 space-y-6 rounded-2xl border border-border bg-glass p-6">
          <h3 className="font-semibold">Export settings</h3>
          <label className="block text-sm">
            Course
            <select
              aria-label="Export course"
              className={input}
              value={course.id}
              disabled={busy}
              onChange={(e) => {
                setCourseId(e.target.value);
                setMessage("");
              }}
            >
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code} · {c.name}
                </option>
              ))}
            </select>
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="min-w-0 text-sm">
              Start date
              <input
                aria-label="Start date"
                className={input}
                type="date"
                value={start}
                disabled={busy}
                onChange={(e) => {
                  setStart(e.target.value);
                  setShortcut(null);
                  setMessage("");
                }}
              />
            </label>
            <label className="min-w-0 text-sm">
              End date
              <input
                aria-label="End date"
                className={input}
                type="date"
                value={end}
                disabled={busy}
                onChange={(e) => {
                  setEnd(e.target.value);
                  setShortcut(null);
                  setMessage("");
                }}
              />
            </label>
          </div>
          {start && end && start > end && (
            <p role="alert" className="text-sm text-destructive">
              Start date must not be after end date.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <button
              className={`${button} ${semesterSelected ? "border-primary bg-primary/15" : "border-border bg-secondary/40"}`}
              aria-pressed={semesterSelected}
              disabled={busy || !semesterStart}
              onClick={() => {
                setStart(semesterStart);
                setShortcut("semester");
                setEnd(today());
                setMessage("");
              }}
            >
              Semester to date
            </button>
            <button
              className={`${button} ${monthSelected ? "border-primary bg-primary/15" : "border-border bg-secondary/40"}`}
              aria-pressed={monthSelected}
              disabled={busy}
              onClick={() => {
                setStart(`${today().slice(0, 7)}-01`);
                setShortcut("month");
                setEnd(today());
                setMessage("");
              }}
            >
              This month
            </button>
          </div>
          {!semesterStart && (
            <p className="text-sm text-muted-foreground">Choose a start date, or use This month.</p>
          )}
          <fieldset>
            <legend className="text-sm">File format</legend>
            <div className="mt-2 grid grid-cols-2 gap-3">
              {(["csv", "json"] as const).map((f) => (
                <label
                  key={f}
                  className={`rounded-lg border p-3 text-sm ${format === f ? "border-primary bg-primary/15" : "border-border bg-secondary/40"}`}
                >
                  <input
                    type="radio"
                    name="export-format"
                    value={f}
                    checked={format === f}
                    disabled={busy}
                    onChange={() => {
                      setFormat(f);
                      setMessage("");
                    }}
                  />{" "}
                  <span>{f.toUpperCase()}</span>
                  <span className="mt-1 block text-xs text-muted-foreground">
                    {f === "csv" ? "Excel / spreadsheets" : "Structured data"}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
        </div>
        <div className="min-w-0 space-y-6 rounded-2xl border border-border bg-glass p-6">
          <h3 className="font-semibold">Download summary</h3>
          <dl className="space-y-5 text-sm">
            <div>
              <dt className="text-muted-foreground">Course</dt>
              <dd className="mt-1">
                {course.code} · {course.name}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Date range</dt>
              <dd className="mt-1">
                {start || "Choose a start date"} → {end || "Choose an end date"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Expected filename</dt>
              <dd className="mt-1 break-all">{expectedFilename}</dd>
            </div>
          </dl>
          <button
            className="w-full rounded-lg bg-primary px-4 py-3 text-sm font-medium text-primary-foreground disabled:opacity-50"
            disabled={!valid || busy}
            onClick={() => void download()}
          >
            {busy ? "Preparing download..." : `Download ${format.toUpperCase()}`}
          </button>
          {message && (
            <p role="status" className="text-sm">
              {message}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
