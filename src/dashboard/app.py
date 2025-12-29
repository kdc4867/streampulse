import streamlit as st
import os
import sys

# utils와 views를 import하기 위해 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from views.realtime import render_realtime_page
from views.insights import render_insights_page

st.set_page_config(page_title="StreamPulse HQ", layout="wide", page_icon="⚡")

# 메인 네비게이션
st.sidebar.title("StreamPulse V3")
page = st.sidebar.radio("Navigate", ["Real-time Monitor", "Daily Insights"])

if page == "Real-time Monitor":
    render_realtime_page()
else:
    render_insights_page()

# 새로고침
if st.sidebar.button("Refresh Data"):
    st.rerun()