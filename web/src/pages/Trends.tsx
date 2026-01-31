import { useEffect, useMemo, useState } from "react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from "recharts";
import { getLive, getTrend } from "../api";
import { LiveTraffic, TrendPoint } from "../types";
import { formatNumber, formatTime, formatTimeShort } from "../utils";

const PRESETS = [
  { label: "1D", hours: 24 },
  { label: "7D", hours: 168 },
  { label: "30D", hours: 720 },
] as const;

const LINE_COLORS = ["var(--primary)", "#ff7a59", "#2bb0a3"];

type TrendItem = {
  category: string;
  points: TrendPoint[];
};

export default function Trends() {
  const [live, setLive] = useState<LiveTraffic[]>([]);
  const [selected, setSelected] = useState<string[]>(["", "", ""]);
  const [trends, setTrends] = useState<TrendItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [preset, setPreset] = useState(PRESETS[0]);
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");

  useEffect(() => {
    let mounted = true;
    getLive()
      .then((res) => {
        if (!mounted) return;
        const liveData = (res.data as LiveTraffic[]).map((item) => ({
          ...item,
          platform: (item.platform || "").trim(),
          viewers: Number(item.viewers) || 0,
        }));
        setLive(liveData);
        const unique = Array.from(new Set(liveData.map((item) => item.category_name)));
        if (unique.length > 0) {
          setSelected((prev) =>
            prev.every((s) => !s)
              ? [unique[0] || "", unique[1] || "", unique[2] || ""]
              : prev
          );
        }
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const hours = useMemo(() => {
    if (rangeStart && rangeEnd) {
      const start = new Date(rangeStart);
      const end = new Date(rangeEnd);
      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) {
        return preset.hours;
      }
      const diff = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60));
      return Math.min(Math.max(diff, 1), 720);
    }
    return preset.hours;
  }, [rangeStart, rangeEnd, preset]);

  useEffect(() => {
    const targets = Array.from(new Set(selected.filter(Boolean))).slice(0, 3);
    if (targets.length === 0) {
      setTrends([]);
      return;
    }
    let mounted = true;
    const trendOpts =
      rangeStart && rangeEnd ? { start: rangeStart, end: rangeEnd } : undefined;
    Promise.all(
      targets.map((cat) =>
        trendOpts ? getTrend(cat, hours, trendOpts) : getTrend(cat, hours)
      )
    )
      .then((results) => {
        if (!mounted) return;
        const merged = targets.map((cat, idx) => ({
          category: cat,
          points: (results[idx].data as TrendPoint[]) || [],
        }));
        setTrends(merged);
      })
      .catch(() => {
        if (!mounted) return;
        setTrends([]);
      });
    return () => {
      mounted = false;
    };
  }, [selected, hours, rangeStart, rangeEnd]);

  const categories = useMemo(() => {
    return Array.from(new Set(live.map((item) => item.category_name))).sort();
  }, [live]);

  const buildSeries = (platform: string) => {
    const map = new Map<string, Record<string, unknown>>();
    trends.forEach((item) => {
      item.points
        .filter((point) => (point.platform || "").trim() === platform)
        .forEach((point) => {
          const key = point.ts_utc;
          const row = map.get(key) || { ts_utc: key };
          row[item.category] = Number(point.viewers) || 0;
          map.set(key, row);
        });
    });
    return Array.from(map.values()).sort((a, b) =>
      String(a.ts_utc).localeCompare(String(b.ts_utc))
    );
  };

  const soopData = buildSeries("SOOP");
  const chzzkData = buildSeries("CHZZK");

  const handleSelect = (index: number, value: string) => {
    const next = [...selected];
    next[index] = value;
    setSelected(next);
  };

  return (
    <div className="page">
      <div className="trend-controls">
        <div className="trend-row">
          <label>카테고리 1</label>
          <select
            value={selected[0]}
            onChange={(event) => handleSelect(0, event.target.value)}
          >
            <option value="">선택 안 함</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>
        <div className="trend-row">
          <label>카테고리 2</label>
          <select
            value={selected[1]}
            onChange={(event) => handleSelect(1, event.target.value)}
          >
            <option value="">선택 안 함</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>
        <div className="trend-row">
          <label>카테고리 3</label>
          <select
            value={selected[2]}
            onChange={(event) => handleSelect(2, event.target.value)}
          >
            <option value="">선택 안 함</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>
        <div className="trend-row">
          <label>기간 선택</label>
          <div className="chip-group">
            {PRESETS.map((opt) => (
              <button
                key={opt.hours}
                type="button"
                className={`chip ${preset.hours === opt.hours ? "active" : ""}`}
                onClick={() => {
                  setPreset(opt);
                  setRangeStart("");
                  setRangeEnd("");
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
        <div className="trend-row">
          <label>직접 입력</label>
          <div className="date-group">
            <input
              type="date"
              value={rangeStart}
              onChange={(event) => setRangeStart(event.target.value)}
            />
            <span>~</span>
            <input
              type="date"
              value={rangeEnd}
              onChange={(event) => setRangeEnd(event.target.value)}
            />
          </div>
        </div>
        <div className="trend-hint">
          기준 시간대: KST(Asia/Seoul) | 현재 설정: {hours}시간
        </div>
      </div>

      <div className="bento-grid">
        <div className="card col-span-2 row-span-2">
          <div className="card-title">SOOP 트렌드</div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={soopData}>
                <XAxis dataKey="ts_utc" tickFormatter={formatTimeShort} />
                <YAxis tickFormatter={formatNumber} width={40} />
                <Tooltip
                  formatter={(val: number) => formatNumber(val)}
                  labelFormatter={formatTime}
                />
                <Legend />
                {trends.map((item, idx) => (
                  <Line
                    key={`soop-${item.category}`}
                    type="monotone"
                    dataKey={item.category}
                    stroke={LINE_COLORS[idx % LINE_COLORS.length]}
                    strokeWidth={2.5}
                    dot={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card col-span-2 row-span-2">
          <div className="card-title">CHZZK 트렌드</div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chzzkData}>
                <XAxis dataKey="ts_utc" tickFormatter={formatTimeShort} />
                <YAxis tickFormatter={formatNumber} width={40} />
                <Tooltip
                  formatter={(val: number) => formatNumber(val)}
                  labelFormatter={formatTime}
                />
                <Legend />
                {trends.map((item, idx) => (
                  <Line
                    key={`chzzk-${item.category}`}
                    type="monotone"
                    dataKey={item.category}
                    stroke={LINE_COLORS[idx % LINE_COLORS.length]}
                    strokeWidth={2.5}
                    dot={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {loading && <p className="empty-text">불러오는 중...</p>}
    </div>
  );
}
