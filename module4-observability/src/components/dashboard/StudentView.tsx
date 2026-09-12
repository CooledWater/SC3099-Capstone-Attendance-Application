import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { KpiCard } from "./KpiCard";
import { CourseHistory } from "./CourseHistory";
import { LiveActivity } from "./LiveActivity";
import { fetchMyCheckIns, toRows } from "@/lib/attendance";

export function StudentView() {
  const q = useQuery({
    queryKey: ["my-check-ins"],
    queryFn: fetchMyCheckIns,
    refetchInterval: 30000,
  });
  const rows = useMemo(() => toRows(q.data ?? []), [q.data]);

  const approved = rows.filter((r) => r.status === "approved").length;
  const flagged = rows.filter((r) => r.status === "flagged").length;
  const noShow = rows.filter((r) => r.status === "no_show").length;
  const rate = rows.length ? Math.round((approved / rows.length) * 100) : 0;
  const courses = new Set(rows.map((r) => r.course)).size;

  return (
    <>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <KpiCard
          label="My check-ins"
          value={String(rows.length)}
          note={`across ${courses} course${courses === 1 ? "" : "s"}`}
          tone="brand"
          bars={[35, 50, 44, 68, 60, 100]}
        />
        <KpiCard
          label="Attendance rate"
          value={`${rate}%`}
          note={`${approved} approved records`}
          tone="accent"
          progress={rate}
        />
        <KpiCard
          label="Flagged"
          value={String(flagged)}
          note="check-ins under review"
          tone="warning"
          progress={rows.length ? (flagged / rows.length) * 100 : 0}
        />
        <KpiCard
          label="Missed sessions"
          value={String(noShow)}
          note="recorded as no-show"
          tone={noShow > 0 ? "danger" : "accent"}
          progress={rows.length ? (noShow / rows.length) * 100 : 0}
        />
        <CourseHistory rows={rows} />
        <LiveActivity rows={rows.slice(0, 4)} />
      </div>
    </>
  );
}
