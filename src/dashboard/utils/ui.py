import inspect
import streamlit as st

_PLOTLY_KW = {"width": "stretch"} if "width" in inspect.signature(st.plotly_chart).parameters else {"use_container_width": True}
_DATAFRAME_KW = {"width": "stretch"} if "width" in inspect.signature(st.dataframe).parameters else {"use_container_width": True}

def plotly_chart_stretch(fig, **kwargs):
    st.plotly_chart(fig, **_PLOTLY_KW, **kwargs)

def dataframe_stretch(df, **kwargs):
    st.dataframe(df, **_DATAFRAME_KW, **kwargs)
