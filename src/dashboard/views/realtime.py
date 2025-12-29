import streamlit as st
import plotly.express as px
import json
import requests
import time
from utils.db import get_live_traffic, get_events, get_trend_data

AGENT_URL = "http://agent:8000/analyze"

def render_realtime_page():
    st.title("⚡ StreamPulse Real-time Monitor")
    
    df_live = get_live_traffic()
    
    # [수정] 데이터 시간 표시 로직 (에러 수정됨)
    if not df_live.empty:
        try:
            # groupby 뒤에 .max()를 추가했습니다!
            times = df_live.groupby('platform')['ts_utc'].max().to_dict()
            
            # 보기 좋게 포맷팅 (YYYY-MM-DD HH:MM)
            time_str_list = []
            for p, t in times.items():
                ts_str = str(t)
                if len(ts_str) > 16: ts_str = ts_str[:16] # 초 단위 자르기
                time_str_list.append(f"**{p}**: {ts_str}")
            
            time_info = " | ".join(time_str_list)
            st.caption(f"🕒 Data Snapshot Time (UTC): {time_info}")
        except Exception as e:
            st.caption(f"🕒 Time Check Error: {e}")

    tab1, tab2 = st.tabs(["📊 Dashboard", "📈 Trend"])

    with tab1:
        if not df_live.empty:
            c1, c2 = st.columns([1,1])
            with c1:
                fig = px.pie(df_live, values='viewers', names='platform', hole=0.4, color='platform', color_discrete_map={'SOOP':'#19CE60', 'CHZZK':'#00FFA3'})
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                st.subheader("Real-time Top 10")
                st.dataframe(df_live[['platform', 'category_name', 'viewers']].head(10), use_container_width=True, hide_index=True)

        st.divider()
        st.header("🧠 Intelligence Reports")
        df_events = get_events()
        
        if not df_events.empty:
            for index, row in df_events.iterrows():
                details = row['cause_detail'] if isinstance(row['cause_detail'], dict) else {}
                if isinstance(details, str): details = json.loads(details)
                stats = details.get('stats', {})
                clues = details.get('clues', [])
                cause_text = f"{clues[0].get('name')} ({clues[0].get('title')})" if clues else "구조적 이슈"
                
                label = f"🚨 [{row['platform']}] {row['category_name']} - {int(row.get('growth_rate', 0)*100)}% 급등"
                
                with st.expander(label, expanded=True):
                    mc1, mc2, mc3 = st.columns([1, 2, 1])
                    with mc1: st.metric("Delta", f"+{stats.get('delta', 0):,}명")
                    with mc2: 
                        st.caption("Primary Cause")
                        st.write(f"**{cause_text}**")
                    with mc3: 
                        st.caption("Type")
                        st.write(f"`{row['event_type']}`")
                    
                    if 'ai_report' in details:
                        st.divider()
                        st.info(f"🤖 **AI Analysis:** {details['ai_report']}")
                    else:
                        st.divider()
                        if st.button(f"🤖 AI 심층 분석 요청", key=f"btn_{row.name}"):
                            with st.spinner("AI 에이전트 분석 중..."):
                                try:
                                    requests.post(AGENT_URL, json={
                                        "platform": row['platform'], "category": row['category_name'],
                                        "cause_type": row['event_type'], "stats": stats, "top_clues": clues
                                    }, timeout=30)
                                    st.success("완료!")
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as e: st.error(f"Error: {e}")
        else:
            st.info("특이사항 없음")

    with tab2:
        st.subheader("🔍 Category Trend Comparison")
        if not df_live.empty:
            period_options = {"12 Hours": 12, "24 Hours": 24, "3 Days": 72}
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                all_cats = sorted(df_live['category_name'].unique())
                sel_category = st.selectbox("카테고리 선택", all_cats)
            with col_f2:
                sel_period = st.selectbox("조회 기간", list(period_options.keys()))
                hours_val = period_options[sel_period]
            
            if sel_category:
                df_trend = get_trend_data(sel_category, hours=hours_val)
                if not df_trend.empty:
                    fig_line = px.line(df_trend, x='ts_utc', y='viewers', color='platform', markers=True, title=f"'{sel_category}' Trend", color_discrete_map={'SOOP':'#19CE60', 'CHZZK':'#00FFA3'})
                    st.plotly_chart(fig_line, use_container_width=True)
                else: st.warning("데이터 없음")