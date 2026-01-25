import { useEffect, useState } from "react";
import Realtime from "./pages/Realtime";
import Insights from "./pages/Insights";
import Trends from "./pages/Trends";

const MENUS = [
  { id: "realtime", label: "Dashboard", icon: "⚡" },
  { id: "insights", label: "Deep Insights", icon: "🧠" },
  { id: "trends", label: "카테고리 트렌드", icon: "📈" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("realtime");
  const [status, setStatus] = useState<{
    apiMs: number | null;
    dbOk: boolean | null;
    checkedAt: Date | null;
  }>({ apiMs: null, dbOk: null, checkedAt: null });

  useEffect(() => {
    let mounted = true;
    const checkStatus = async () => {
      const start = performance.now();
      let apiMs: number | null = null;
      let dbOk: boolean | null = null;
      try {
        const health = await fetch("/health");
        apiMs = Math.round(performance.now() - start);
        const liveRes = await fetch("/api/live");
        dbOk = liveRes.ok;
        if (liveRes.ok) {
          await liveRes.json();
        }
      } catch {
        apiMs = null;
        dbOk = false;
      }
      if (!mounted) return;
      setStatus({ apiMs, dbOk, checkedAt: new Date() });
    };

    checkStatus();
    const interval = window.setInterval(checkStatus, 30000);
    return () => {
      mounted = false;
      window.clearInterval(interval);
    };
  }, []);

  return (
    <div className="app-layout">
      <nav className="sidebar">
        <div className="brand">
          <span>SP</span> StreamPulse
        </div>
        {MENUS.map((menu) => (
          <div
            key={menu.id}
            className={`nav-item ${activeTab === menu.id ? "active" : ""}`}
            onClick={() => setActiveTab(menu.id)}
          >
            <span>{menu.icon}</span>
            {menu.label}
          </div>
        ))}
      </nav>

      <main className="main-content">
        <header className="top-bar">
          <h2 className="page-title">
            {activeTab === "realtime"
              ? "실시간 모니터링 센터"
              : activeTab === "insights"
                ? "심층 분석 리포트"
                : "카테고리 트렌드"}
          </h2>
          <div className="status-indicator">
            <span className={`status-dot ${status.dbOk === false ? "down" : ""}`} />
            <span>시스템 상태: {status.dbOk === false ? "이상 감지" : "정상 가동 중"}</span>
            <div className="status-tooltip">
              <div className="status-row">
                <span>API 레이턴시</span>
                <span>{status.apiMs !== null ? `${status.apiMs}ms` : "-"}</span>
              </div>
              <div className="status-row">
                <span>DB 연결</span>
                <span>
                  {status.dbOk === null ? "-" : status.dbOk ? "정상" : "이상"}
                </span>
              </div>
              <div className="status-row">
                <span>마지막 체크</span>
                <span>
                  {status.checkedAt
                    ? status.checkedAt.toLocaleTimeString("ko-KR", {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                        hour12: false,
                      })
                    : "-"}
                </span>
              </div>
            </div>
          </div>
        </header>
        
        <div className="content-scroll">
          <div className={activeTab === "realtime" ? "view active" : "view"}>
            <Realtime />
          </div>
          <div className={activeTab === "insights" ? "view active" : "view"}>
            <Insights />
          </div>
          <div className={activeTab === "trends" ? "view active" : "view"}>
            <Trends />
          </div>
        </div>
      </main>
    </div>
  );
}
