import { useEffect, useMemo, useState } from "react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getEvents, getLive, getTrend } from "../api";
import DataTable from "../components/DataTable";
import Section from "../components/Section";
import StatCard from "../components/StatCard";
import { EventItem, LiveTraffic, TrendPoint } from "../types";
import { formatNumber, formatTime, formatTimeShort } from "../utils";

type TrendOption = { label: string; hours: number };

const trendOptions: TrendOption[] = [
  { label: "12시간", hours: 12 },
  { label: "24시간", hours: 24 },
  { label: "3일", hours: 72 },
];

export default function Realtime() {
  const [live, setLive] = useState<LiveTraffic[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorLive, setErrorLive] = useState("");
  const [errorEvents, setErrorEvents] = useState("");
  const [errorTrend, setErrorTrend] = useState("");
  const [trendHours, setTrendHours] = useState(trendOptions[0]);
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [categoryQuery, setCategoryQuery] = useState("");

  useEffect(() => {
    let mounted = true;
    Promise.all([getLive(), getEvents()])
      .then(([liveRes, eventRes]) => {
        if (!mounted) return;
        const liveData = (liveRes.data as LiveTraffic[]).map((item) => ({
          ...item,
          platform: (item.platform || "").trim(),
          viewers: Number(item.viewers) || 0,
        }));
        setLive(liveData);
        setEvents(eventRes.data as EventItem[]);
        setErrorLive("");
        setErrorEvents("");
        if (liveData.length > 0) {
          setSelectedCategory(liveData[0].category_name);
        }
      })
      .catch(() => {
        if (!mounted) return;
        setLive([]);
        setEvents([]);
        setErrorLive("실시간 데이터를 불러오지 못했습니다.");
        setErrorEvents("이벤트 데이터를 불러오지 못했습니다.");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedCategory) return;
    let mounted = true;
    getTrend(selectedCategory, trendHours.hours)
      .then((res) => {
        if (!mounted) return;
        setTrend(res.data as TrendPoint[]);
        setErrorTrend("");
      })
      .catch(() => {
        if (!mounted) return;
        setTrend([]);
        setErrorTrend("추이 데이터를 불러오지 못했습니다.");
      });
    return () => {
      mounted = false;
    };
  }, [selectedCategory, trendHours]);

  const totals = useMemo(() => {
    const stats = live.reduce(
      (acc, item) => {
        const viewers = Number(item.viewers) || 0;
        const platform = (item.platform || "").trim();
        acc.total += viewers;
        if (platform) {
          acc[platform] = (acc[platform] || 0) + viewers;
        }
        return acc;
      },
      { total: 0, SOOP: 0, CHZZK: 0 } as Record<string, number>
    );
    return stats;
  }, [live]);

  const categories = useMemo(() => {
    return Array.from(new Set(live.map((item) => item.category_name))).slice(0, 200);
  }, [live]);

  const filteredCategories = useMemo(() => {
    if (!categoryQuery.trim()) return categories;
    const query = categoryQuery.trim().toLowerCase();
    return categories.filter((cat) => cat.toLowerCase().includes(query));
  }, [categories, categoryQuery]);

  const typeLabel = (value?: string) => {
    if (value === "PERSON_ISSUE") return "인물 이슈";
    if (value === "STRUCTURE_ISSUE") return "구조 이슈";
    return value || "-";
  };

  const parseCauseDetail = (value: EventItem["cause_detail"]) => {
    if (!value) return {};
    if (typeof value === "string") {
      try {
        return JSON.parse(value);
      } catch {
        return {};
      }
    }
    return value;
  };

  return (
    <div className="page">
      <div className="hero">
        <div>
          <p className="eyebrow">라이브 신호</p>
          <h1>StreamPulse 실시간 모니터</h1>
          <p className="hero-sub">
            SOOP과 CHZZK의 최신 스냅샷을 기반으로 변화를 빠르게 포착합니다.
          </p>
        </div>
        <div className="hero-panel">
          <div className="hero-badge">업데이트 {formatTime(live[0]?.ts_utc)}</div>
          <div className="hero-grid">
            <StatCard label="전체 시청자" value={formatNumber(totals.total)} />
            <StatCard label="SOOP 시청자" value={formatNumber(totals.SOOP)} />
            <StatCard label="CHZZK 시청자" value={formatNumber(totals.CHZZK)} />
          </div>
        </div>
      </div>

      <Section
        title="실시간 스냅샷"
        subtitle="5분 주기로 최신 상위 카테고리를 갱신합니다."
      >
        <div className="grid-2">
          <div className="card">
            <div className="card-head">
              <h3>플랫폼 비중</h3>
              <span className="pill">LIVE</span>
            </div>
            {errorLive ? <p className="hint error">{errorLive}</p> : null}
            <div className="stack">
              {["SOOP", "CHZZK"].map((platform) => {
                const value = totals[platform] || 0;
                const pct = totals.total ? (value / totals.total) * 100 : 0;
                return (
                  <div key={platform} className="bar-row">
                    <div className="bar-label">
                      <span>{platform}</span>
                      <span>{formatNumber(value)}명</span>
                    </div>
                    <div className="bar-track">
                      <div className="bar-fill" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <h3>카테고리 Top 10</h3>
              <span className="pill">LIVE</span>
            </div>
            <DataTable
              columns={[
                { key: "platform", label: "플랫폼" },
                { key: "category_name", label: "카테고리" },
                { key: "viewers", label: "시청자", align: "right" },
              ]}
              rows={live.slice(0, 10).map((row) => ({
                ...row,
                viewers: formatNumber(row.viewers),
              }))}
              emptyText={
                errorLive
                  ? "데이터를 불러오지 못했습니다."
                  : loading
                  ? "불러오는 중..."
                  : "데이터 없음"
              }
            />
          </div>
        </div>
      </Section>

      <Section
        title="급등 감지"
        subtitle="Detector가 잡아낸 최신 급등 신호입니다."
      >
        {errorEvents ? <p className="hint error">{errorEvents}</p> : null}
        {events.length === 0 ? (
          <div className="card">
            <p className="hint">
              {loading ? "불러오는 중..." : "감지된 이벤트 없음"}
            </p>
          </div>
        ) : (
          <div className="spike-grid">
            {events.map((event) => {
              const details = parseCauseDetail(event.cause_detail);
              const clues = Array.isArray(details?.clues) ? details.clues : [];
              const stats = details?.stats || {};
              const primary = clues[0];
              const category = event.category_name?.trim() || "미분류";
              const growth = event.growth_rate
                ? `${Math.round(event.growth_rate * 100)}%`
                : "-";
              return (
                <div key={event.event_id} className="card spike-card">
                  <div className="spike-head">
                    <span className="pill">🚨 {event.platform}</span>
                    <span className="spike-growth">{growth} 급등</span>
                  </div>
                  <h3 className="spike-title">{category}</h3>
                  <div className="spike-body">
                    <div>
                      <p className="stat-label">Delta</p>
                      <p className="stat-value">+{formatNumber(stats?.delta)}</p>
                    </div>
                    <div>
                      <p className="stat-label">Primary Cause</p>
                      <p className="spike-cause">
                        {primary
                          ? `${primary.name} (${primary.title || "-"})`
                          : "구조적 이슈"}
                      </p>
                    </div>
                    <div>
                      <p className="stat-label">Type</p>
                      <p className="spike-type">{typeLabel(event.event_type)}</p>
                    </div>
                  </div>
                  <div className="spike-foot">
                    <span>{formatTime(event.created_at)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Section>

      <Section
        title="카테고리 추이"
        subtitle="선택한 카테고리의 시계열 변화를 비교합니다."
      >
        <div className="card">
          <div className="trend-controls">
            <input
              className="search"
              placeholder="카테고리 검색"
              value={categoryQuery}
              onChange={(event) => setCategoryQuery(event.target.value)}
            />
            <select
              value={selectedCategory}
              onChange={(event) => setSelectedCategory(event.target.value)}
            >
              {filteredCategories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
            <div className="segment">
              {trendOptions.map((opt) => (
                <button
                  key={opt.hours}
                  type="button"
                  className={opt.hours === trendHours.hours ? "active" : ""}
                  onClick={() => setTrendHours(opt)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          {errorTrend ? <p className="hint error">{errorTrend}</p> : null}
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={trend}>
                <XAxis
                  dataKey="ts_utc"
                  tickFormatter={(v) => formatTimeShort(v)}
                  minTickGap={24}
                />
                <YAxis tickFormatter={(v) => formatNumber(v)} />
                <Tooltip
                  formatter={(value: number) => formatNumber(value)}
                  labelFormatter={(label: string) => formatTime(label)}
                />
                <Line type="monotone" dataKey="viewers" stroke="#E6FF6A" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </Section>
    </div>
  );
}
