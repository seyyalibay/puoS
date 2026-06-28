import streamlit as st

st.set_page_config(layout="wide")

st.markdown("""
<style>
[data-testid="stSidebar"] {
    background-color: #111111 !important;
}
h1 {
    color: #5E6AD2 !important;
}
</style>
""", unsafe_allow_html=True)

st.title("CSS Test Başlığı")
st.write("Sidebar #111111 (koyu siyah), başlık #5E6AD2 (mor) olmalı.")
