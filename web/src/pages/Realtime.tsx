import { useEffect, useMemo, useState } from "react";
import { getEvents, getLive } from "../api";
import DataTable from "../components/DataTable";
import { EventItem, LiveTraffic } from "../types";
import { formatNumber, formatTimeShort } from "../utils";

export default function Realtime() {
  const [live, setLive] = useState<LiveTraffic[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [loading, setLoading] = useState(true);

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
        <div className="card-sub">기준: 전날 동일 시간 ±2시간 평균</div>
        <div className="spike-list">
          {events.length === 0 ? (
            <p className="empty-text">감지된 특이사항 없음</p>
          ) : (
            events.map((ev) => {
              let details: Record<string, unknown> = {};
              if (typeof ev.cause_detail === "string") {
                try {
                  details = JSON.parse(ev.cause_detail || "{}");
                } catch {
                  details = {};
                }
              } else if (ev.cause_detail) {
                details = ev.cause_detail as Record<string, unknown>;
              }
              const stats = details?.stats || {};
              const baseline =
                typeof stats.baseline_season === "number" ? stats.baseline_season : null;
              const current = typeof stats.current === "number" ? stats.current : null;
              const growth = baseline && current
                ? Math.round((current / baseline) * 100)
                : Math.round((ev.growth_rate || 0) * 100);

              return (
                <div key={ev.event_id} className="spike-item">
                  <div className="spike-header">
                    <span>{ev.platform}</span>
                    <span>+{growth}%</span>
                  </div>
                  <div className="spike-msg">{ev.category_name || "미분류"}</div>
                  {baseline ? (
                    <div className="spike-baseline">기준 {formatNumber(baseline)}명</div>
                  ) : null}
                  <div className="spike-time">{formatTimeShort(ev.created_at)} 감지</div>
                </div>
              );
            })
          )}
        </div>
      </div>

      <div className="card col-span-3 row-span-2">
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
