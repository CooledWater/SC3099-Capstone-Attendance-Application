import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  assignTA,
  fetchAdminCourses,
  fetchCourseTAs,
  fetchStaff,
  unassignTA,
  type AdminCourse,
} from "@/lib/admin";

const input =
  "min-w-0 max-w-full rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm";
const button = `${input} hover:bg-primary/15 disabled:opacity-50`;

export function AdminCourses({ userId }: { userId: string }) {
  const qc = useQueryClient();
  const [active, setActive] = useState(true);
  const [selected, setSelected] = useState("");
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState({ code: "", name: "", semester: "", instructor_id: "" });
  const courses = useQuery({
    queryKey: ["admin-courses", userId, active],
    queryFn: ({ signal }) => fetchAdminCourses(active, signal),
  });
  const instructors = useQuery({
    queryKey: ["admin-staff", userId, "instructor"],
    queryFn: ({ signal }) => fetchStaff("instructor", signal),
  });
  const course = courses.data?.find((item) => item.id === selected) ?? courses.data?.[0];
  const create = useMutation({
    mutationFn: () =>
      api.request<AdminCourse>("/courses/", {
        method: "POST",
        body: JSON.stringify({
          ...draft,
          code: draft.code.trim(),
          name: draft.name.trim(),
          semester: draft.semester.trim(),
          instructor_id: draft.instructor_id || null,
        }),
      }),
    onSuccess: async (result) => {
      setSelected(result.id);
      setActive(true);
      setCreating(false);
      setDraft({ code: "", name: "", semester: "", instructor_id: "" });
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["admin-courses"] }),
        qc.invalidateQueries({ queryKey: ["courses"] }),
      ]);
    },
  });
  return (
    <section className="space-y-5 rounded-2xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="mr-auto text-lg font-semibold">Courses and staff</h2>
        <label>
          Course status{" "}
          <select
            className={input}
            value={String(active)}
            onChange={(e) => {
              setActive(e.target.value === "true");
              setSelected("");
            }}
          >
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </label>
        <button
          className="rounded-lg bg-gradient-to-r from-primary to-accent px-3 py-2 text-sm font-medium text-primary-foreground transition hover:brightness-110"
          onClick={() => {
            create.reset();
            setCreating(!creating);
          }}
        >
          Create course
        </button>
      </div>
      {creating && (
        <form
          className="grid gap-3 rounded-xl border border-border p-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          {(["code", "name", "semester"] as const).map((field) => (
            <label key={field} className="grid min-w-0 gap-1 capitalize">
              {field}
              <input
                className={input}
                required
                maxLength={field === "code" || field === "semester" ? 20 : 255}
                value={draft[field]}
                onChange={(e) => setDraft({ ...draft, [field]: e.target.value })}
              />
            </label>
          ))}
          <label className="grid min-w-0 gap-1">
            Instructor
            <select
              className={input}
              value={draft.instructor_id}
              onChange={(e) => setDraft({ ...draft, instructor_id: e.target.value })}
            >
              <option value="">Unassigned</option>
              {instructors.data?.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.full_name} · {user.email}
                </option>
              ))}
            </select>
          </label>
          {create.isError && <p role="alert">{create.error.message}</p>}
          <button
            className={button}
            disabled={
              create.isPending || !draft.code.trim() || !draft.name.trim() || !draft.semester.trim()
            }
          >
            Save course
          </button>
        </form>
      )}
      {courses.isPending && <p role="status">Loading courses…</p>}
      {courses.isError && (
        <p role="alert">
          Could not load courses.{" "}
          <button className={button} onClick={() => void courses.refetch()}>
            Retry
          </button>
        </p>
      )}
      {!courses.isPending && !courses.isError && !course && (
        <p>No {active ? "active" : "inactive"} courses.</p>
      )}
      {course && (
        <>
          <label className="grid min-w-0 gap-2">
            Course
            <select
              className={input}
              value={course.id}
              onChange={(e) => setSelected(e.target.value)}
            >
              {courses.data?.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.code} · {item.name} · {item.semester}
                </option>
              ))}
            </select>
          </label>
          <CourseStaff key={course.id} course={course} userId={userId} />
        </>
      )}
    </section>
  );
}

