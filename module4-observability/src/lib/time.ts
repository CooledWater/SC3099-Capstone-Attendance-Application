const SINGAPORE_TIME_ZONE = "Asia/Singapore";
const SINGAPORE_UTC_OFFSET_MINUTES = 8 * 60;

export function parseApiDateTime(value: string): Date {
  const hasTimeZone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
  return new Date(hasTimeZone ? value : `${value}Z`);
}

export function parseSingaporeDateTimeLocal(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(value);
  if (!match) return null;

  const [, yearText, monthText, dayText, hourText, minuteText, secondText = "0"] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const hour = Number(hourText);
  const minute = Number(minuteText);
  const second = Number(secondText);
  const localTime = new Date(Date.UTC(year, month - 1, day, hour, minute, second));

  if (
    localTime.getUTCFullYear() !== year ||
    localTime.getUTCMonth() !== month - 1 ||
    localTime.getUTCDate() !== day ||
    hour > 23 ||
    minute > 59 ||
    second > 59
  ) {
    return null;
  }

  return new Date(localTime.getTime() - SINGAPORE_UTC_OFFSET_MINUTES * 60_000);
}

export function toSingaporeDateTimeLocal(value: string): string {
  const date = parseApiDateTime(value);
  if (Number.isNaN(date.getTime())) return "";

  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: SINGAPORE_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? "";

  return `${part("year")}-${part("month")}-${part("day")}T${part("hour")}:${part("minute")}`;
}

export function formatSingaporeDateTime(
  value: string,
  options: Intl.DateTimeFormatOptions = { dateStyle: "medium", timeStyle: "short" },
): string {
  const date = parseApiDateTime(value);
  if (Number.isNaN(date.getTime())) return "Invalid time";

  return new Intl.DateTimeFormat(undefined, {
    ...options,
    timeZone: SINGAPORE_TIME_ZONE,
  }).format(date);
}
