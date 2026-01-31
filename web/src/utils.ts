export const numberFmt = new Intl.NumberFormat("en-US");

export function formatNumber(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return numberFmt.format(value);
}

const TZ = "Asia/Seoul";

export function formatTimeForChart(value: string, hours: number) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  const formatter = new Intl.DateTimeFormat("ko-KR", {
    timeZone: TZ,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const formatterMD = new Intl.DateTimeFormat("ko-KR", {
    timeZone: TZ,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    hour12: false,
  });
  if (hours <= 24) {
    return formatter.format(date).replace(/:(\d{2})$/, ":00");
  }
  return formatterMD.format(date) + "시";
}

export function formatTime(
  value: string | null | undefined,
  timeZone: string | unknown = TZ
) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const tz = typeof timeZone === "string" ? timeZone : TZ;
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
    timeZone: TZ,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}