function CourseStaff({ course, userId }: { course: AdminCourse; userId: string }) {
  const qc = useQueryClient();
  const [instructorId, setInstructorId] = useState(course.instructor_id ?? "");
  const [taId, setTaId] = useState("");
  const [name, setName] = useState(course.name);
  const [semester, setSemester] = useState(course.semester);
  const instructors = useQuery({
    queryKey: ["admin-staff", userId, "instructor"],
    queryFn: ({ signal }) => fetchStaff("instructor", signal),
  });
  const tas = useQuery({
    queryKey: ["admin-staff", userId, "ta"],
    queryFn: ({ signal }) => fetchStaff("ta", signal),
  });
  const assignments = useQuery({
    queryKey: ["admin-course-tas", userId, course.id],
    queryFn: ({ signal }) => fetchCourseTAs(course.id, signal),
  });
  const change = useMutation({
    mutationFn: (action: () => Promise<unknown>) => action(),
    onSuccess: async () => {
      setTaId("");
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["admin-courses"] }),
        qc.invalidateQueries({ queryKey: ["courses"] }),
        qc.invalidateQueries({ queryKey: ["admin-course-tas"] }),
        qc.invalidateQueries({ queryKey: ["sessions"] }),
        qc.invalidateQueries({ queryKey: ["audit-logs"] }),
      ]);
    },
  });
  const pending = change.isPending;
  const instructorChanged = instructorId !== (course.instructor_id ?? "");
  const hasChanges =
    name.trim() !== course.name || semester.trim() !== course.semester || instructorChanged;
  const cannotSave =
    pending ||
    !hasChanges ||
    !name.trim() ||
    !semester.trim() ||
    instructors.isPending ||
    instructors.isError;
  const availableTAs = (tas.data ?? []).filter(
    (ta) => !assignments.data?.items.some((item) => item.user_id === ta.id),
  );
  return (
    <div className="space-y-5">
      {change.isError && (
        <p role="alert" className="text-destructive">
          {change.error.message}
        </p>
      )}
      {change.isSuccess && (
        <p role="status" className="text-accent">
          Course updated.
        </p>
      )}
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (cannotSave) return;
          if (
            instructorChanged &&
            !window.confirm(
              `Change the instructor for ${course.code}? Existing session owners remain unchanged.`,
            )
          )
            return;
          change.mutate(() =>
            api.request(`/courses/${encodeURIComponent(course.id)}`, {
              method: "PUT",
              body: JSON.stringify({
                name: name.trim(),
                semester: semester.trim(),
                instructor_id: instructorId || null,
              }),
            }),
          );
        }}
      >
        <label className="grid min-w-0 gap-1">
          Course name
          <input
            className={input}
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label className="grid min-w-0 gap-1">
          Semester
          <input
            className={input}
            required
            maxLength={20}
            value={semester}
            onChange={(e) => setSemester(e.target.value)}
          />
        </label>
        <label className="grid min-w-0 gap-1">
          Assigned instructor
          <select
            className={input}
            value={instructorId}
            disabled={instructors.isPending || instructors.isError}
            onChange={(e) => setInstructorId(e.target.value)}
          >
            <option value="">Unassigned</option>
            {course.instructor_id &&
              !instructors.data?.some((user) => user.id === course.instructor_id) && (
                <option value={course.instructor_id}>
                  {course.instructor_name ?? "Current instructor"} (unavailable)
                </option>
              )}
            {instructors.data?.map((user) => (
              <option key={user.id} value={user.id}>
                {user.full_name} · {user.email}
              </option>
            ))}
          </select>
        </label>
        <button className={button} disabled={cannotSave}>
          {pending ? "Saving…" : "Save changes"}
        </button>
      </form>
      {instructors.isError && (
        <p role="alert">
          Could not load instructors.{" "}
          <button className={button} onClick={() => void instructors.refetch()}>
            Retry
          </button>
        </p>
      )}
      <div className="space-y-3 border-t border-border pt-4">
        <h3 className="font-medium">Teaching assistants</h3>
        <p className="text-sm text-muted-foreground">
          Assignments grant access to this course’s sessions and check-ins.
        </p>
        {assignments.isPending && <p role="status">Loading assignments…</p>}
        {assignments.isError && (
          <p role="alert">
            Could not load TA assignments.{" "}
            <button className={button} onClick={() => void assignments.refetch()}>
              Retry
            </button>
          </p>
        )}
        {assignments.data?.items.map((ta) => (
          <div
            key={ta.user_id}
            className="flex flex-wrap items-center gap-3 rounded-lg border border-border p-3"
          >
            <span className="mr-auto">
              {ta.full_name} · {ta.email}
              {!ta.is_active && " (inactive)"}
            </span>
            <button
              className={button}
              disabled={pending}
              onClick={() => {
                if (window.confirm(`Remove ${ta.full_name} from ${course.code}?`))
                  change.mutate(() => unassignTA(course.id, ta.user_id));
              }}
            >
              Remove TA
            </button>
          </div>
        ))}
        {assignments.isSuccess && !assignments.data.items.length && <p>No TAs assigned.</p>}
        <form
          className="flex flex-wrap gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            change.mutate(() => assignTA(course.id, taId));
          }}
        >
          <select
            aria-label="Teaching assistant to assign"
            className={input}
            value={taId}
            onChange={(e) => setTaId(e.target.value)}
            disabled={tas.isPending || tas.isError || !assignments.isSuccess}
          >
            <option value="">Select an active TA</option>
            {availableTAs.map((user) => (
              <option key={user.id} value={user.id}>
                {user.full_name} · {user.email}
              </option>
            ))}
          </select>
          <button className={button} disabled={pending || !taId || !assignments.isSuccess}>
            Assign TA
          </button>
        </form>
        {tas.isError && (
          <p role="alert">
            Could not load TAs.{" "}
            <button className={button} onClick={() => void tas.refetch()}>
              Retry
            </button>
          </p>
        )}
      </div>
      {course.is_active && (
        <button
          className={`${button} text-destructive`}
          disabled={pending}
          onClick={() => {
            if (window.confirm(`Deactivate ${course.code}? Attendance history will be retained.`))
              change.mutate(() =>
                api.request(`/courses/${encodeURIComponent(course.id)}`, { method: "DELETE" }),
              );
          }}
        >
          Deactivate course
        </button>
      )}
    </div>
  );
}
