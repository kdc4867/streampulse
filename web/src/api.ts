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

export function getEvents() {
  return fetchJson<{ data: unknown[] }>("/api/events");
}

export function getTrend(category: string, hours: number) {
  const qs = new URLSearchParams({ category, hours: String(hours) });
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

export function getVolatility() {
  return fetchJson<{ data: unknown[] }>("/api/volatility");
}
