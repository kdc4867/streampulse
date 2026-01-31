const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function getLive() {
  return fetchJson<{ data: unknown[] }>("/api/live");
}

export function getEvents(opts?: { since?: string; limit?: number }) {
  const qs = new URLSearchParams();
  if (opts?.since) qs.set("since", opts.since);
  if (opts?.limit != null) qs.set("limit", String(opts.limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return fetchJson<{ data: unknown[] }>(`/api/events${suffix}`);
}

export function getTrend(
  category: string,
  hours: number,
  opts?: { start?: string; end?: string }
) {
  const qs = new URLSearchParams({ category, hours: String(hours) });
  if (opts?.start && opts?.end) {
    qs.set("start", opts.start);
    qs.set("end", opts.end);
  }
  return fetchJson<{ data: unknown[] }>(`/api/trend?${qs.toString()}`);
}

export function getDailyTop() {
  return fetchJson<{ data: unknown[] }>("/api/daily-top");
}

export function getFlash() {
  return fetchJson<{ data: unknown[] }>("/api/flash");
}

export function getKing() {
  return fetchJson<{ data: unknown[] }>("/api/king");
}

export function getNewCategories() {
  return fetchJson<{ data: unknown[] }>("/api/new");
}

export function getVolatility(opts?: { start?: string; end?: string }) {
  const qs = new URLSearchParams();
  if (opts?.start) qs.set("start", opts.start);
  if (opts?.end) qs.set("end", opts.end);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return fetchJson<{ data: unknown[] }>(`/api/volatility${suffix}`);
}

export function getInsightsPeriod(start: string, end: string) {
  const qs = new URLSearchParams({ start, end });
  return fetchJson<{ data: { total_events: number; by_platform: Record<string, number>; by_event_type: Record<string, number>; start: string; end: string } }>(
    `/api/insights-period?${qs.toString()}`
  );
}
