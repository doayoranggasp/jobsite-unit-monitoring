import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime
import uuid
from streamlit_gsheets import GSheetsConnection

# =========================================================
# CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="Jobsite Fleet Management System",
    page_icon="🚜",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main { background-color: #f8f9fa; }
    .stButton > button {
        width: 100%;
        background-color: #007bff;
        color: white;
        border-radius: 8px;
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# SESSION STATE
# =========================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""


# =========================================================
# API / CONNECTION HELPERS
# =========================================================
def get_webapp_url():
    """Ambil URL Apps Script dari Streamlit secrets."""
    try:
        url = st.secrets["app"]["webapp_url"]
        if not url or not str(url).strip():
            raise ValueError("webapp_url kosong.")
        return str(url).strip()
    except Exception as exc:
        raise RuntimeError(
            "Konfigurasi [app].webapp_url tidak ditemukan. "
            "Periksa file .streamlit/secrets.toml."
        ) from exc


def post_to_webapp(payload):
    """Kirim payload ke Apps Script dan validasi responsnya."""
    url = get_webapp_url()
    # Token server-side only; never place it in browser-visible HTML.
    try:
        token = str(st.secrets["app"]["api_token"]).strip()
    except Exception as exc:
        raise RuntimeError("Konfigurasi [app].api_token belum tersedia di Streamlit Secrets.") from exc
    if not token:
        raise RuntimeError("Konfigurasi [app].api_token kosong.")
    payload = dict(payload)
    payload["api_token"] = token
    try:
        response = requests.post(url, json=payload, timeout=45)
    except requests.Timeout as exc:
        raise RuntimeError(
            "Permintaan ke Google Apps Script timeout setelah 30 detik."
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Gagal terhubung ke Google Apps Script: {exc}") from exc

    if not response.ok:
        raise RuntimeError(
            f"Google Apps Script mengembalikan HTTP {response.status_code}. "
            f"Respons: {response.text[:500]}"
        )

    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "Respons Apps Script bukan JSON yang valid. "
            f"Respons awal: {response.text[:300]}"
        ) from exc

    if not isinstance(result, dict):
