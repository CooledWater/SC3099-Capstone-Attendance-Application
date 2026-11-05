export function formatCourseLabel(
  code: string | null | undefined,
  name?: string | null,
  separator = " · ",
) {
  const courseCode = code?.trim();
  const courseName = name?.trim();
  if (!courseCode) return courseName ?? "";
  return !courseName || courseName.toLowerCase() === courseCode.toLowerCase()
    ? courseCode
    : `${courseCode}${separator}${courseName}`;
}
