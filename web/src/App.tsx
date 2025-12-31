import { useState } from "react";
import Realtime from "./pages/Realtime";
import Insights from "./pages/Insights";

const MENUS = [
  { id: "realtime", label: "Dashboard", icon: "⚡" },
  { id: "insights", label: "Deep Insights", icon: "🧠" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("realtime");

  return (
    <div className="app-layout">
      {/* Sidebar Navigation */}
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

      {/* Main Content Area */}
      <main className="main-content">
        <header className="top-bar">
          <h2 className="page-title">
            {activeTab === "realtime" ? "실시간 모니터링 센터" : "심층 분석 리포트"}
          </h2>
          <div className="last-update">시스템 상태: 🟢 정상 가동 중</div>
        </header>
        
        <div className="content-scroll">
          <div className={activeTab === "realtime" ? "view active" : "view"}>
            <Realtime />
          </div>
          <div className={activeTab === "insights" ? "view active" : "view"}>
            <Insights />
          </div>
        </div>
      </main>
    </div>
  );
}
