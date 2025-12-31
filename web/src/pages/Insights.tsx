import { useEffect, useState } from "react";
import { getDailyTop, getFlash, getKing, getVolatility } from "../api";
import DataTable from "../components/DataTable";
import { formatNumber, formatTime } from "../utils";
import {
  DailyTop,
  FlashCategory,
  KingStreamer,
  VolatilityMetric,
} from "../types";

const TABS = [
  { id: "top", label: "🏆 일간 랭킹" },
  { id: "king", label: "👑 스트리머 King" },
  { id: "flash", label: "⚡ 반짝 이슈" },
  { id: "volatility", label: "📉 콘크리트/변동" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function Insights() {
  const [activeTab, setActiveTab] = useState<TabId>("top");
  const [data, setData] = useState<{
    top: DailyTop[];
    king: KingStreamer[];
    flash: FlashCategory[];
    vol: VolatilityMetric[];
  }>({
    top: [],
    king: [],
    flash: [],
    vol: [],
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    Promise.all([getDailyTop(), getKing(), getFlash(), getVolatility()])
      .then(([topRes, kingRes, flashRes, volRes]) => {
        if (!mounted) return;
        setData({
          top: topRes.data as DailyTop[],
          king: kingRes.data as KingStreamer[],
          flash: flashRes.data as FlashCategory[],
          vol: volRes.data as VolatilityMetric[],
        });
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const soopTop = data.top.filter((d) => d.platform === "SOOP").slice(0, 10);
  const chzzkTop = data.top.filter((d) => d.platform === "CHZZK").slice(0, 10);

  const soopVolSorted = data.vol
    .filter((item) => item.platform === "SOOP")
    .sort((a, b) => (a.volatility_index || 0) - (b.volatility_index || 0));
  const chzzkVolSorted = data.vol
    .filter((item) => item.platform === "CHZZK")
    .sort((a, b) => (a.volatility_index || 0) - (b.volatility_index || 0));

  const soopStable = soopVolSorted.slice(0, 20);
  const chzzkStable = chzzkVolSorted.slice(0, 20);
  const soopRoller = [...soopVolSorted].reverse().slice(0, 20);
  const chzzkRoller = [...chzzkVolSorted].reverse().slice(0, 20);

  return (
    <div>
      <div className="tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`tab-btn ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="bento-grid">
        {activeTab === "top" && (
          <>
            <div className="card col-span-2">
              <div className="card-title">SOOP 일간 Top 10</div>
              <DataTable
                columns={[
                  { key: "category_name", label: "카테고리" },
                  { key: "avg_viewers", label: "평균 시청자", align: "right" },
                  { key: "peak_viewers", label: "최고 시청자", align: "right" },
                ]}
                rows={soopTop.map((row) => ({
                  ...row,
                  avg_viewers: formatNumber(row.avg_viewers),
                  peak_viewers: formatNumber(row.peak_viewers),
                }))}
                emptyText={loading ? "불러오는 중..." : "데이터 없음"}
              />
            </div>
            <div className="card col-span-2">
              <div className="card-title">CHZZK 일간 Top 10</div>
              <DataTable
                columns={[
                  { key: "category_name", label: "카테고리" },
                  { key: "avg_viewers", label: "평균 시청자", align: "right" },
                  { key: "peak_viewers", label: "최고 시청자", align: "right" },
                ]}
                rows={chzzkTop.map((row) => ({
                  ...row,
                  avg_viewers: formatNumber(row.avg_viewers),
                  peak_viewers: formatNumber(row.peak_viewers),
                }))}
                emptyText={loading ? "불러오는 중..." : "데이터 없음"}
              />
            </div>
          </>
        )}

        {activeTab === "king" && (
          <div className="card col-span-4">
            <div className="card-title">플랫폼별 최고 시청자 기록 (Peak Viewers)</div>
            <DataTable
              columns={[
                { key: "platform", label: "플랫폼" },
                { key: "streamer", label: "스트리머" },
                { key: "category", label: "카테고리" },
                { key: "viewers", label: "최고 시청자", align: "right" },
                { key: "timestamp", label: "시간" },
              ]}
              rows={data.king.slice(0, 20).map((row) => ({
                ...row,
                viewers: formatNumber(row.viewers),
                timestamp: formatTime(row.timestamp),
              }))}
              emptyText={loading ? "불러오는 중..." : "데이터 없음"}
            />
          </div>
        )}

        {activeTab === "flash" && (
          <div className="card col-span-4">
            <div className="card-title">반짝 이슈 (급상승 후 하락)</div>
            <DataTable
              columns={[
                { key: "platform", label: "플랫폼" },
                { key: "category_name", label: "카테고리" },
                { key: "peak_viewers", label: "Peak", align: "right" },
                { key: "peak_contributor", label: "최고 기여자" },
                { key: "curr_viewers", label: "현재", align: "right" },
                { key: "current_broadcaster", label: "현재 방송" },
              ]}
              rows={data.flash.map((row) => ({
                ...row,
                peak_viewers: formatNumber(row.peak_viewers),
                curr_viewers: formatNumber(row.curr_viewers),
              }))}
              emptyText={loading ? "불러오는 중..." : "데이터 없음"}
            />
          </div>
        )}

        {activeTab === "volatility" && (
          <>
            <div className="card col-span-2">
              <div className="card-title">SOOP 콘크리트 Top 20</div>
              <DataTable
                columns={[
                  { key: "category_name", label: "카테고리" },
                  { key: "avg_v", label: "평균", align: "right" },
                  { key: "volatility_index", label: "변동성", align: "right" },
                ]}
                rows={soopStable.map((row) => ({
                  ...row,
                  avg_v: formatNumber(row.avg_v),
                  volatility_index: row.volatility_index
                    ? row.volatility_index.toFixed(2)
                    : "-",
                }))}
                emptyText={loading ? "불러오는 중..." : "데이터 없음"}
              />
            </div>
            <div className="card col-span-2">
              <div className="card-title">CHZZK 콘크리트 Top 20</div>
              <DataTable
                columns={[
                  { key: "category_name", label: "카테고리" },
                  { key: "avg_v", label: "평균", align: "right" },
                  { key: "volatility_index", label: "변동성", align: "right" },
                ]}
                rows={chzzkStable.map((row) => ({
                  ...row,
                  avg_v: formatNumber(row.avg_v),
                  volatility_index: row.volatility_index
                    ? row.volatility_index.toFixed(2)
                    : "-",
                }))}
                emptyText={loading ? "불러오는 중..." : "데이터 없음"}
              />
            </div>
            <div className="card col-span-2">
              <div className="card-title">SOOP 롤러코스터 Top 20</div>
              <DataTable
                columns={[
                  { key: "category_name", label: "카테고리" },
                  { key: "avg_v", label: "평균", align: "right" },
                  { key: "volatility_index", label: "변동성", align: "right" },
                ]}
                rows={soopRoller.map((row) => ({
                  ...row,
                  avg_v: formatNumber(row.avg_v),
                  volatility_index: row.volatility_index
                    ? row.volatility_index.toFixed(2)
                    : "-",
                }))}
                emptyText={loading ? "불러오는 중..." : "데이터 없음"}
              />
            </div>
            <div className="card col-span-2">
              <div className="card-title">CHZZK 롤러코스터 Top 20</div>
              <DataTable
                columns={[
                  { key: "category_name", label: "카테고리" },
                  { key: "avg_v", label: "평균", align: "right" },
                  { key: "volatility_index", label: "변동성", align: "right" },
                ]}
                rows={chzzkRoller.map((row) => ({
                  ...row,
                  avg_v: formatNumber(row.avg_v),
                  volatility_index: row.volatility_index
                    ? row.volatility_index.toFixed(2)
                    : "-",
                }))}
                emptyText={loading ? "불러오는 중..." : "데이터 없음"}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
