export function formatTime12h(value?: string, dayOffset = 0): string {
  if (!value) return "";

  const match = /^(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?$/.exec(value);
  if (!match) return value;

  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour > 23 || minute > 59) return value;

  const displayHour = hour % 12 || 12;
  const period = hour < 12 ? "AM" : "PM";
  const nextDay = dayOffset > 0 ? " (next day)" : "";
  return `${displayHour}:${match[2]} ${period}${nextDay}`;
}
