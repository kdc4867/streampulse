import { useEffect, useMemo, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getEvents, getLive, getTrend } from "../api";
import DataTable from "../components/DataTable";
import { EventItem, LiveTraffic, TrendPoint } from "../types";
import { formatNumber, formatTimeShort } from "../utils";

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
  const [trendHours] = useState(trendOptions[0]);

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
      })
      .catch(() => {
        if (!mounted) return;
        setLive([]);
        setEvents([]);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!live[0]?.category_name) return;
    let mounted = true;
    getTrend(live[0].category_name, trendHours.hours)
      .then((res) => {
        if (!mounted) return;
        setTrend(res.data as TrendPoint[]);
      })
      .catch(() => {
        if (!mounted) return;
        setTrend([]);
      });
    return () => {
      mounted = false;
    };
  }, [live, trendHours]);

  const totals = useMemo(() => {
    return live.reduce(
      (acc, item) => {
        acc.total += item.viewers;
        acc[item.platform.trim()] = (acc[item.platform.trim()] || 0) + item.viewers;
        return acc;
      },
      { total: 0, SOOP: 0, CHZZK: 0 } as Record<string, number>
    );
  }, [live]);

  return (
    <div className="bento-grid">
      <div className="card col-span-1">
        <div className="card-title">총 시청자</div>
        <div className="stat-value">{formatNumber(totals.total)}명</div>
        <div className="stat-sub">현재 전체 트래픽</div>
      </div>
      <div className="card col-span-1">
        <div className="card-title">SOOP 점유율</div>
        <div className="stat-value text-soop">
          {totals.total ? ((totals.SOOP / totals.total) * 100).toFixed(1) : "0.0"}%
        </div>
        <div className="stat-sub">{formatNumber(totals.SOOP)}명</div>
      </div>
      <div className="card col-span-1">
        <div className="card-title">CHZZK 점유율</div>
        <div className="stat-value text-chzzk">
          {totals.total ? ((totals.CHZZK / totals.total) * 100).toFixed(1) : "0.0"}%
        </div>
        <div className="stat-sub">{formatNumber(totals.CHZZK)}명</div>
      </div>

      <div className="card col-span-1 row-span-2">
        <div className="card-title">🚨 실시간 급등 감지</div>
        <div className="spike-list">
          {events.length === 0 ? (
            <p className="empty-text">감지된 특이사항 없음</p>
          ) : (
            events.map((ev) => (
              <div key={ev.event_id} className="spike-item">
                <div className="spike-header">
                  <span>{ev.platform}</span>
                  <span>+{Math.round(ev.growth_rate * 100)}%</span>
                </div>
                <div className="spike-msg">{ev.category_name || "미분류"}</div>
                <div className="spike-time">{formatTimeShort(ev.created_at)} 감지</div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="card col-span-2 row-span-2">
        <div className="card-title">
          📊 카테고리 트렌드 (1위: {live[0]?.category_name || "-"})
        </div>
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trend}>
              <XAxis dataKey="ts_utc" tickFormatter={formatTimeShort} />
              <YAxis tickFormatter={formatNumber} width={40} />
              <Tooltip
                formatter={(val: number) => formatNumber(val)}
                labelFormatter={formatTimeShort}
              />
              <Line
                type="monotone"
                dataKey="viewers"
                stroke="var(--primary)"
                strokeWidth={3}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card col-span-1 row-span-2">
        <div className="card-title">🔥 실시간 Top 10</div>
        <DataTable
          columns={[
            { key: "platform", label: "PLT" },
            { key: "category_name", label: "카테고리" },
            { key: "viewers", label: "시청자", align: "right" },
          ]}
          rows={live.slice(0, 10).map((row) => ({ ...row, viewers: formatNumber(row.viewers) }))}
          emptyText={loading ? "불러오는 중..." : "데이터 없음"}
        />
      </div>
    </div>
  );
}
