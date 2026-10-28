import { parseApiDateTime } from "./time";

export type StudentCourse = {
  course_id: string;
  course_code: string;
  attendance_rate?: number | null;
  sessions_attended?: number | null;
  total_sessions?: number | null;
  average_risk_score?: number | null;
};
export type StudentCheckIn = {
  course_id?: string;
  session_name: string;
  course_code: string;
  checked_in_at: string;
  status: string;
};
export type StudentAttendance = {
  student_id: string;
  student_name: string;
  student_email: string;
  courses: StudentCourse[];
  recent_checkins: StudentCheckIn[];
};

export function courseCheckIns(data: StudentAttendance, course: StudentCourse) {
  const uniqueCode =
    data.courses.filter((item) => item.course_code === course.course_code).length === 1;
  return {
    ambiguous:
      !uniqueCode &&
      data.recent_checkins.some(
        (item) => !item.course_id && item.course_code === course.course_code,
      ),
    records: data.recent_checkins
      .filter((item) =>
        item.course_id
          ? item.course_id === course.course_id
          : uniqueCode && item.course_code === course.course_code,
      )
      .sort(
        (a, b) =>
          parseApiDateTime(b.checked_in_at).getTime() - parseApiDateTime(a.checked_in_at).getTime(),
      ),
  };
}

export function availableNumber(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}
