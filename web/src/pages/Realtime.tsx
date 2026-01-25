import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getEvents, getLive, getTrend } from "../api";
import DataTable from "../components/DataTable";
import Section from "../components/Section";
import StatCard from "../components/StatCard";
import { EventItem, LiveTraffic } from "../types";
import { formatNumber, formatTime, formatTimeForChart, formatTimeShort } from "../utils";

type TrendOption = { label: string; hours: number };

const trendOptions: TrendOption[] = [
  { label: "12시간", hours: 12 },
  { label: "24시간", hours: 24 },
  { label: "3일", hours: 72 },
];

const getTicks = (data: Array<{ ts_utc: string }>, hours: number) => {
  if (!data || data.length === 0) return [];
  const stepHours = hours <= 24 ? 4 : 6;
  const stepPoints = stepHours * 12; // 5분 단위 기준
  return data.filter((_, i) => i % stepPoints === 0).map((d) => d.ts_utc);
};

const normalizeTimestamp = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const minutes = date.getUTCMinutes();
  const aligned = minutes - (minutes % 5);
  date.setUTCMinutes(aligned, 0, 0);
  return date.toISOString();
};

export default function Realtime() {
  const [live, setLive] = useState<LiveTraffic[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [trend, setTrend] = useState<Array<{ ts_utc: string; viewers: number }>>(
    []
  );
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
        const summed = (res.data as Array<{ ts_utc: string; viewers: number }>).reduce(
          (acc, point) => {
            if (!point.ts_utc) return acc;
            const key = normalizeTimestamp(point.ts_utc);
            const viewers = Number(point.viewers) || 0;
            acc[key] = (acc[key] || 0) + viewers;
            return acc;
          },
          {} as Record<string, number>
        );
        const aggregated = Object.entries(summed)
          .map(([ts_utc, viewers]) => ({ ts_utc, viewers }))
          .sort((a, b) => new Date(a.ts_utc).getTime() - new Date(b.ts_utc).getTime());
        setTrend(aggregated);
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

  const marketSpikes = useMemo(
    () => events.filter((event) => event.event_type !== "CATEGORY_ADOPTION"),
    [events]
  );
  const categoryAdoptions = useMemo(
    () => events.filter((event) => event.event_type === "CATEGORY_ADOPTION"),
    [events]
  );

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
          <div className="hero-badge">업데이트 {formatTime(live[0]?.ts_utc, "Asia/Seoul")}</div>
          <div className="hero-grid">
            <StatCard label="전체 시청자" value={formatNumber(totals.total)} />
            <StatCard label="SOOP 시청자" value={formatNumber(totals.SOOP)} />
            <StatCard label="CHZZK 시청자" value={formatNumber(totals.CHZZK)} />
          </div>
        </div>
      </div>

      <div className="dashboard-layout">
        <div className="dashboard-main">
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
                <div className="pie-wrap">
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie
                        data={[
                          { name: "SOOP", value: totals.SOOP || 0 },
                          { name: "CHZZK", value: totals.CHZZK || 0 },
                        ]}
                        dataKey="value"
                        nameKey="name"
                        innerRadius={55}
                        outerRadius={90}
                        paddingAngle={2}
                      >
                        <Cell fill="var(--soop)" />
                        <Cell fill="var(--chzzk)" />
                      </Pie>
                      <Tooltip
                        formatter={(value: number) => `${formatNumber(value)}명`}
                      />
                    </PieChart>
                  </ResponsiveContainer>
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
            title="카테고리 추이"
            subtitle="선택한 카테고리의 시계열 변화를 비교합니다."
          >
            <div className="card">
              <div className="trend-controls compact">
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
              <AreaChart data={trend} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorViewers" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0D9488" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#0D9488" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                <XAxis
                  dataKey="ts_utc"
                  ticks={getTicks(trend, trendHours.hours)}
                  tickFormatter={(v) => formatTimeForChart(v, trendHours.hours)}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 11, fill: "#94a3b8" }}
                  minTickGap={30}
                />
                <YAxis
                  tickFormatter={(v) => formatNumber(v)}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 11, fill: "#94a3b8" }}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: "12px",
                    border: "none",
                    boxShadow: "0 8px 16px rgba(0,0,0,0.1)",
                  }}
                  formatter={(value: number) => [formatNumber(value), "시청자"]}
                />
                <Area
                  type="monotone"
                  dataKey="viewers"
                  stroke="#0D9488"
                  strokeWidth={3}
                  fillOpacity={1}
                  fill="url(#colorViewers)"
                  animationDuration={1000}
                  connectNulls
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </Section>
        </div>

        <aside className="dashboard-aside">
          <Section
            title="급등 감지"
            subtitle="Detector가 잡아낸 최신 급등 신호입니다."
          >
            {errorEvents ? <p className="hint error">{errorEvents}</p> : null}
            {marketSpikes.length === 0 ? (
              <div className="card">
                <p className="hint">
                  {loading ? "불러오는 중..." : "감지된 이벤트 없음"}
                </p>
              </div>
            ) : (
              <div className="spike-grid">
                {marketSpikes.map((event) => {
                  const details = parseCauseDetail(event.cause_detail);
                  const clues = Array.isArray(details?.clues) ? details.clues : [];
                  const stats = details?.stats || {};
                  const market = details?.market || {};
                  const primary = clues[0];
                  const category = event.category_name?.trim() || "미분류";
                  const growth = event.growth_rate
                    ? `${Math.round(event.growth_rate * 100)}%`
                    : "-";
                  return (
                    <div key={event.event_id} className="card spike-card market-spike">
                      <div className="spike-head">
                        <span className="pill pill-spike">MARKET TREND</span>
                        <span className="spike-growth">{growth}</span>
                      </div>
                      <h3 className="spike-title">{category}</h3>
                      <div className="market-stats-grid">
                        <div className="m-stat">
                          <span className="m-label">독점 지수(DI)</span>
                          <span className="m-value">
                            {market?.dominance_index
                              ? `${(market.dominance_index * 100).toFixed(1)}%`
                              : "-"}
                          </span>
                        </div>
                        <div className="m-stat">
                          <span className="m-label">채널 증가</span>
                          <span className="m-value">
                            {typeof market?.open_lives_delta === "number"
                              ? `+${market.open_lives_delta}`
                              : "-"}
                          </span>
                        </div>
                        <div className="m-stat">
                          <span className="m-label">낙수 효과(Top 2-5)</span>
                          <span className="m-value text-up">
                            {typeof market?.top2_5_delta === "number"
                              ? `+${formatNumber(market.top2_5_delta)}`
                              : "-"}
                          </span>
                        </div>
                      </div>
                      <div className="spike-body">
                        <div>
                          <p className="stat-label">Delta</p>
                          <p className="stat-value">+{formatNumber(stats?.delta)}</p>
                        </div>
                        <div>
                          <p className="stat-label">Primary</p>
                          <p className="spike-cause">
                            {primary
                              ? `${primary.name} (${primary.title || "-"})`
                              : "구조적 이슈"}
                          </p>
                        </div>
                      </div>
                      <div className="spike-foot">
                        <span>{formatTime(event.created_at, "Asia/Seoul")}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Section>

          <Section
            title="최근 활성화 카테고리"
            subtitle="신규 진입 스트리머 중심의 콘텐츠 이동 로그"
          >
            {categoryAdoptions.length === 0 ? (
              <div className="card">
                <p className="hint">
                  {loading ? "불러오는 중..." : "특이사항 없음"}
                </p>
              </div>
            ) : (
              <div className="adoption-list card">
                {categoryAdoptions.map((event) => {
                  const details = parseCauseDetail(event.cause_detail);
                  const clues = Array.isArray(details?.clues) ? details.clues : [];
                  const primary = clues[0];
                  return (
                    <div key={event.event_id} className="adoption-item">
                      <span className="time">{formatTimeShort(event.created_at)}</span>
                      <span className="platform-tag">{event.platform}</span>
                      <span className="category">{event.category_name?.trim() || "미분류"}</span>
                      <span className="desc">
                        <strong>{primary?.name || "Unknown"}</strong> 님 진입
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </Section>
        </aside>
      </div>
    </div>
  );
}
