export function formatDateDisplay(value?: string | Date | null, dayOffset = 0): string {
  if (!value) return "";

  const baseDate = value instanceof Date ? new Date(value) : new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(baseDate.getTime())) return "";

  const target = new Date(baseDate);
  target.setUTCDate(target.getUTCDate() + dayOffset);
  return `${target.getUTCDate()} ${target.toLocaleString("en-US", { month: "short", timeZone: "UTC" })}`;
}

export function formatTime12h(
  value?: string,
  dayOffset = 0,
  travelDate?: string | Date | null,
): string {
  if (!value) return "";

  const match = /^(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?$/.exec(value);
  if (!match) return value;

  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour > 23 || minute > 59) return value;

  const displayHour = hour % 12 || 12;
  const period = hour < 12 ? "AM" : "PM";
  const prefix = `${displayHour}:${match[2]} ${period}`;

  if (dayOffset > 0 && travelDate) {
    return `${prefix}, ${formatDateDisplay(travelDate, dayOffset)}`;
  }

  return prefix;
}
