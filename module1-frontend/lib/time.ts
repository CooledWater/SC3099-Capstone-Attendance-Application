const SINGAPORE_TIME_ZONE = 'Asia/Singapore';

// The backend stores UTC but can serialize datetimes without a timezone suffix.
export function parseApiDateTime(value: string): Date {
  const hasTimeZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  return new Date(hasTimeZone ? value : `${value}Z`);
}

export function formatSingaporeDateTime(
  value: string | Date,
  options: Intl.DateTimeFormatOptions = { dateStyle: 'medium', timeStyle: 'short' },
): string {
  const date = typeof value === 'string' ? parseApiDateTime(value) : value;
  if (Number.isNaN(date.getTime())) return 'Invalid time';
  return `${new Intl.DateTimeFormat('en-SG', {
    ...options,
    timeZone: SINGAPORE_TIME_ZONE,
  }).format(date)} SGT`;
}

export function singaporeGreeting(now = new Date()): string {
  const hour = Number(new Intl.DateTimeFormat('en-GB', {
    timeZone: SINGAPORE_TIME_ZONE, hour: '2-digit', hourCycle: 'h23',
  }).format(now));
  return hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening';
}
