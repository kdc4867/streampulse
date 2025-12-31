export const numberFmt = new Intl.NumberFormat("en-US");

export function formatNumber(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return numberFmt.format(value);
}

export function formatTime(value: string | null | undefined, tzLabel = "UTC") {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const formatted = date.toLocaleString("ko-KR", {
    timeZone: "UTC",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${formatted} ${tzLabel}`;
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
