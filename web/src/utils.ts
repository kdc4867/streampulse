export const numberFmt = new Intl.NumberFormat("en-US");

export function formatNumber(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return numberFmt.format(value);
}

export function formatTimeForChart(value: string, hours: number) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  const h = date.getUTCHours();
  if (hours <= 24) {
    return `${String(h).padStart(2, "0")}:00`;
  }
  const m = date.getUTCMonth() + 1;
  const d = date.getUTCDate();
  return `${m}/${d} ${h}시`;
}

export function formatTime(
  value: string | null | undefined,
  timeZone: string | unknown = "UTC"
) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const tz = typeof timeZone === "string" ? timeZone : "UTC";
  return date.toLocaleString("ko-KR", {
    timeZone: tz,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function formatTimeShort(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString("ko-KR", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
  });
}
