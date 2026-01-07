import streamlit as st
import pandas as pd
from utils.db import get_daily_category_top, get_king_of_streamers, get_new_categories, get_volatility_metrics, get_flash_categories
from utils.ui import dataframe_stretch

def render_insights_page():
    st.title("🏆 Daily Insights")
    st.caption("Last Update: Real-time | Timezone: UTC")
    
    st.header("1. ⚔️ Platform Top Categories")
    st.markdown("##### 💡 기준: 최근 24시간 `평균 시청자 수` (Average Viewers)")
    
    df_top = get_daily_category_top()
    if not df_top.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader(f"🌲 SOOP Top 10")
            soop_top = df_top[df_top['platform']=='SOOP'].head(10).reset_index(drop=True)
            soop_top.index += 1
            dataframe_stretch(soop_top[['category_name', 'avg_viewers', 'peak_viewers']])
        with c2:
            st.subheader(f"🟢 CHZZK Top 10")
            chzzk_top = df_top[df_top['platform']=='CHZZK'].head(10).reset_index(drop=True)
            chzzk_top.index += 1
            dataframe_stretch(chzzk_top[['category_name', 'avg_viewers', 'peak_viewers']])
    else:
        st.warning("데이터 수집 중...")

    st.divider()
    
    st.header("2. 🌠 Flash-in-the-pan (반짝 카테고리)")
    st.info("최근 30일 내 `Peak 2,000명`을 넘겼으나, `5일 이내`에 식어버린 카테고리 (Top 20)")
    
    df_flash = get_flash_categories()
    if not df_flash.empty:
        cnt_soop = len(df_flash[df_flash['platform']=='SOOP'])
        cnt_chzzk = len(df_flash[df_flash['platform']=='CHZZK'])
        
        m1, m2 = st.columns(2)
        m1.metric("SOOP 반짝 이슈", f"{cnt_soop} 건")
        m2.metric("CHZZK 반짝 이슈", f"{cnt_chzzk} 건")
        
        dataframe_stretch(
            df_flash.head(20).rename(columns={
                'peak_viewers': '최고(Past)',
                'peak_contributor': '최고점 기여 스트리머', # [신규]
                'curr_viewers': '현재(Now)',
                'current_broadcaster': '현재 방송중',     # [신규]
                'active_days': '유지(일)'
            })[['platform', 'category_name', '최고(Past)', '최고점 기여 스트리머', '현재(Now)', '현재 방송중', '유지(일)']],
            hide_index=True
        )
    else:
        st.write("조건에 맞는 카테고리가 없습니다. (데이터 누적 필요)")

    st.divider()

    st.header("3. 👑 King of Streamers (Peak Viewers)")
    st.markdown("##### 💡 플랫폼별 시청자 수 1위~10위 (발생 시점 포함)")
    
    df_king = get_king_of_streamers()
    if not df_king.empty:
        df_king['when'] = pd.to_datetime(df_king['timestamp']).dt.strftime('%m-%d %H:%M')
        
        k1, k2 = st.columns(2)
        with k1:
            st.subheader("🌲 SOOP Kings")
            soop_king = df_king[df_king['platform']=='SOOP'].head(10).reset_index(drop=True)
            soop_king.index += 1
            dataframe_stretch(soop_king[['streamer', 'category', 'viewers', 'when']])
            
        with k2:
            st.subheader("🟢 CHZZK Kings")
            chzzk_king = df_king[df_king['platform']=='CHZZK'].head(10).reset_index(drop=True)
            chzzk_king.index += 1
            dataframe_stretch(chzzk_king[['streamer', 'category', 'viewers', 'when']])
    else:
        st.write("스트리머 정보 분석 중...")
    
    st.divider()

    st.header("4. 🚀 New Categories")
    st.markdown("##### 💡 최근 7일간 기록이 없다가 `오늘 처음` 등장한 카테고리")
    
    df_new = get_new_categories()
    if not df_new.empty:
        n1, n2 = st.columns(2)
        with n1:
            st.subheader("SOOP New")
            dataframe_stretch(df_new[df_new['platform']=='SOOP'], hide_index=True)
        with n2:
            st.subheader("CHZZK New")
            dataframe_stretch(df_new[df_new['platform']=='CHZZK'], hide_index=True)
            
        if len(df_new) > 10:
            st.caption("※ 초기 데이터 수집 단계에서는 기존 카테고리도 'New'로 인식될 수 있습니다. (7일 후 안정화됨)")
    else:
        st.info("지난 24시간 내 신규 진입 카테고리가 없습니다.")

    st.divider()
    
    st.header("5. 📉 Stability vs Volatility (Top 20)")
    st.markdown("##### 💡 변동성 지수 (낮을수록 콘크리트, 높을수록 롤러코스터)")
    
    df_vol = get_volatility_metrics()
    if not df_vol.empty:
        tab_stable, tab_volatile = st.tabs(["🛡️ 콘크리트 (Stability)", "🎢 롤러코스터 (Volatility)"])
        
        with tab_stable:
            s1, s2 = st.columns(2)
            with s1:
                st.subheader("SOOP 콘크리트 Top 20")
                df_s_soop = df_vol[df_vol['platform']=='SOOP'].sort_values('volatility_index', ascending=True).head(20)
                dataframe_stretch(df_s_soop[['category_name', 'avg_v', 'volatility_index']], hide_index=True)
            with s2:
                st.subheader("CHZZK 콘크리트 Top 20")
                df_s_chzzk = df_vol[df_vol['platform']=='CHZZK'].sort_values('volatility_index', ascending=True).head(20)
                dataframe_stretch(df_s_chzzk[['category_name', 'avg_v', 'volatility_index']], hide_index=True)

        with tab_volatile:
            v1, v2 = st.columns(2)
            with v1:
                st.subheader("SOOP 롤러코스터 Top 20")
                df_v_soop = df_vol[df_vol['platform']=='SOOP'].sort_values('volatility_index', ascending=False).head(20)
                dataframe_stretch(df_v_soop[['category_name', 'avg_v', 'volatility_index']], hide_index=True)
            with v2:
                st.subheader("CHZZK 롤러코스터 Top 20")
                df_v_chzzk = df_vol[df_vol['platform']=='CHZZK'].sort_values('volatility_index', ascending=False).head(20)
                dataframe_stretch(df_v_chzzk[['category_name', 'avg_v', 'volatility_index']], hide_index=True)
