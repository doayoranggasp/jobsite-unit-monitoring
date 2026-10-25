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
    :root { --jf-bg:#07111f; --jf-panel:rgba(14,29,49,.86); --jf-line:rgba(80,190,255,.24); --jf-cyan:#43d9ff; --jf-blue:#397bff; }
    .stApp { background: radial-gradient(ellipse at 10% 0%, #102d4b 0%, #081525 38%, #050b14 100%); color:#e8f4ff; }
    [data-testid="stHeader"] { background:rgba(4,12,22,.78); }
    [data-testid="stSidebar"] { background:linear-gradient(180deg,#071526 0%,#0a1d31 100%); border-right:1px solid var(--jf-line); }
    [data-testid="stSidebar"] * { color:#e8f4ff; }
    h1,h2,h3 { color:#f3faff !important; letter-spacing:.2px; }
    [data-testid="stMetric"] { background:linear-gradient(145deg,rgba(18,43,68,.95),rgba(8,20,36,.92)); border:1px solid var(--jf-line); padding:16px; border-radius:16px; box-shadow:0 8px 28px rgba(0,0,0,.18); }
    [data-testid="stMetricValue"] { color:var(--jf-cyan); }
    .stButton > button, .stFormSubmitButton > button { width:100%; background:linear-gradient(100deg,#0878c9,#315bff); color:white; border:1px solid rgba(100,220,255,.4); border-radius:10px; font-weight:700; transition:all .2s ease; }
    .stButton > button:hover, .stFormSubmitButton > button:hover { border-color:#70e5ff; box-shadow:0 0 18px rgba(67,217,255,.24); transform:translateY(-1px); }
    [data-testid="stDataFrame"], [data-testid="stTable"] { border:1px solid var(--jf-line); border-radius:12px; overflow:hidden; }
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div, textarea { background:rgba(6,18,32,.88) !important; }
    .jf-hero { padding:22px 26px; margin:4px 0 22px; border:1px solid rgba(67,217,255,.32); border-radius:18px; background:linear-gradient(115deg,rgba(14,54,83,.92),rgba(13,25,52,.84)); box-shadow:0 12px 34px rgba(0,0,0,.22); }
    .jf-kicker { color:#69e4ff; font-size:12px; font-weight:800; letter-spacing:2px; text-transform:uppercase; }
    .jf-title { font-size:clamp(24px,3vw,38px); font-weight:850; margin:5px 0; color:#f4fbff; }
    .jf-subtitle { color:#a9c7df; font-size:14px; }

    /* Premium navigation / enterprise sidebar */
    [data-testid="stSidebar"] > div:first-child { padding-top: 1.25rem; }
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .65rem; }
    [data-testid="stSidebar"] .stRadio > label { color:#7ddfff !important; font-size:11px !important; font-weight:800 !important; letter-spacing:1.7px !important; text-transform:uppercase; margin: 12px 0 8px; }
    [data-testid="stSidebar"] div[role="radiogroup"] { gap:7px; }
    [data-testid="stSidebar"] div[role="radiogroup"] > label {
        display:flex; align-items:center; min-height:42px; padding:10px 12px !important;
        border:1px solid rgba(110,180,220,.12); border-radius:12px;
        background:linear-gradient(110deg,rgba(13,34,56,.72),rgba(8,22,39,.52));
        transition:all .18s ease; margin:0 !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        border-color:rgba(67,217,255,.55); background:rgba(20,59,87,.8); transform:translateX(2px);
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
        border-color:rgba(67,217,255,.75); background:linear-gradient(100deg,rgba(10,120,201,.34),rgba(49,91,255,.19));
        box-shadow:inset 3px 0 0 #43d9ff, 0 5px 18px rgba(0,0,0,.12);
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label p { font-size:13px; font-weight:650; color:#dceeff; }
    [data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child { display:none; }
    .jf-brand-card { padding:18px 15px; margin:4px 0 14px; border:1px solid rgba(67,217,255,.28); border-radius:16px; background:linear-gradient(145deg,rgba(17,57,86,.92),rgba(7,19,35,.96)); box-shadow:0 10px 28px rgba(0,0,0,.2); }
    .jf-brand-mark { display:inline-flex; align-items:center; justify-content:center; width:34px; height:34px; border-radius:10px; background:linear-gradient(135deg,#43d9ff,#397bff); color:#031323; font-weight:950; margin-bottom:10px; box-shadow:0 0 20px rgba(67,217,255,.2); }
    .jf-brand-name { font-size:19px; line-height:1.08; font-weight:900; letter-spacing:.4px; color:#f4fbff; }
    .jf-brand-caption { color:#8bb6d5; font-size:10px; letter-spacing:1.5px; margin-top:8px; text-transform:uppercase; }
    .jf-user-chip { border:1px solid rgba(67,217,255,.2); background:rgba(8,24,42,.7); padding:10px 12px; border-radius:12px; color:#b9d8ee; font-size:12px; }
    .jf-section-label { color:#69e4ff; font-size:10px; letter-spacing:1.8px; font-weight:850; text-transform:uppercase; margin:12px 0 6px; }
    .jf-hero { position:relative; overflow:hidden; }
    .jf-hero:after { content:""; position:absolute; width:210px; height:210px; right:-75px; top:-95px; border:1px solid rgba(67,217,255,.22); border-radius:50%; box-shadow:0 0 0 22px rgba(67,217,255,.035),0 0 0 48px rgba(67,217,255,.025); pointer-events:none; }
    @media (max-width: 768px) { .jf-brand-name { font-size:17px; } .jf-hero { padding:18px; } }
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
if "company_logo_bytes" not in st.session_state:
    st.session_state.company_logo_bytes = None
if "background_bytes" not in st.session_state:
    st.session_state.background_bytes = None

# Uploaded branding is held in the active Streamlit session (not persisted to Google Sheets).
import base64
_logo = st.session_state.company_logo_bytes
_bg = st.session_state.background_bytes
if _bg:
    _bg64 = base64.b64encode(_bg).decode("ascii")
    st.markdown(f"<style>.stApp {{ background-image:linear-gradient(rgba(4,12,24,.84),rgba(4,12,24,.91)),url('data:image/jpeg;base64,{_bg64}'); background-size:cover; background-position:center; background-attachment:fixed; }}</style>", unsafe_allow_html=True)


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
        raise RuntimeError("Format respons Apps Script tidak sesuai; seharusnya objek JSON.")

    return result


def api_success(result):
    """Mendukung format respons backend result=success."""
    return str(result.get("result", "")).strip().lower() == "success"


@st.cache_data(ttl=60, show_spinner="Memuat Master Jobsite...")
def load_jobsite_names():
    """Ambil daftar lokasi resmi dari tab Master_Jobsite melalui Apps Script."""
    result = post_to_webapp({"action": "get_jobsite_master"})
    if not api_success(result):
        raise RuntimeError(result.get("message", "Master Jobsite gagal dimuat."))
    names = result.get("jobsites", [])
    return sorted({str(x).strip() for x in names if str(x).strip()}, key=str.casefold)


def get_gsheets_connection():
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception as exc:
        st.error(
            "Koneksi Google Sheets gagal. Periksa konfigurasi koneksi "
            f"Streamlit dan akses spreadsheet. Detail: {exc}"
        )
        return None


def get_worksheet_id(key):
    """Public-sheet mode requires the numeric gid for each tab."""
    try:
        value = str(st.secrets["app"][key]).strip()
        if not value.isdigit():
            raise ValueError("GID harus berupa angka.")
        return value
    except Exception as exc:
        raise RuntimeError(
            f"GID worksheet belum benar. Tambahkan [app].{key} di Streamlit Secrets "
            "menggunakan angka gid tab Google Sheets."
        ) from exc


def clean_text_series(series):
    """Konversi kolom menjadi teks tanpa nilai NaN/None."""
    return (
        series.fillna("")
        .astype(str)
        .replace({"nan": "", "None": "", "NaT": ""})
        .str.strip()
    )


# =========================================================
# LOGIN / REGISTER
# =========================================================
if not st.session_state.logged_in:
    st.title("Login & Register - Jobsite Fleet System")
    st.markdown("Silakan masuk menggunakan akun terdaftar atau buat akun baru.")

    tab_login, tab_reg = st.tabs(["Login", "Register Akun Baru"])

    with tab_login:
        with st.form("form_login"):
            l_user = st.text_input("Username").strip()
            l_pass = st.text_input("Password", type="password")
            btn_login = st.form_submit_button("Masuk ke Sistem")

        if btn_login:
            if not l_user or not l_pass:
                st.warning("Username dan Password wajib diisi.")
            else:
                try:
                    result = post_to_webapp({
                        "action": "login",
                        "username": l_user,
                        "password": l_pass,
                    })
                    if api_success(result):
                        st.session_state.logged_in = True
                        st.session_state.username = l_user
                        st.success("Login berhasil.")
                        st.rerun()
                    else:
                        st.error(result.get("message", "Login gagal. Periksa username dan password."))
                except Exception as exc:
                    st.error(str(exc))

    with tab_reg:
        with st.form("form_reg"):
            r_user = st.text_input("Username Baru").strip()
            r_pass = st.text_input("Password Baru", type="password")
            r_pass_confirm = st.text_input("Ulangi Password", type="password")
            btn_reg = st.form_submit_button("Daftar Akun")

        if btn_reg:
            if not r_user or not r_pass or not r_pass_confirm:
                st.warning("Semua kolom wajib diisi.")
            elif r_pass != r_pass_confirm:
                st.warning("Password dan konfirmasi password tidak sama.")
            elif len(r_pass) < 8:
                st.warning("Gunakan password minimal 8 karakter.")
            else:
                try:
                    result = post_to_webapp({
                        "action": "register",
                        "username": r_user,
                        "password": r_pass,
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    if api_success(result):
                        st.success("Pendaftaran berhasil. Silakan masuk melalui tab Login.")
                    else:
                        st.warning(result.get("message", "Pendaftaran gagal."))
                except Exception as exc:
                    st.error(str(exc))

    st.stop()


# =========================================================
# MASTER DATA PARSER
# =========================================================
@st.cache_data(ttl=300, show_spinner="Memuat master data MSE600...")
def load_master_from_cloud():
    conn = st.connection("gsheets", type=GSheetsConnection)

    # Baca sebagai data mentah agar baris header bisa dicari.
    raw = conn.read(worksheet=get_worksheet_id("mse600_gid"), ttl=0, header=None)
    if raw is None or raw.empty:
        return pd.DataFrame(columns=[
            "Equipment_No", "Equipment_Name", "Status_Code",
            "Status_Description", "Project_Location", "Serial_Number_Info"
        ])

    raw = raw.fillna("")
    header_row = 0

    # Cari baris header yang paling mungkin berisi kolom equipment.
    for i in range(min(len(raw), 30)):
        row_values = clean_text_series(raw.iloc[i]).str.lower().tolist()
        row_text = " ".join(row_values)
        if any(word in row_text for word in ["equipment", "equip no", "equipment no", "unit no"]):
            header_row = i
            break

    # Mapping berdasarkan nama header jika header terbaca dengan jelas.
    header_values = clean_text_series(raw.iloc[header_row]).tolist()
    normalized_headers = [h.lower().replace("_", " ").strip() for h in header_values]

    def find_col(keywords, fallback_index):
        for idx, header in enumerate(normalized_headers):
            if any(keyword in header for keyword in keywords):
                return idx
        return fallback_index

    data = raw.iloc[header_row + 1:].copy().reset_index(drop=True)
    if data.empty:
        return pd.DataFrame(columns=[
            "Equipment_No", "Equipment_Name", "Status_Code",
            "Status_Description", "Project_Location", "Serial_Number_Info"
        ])

    ncols = data.shape[1]

    def column(index):
        if index is not None and 0 <= index < ncols:
            return clean_text_series(data.iloc[:, index])
        return pd.Series([""] * len(data), dtype="object")

    # Fallback index mempertahankan format MSE600 yang digunakan script awal.
    equipment_idx = find_col(["equipment no", "equip no", "equipment", "unit no"], 0)
    name_idx = find_col(["equipment name", "unit name", "description"], 2 if ncols > 2 else 1)
    status_idx = find_col(["status code", "status"], 3)
    status_desc_idx = find_col(["equipment status description", "status description", "status desc"], 4)
    location_idx = find_col(["project location", "location", "project"], 8 if ncols > 8 else 5)
    serial_idx = find_col(["serial number", "serial no", "serial"], 11 if ncols > 11 else 6)

    result = pd.DataFrame({
        "Equipment_No": column(equipment_idx),
        "Equipment_Name": column(name_idx),
        "Status_Code": column(status_idx),
        "Status_Description": column(status_desc_idx),
        "Project_Location": column(location_idx),
        "Serial_Number_Info": column(serial_idx),
    })

    # Buang baris kosong dan baris header yang ikut masuk ke data.
    equipment_lower = result["Equipment_No"].str.lower()
    invalid_header = equipment_lower.str.contains(
        r"^(equipment|equipment no|equip|equip no|no|unit|unit no)$",
        regex=True,
        na=False,
    )
    result = result[
        (result["Equipment_No"] != "")
        & (~invalid_header)
        & (equipment_lower != "nan")
        & (equipment_lower != "none")
    ].copy()

    # Hilangkan spasi berlebih pada seluruh kolom.
    for col in result.columns:
        result[col] = clean_text_series(result[col])

    return result.reset_index(drop=True)


try:
    df_master = load_master_from_cloud()
except Exception as exc:
    df_master = pd.DataFrame()
    st.sidebar.error(f"Gagal memuat master MSE600: {exc}")


# =========================================================
# SIDEBAR NAVIGATION
# =========================================================
if st.session_state.company_logo_bytes:
    st.sidebar.image(st.session_state.company_logo_bytes, use_container_width=True)
st.sidebar.markdown("<div class='jf-brand-card'><div class='jf-brand-mark'>JF</div><div class='jf-brand-name'>JOBSITE FLEET<br>SYSTEM</div><div class='jf-brand-caption'>Operations Control Platform</div></div>", unsafe_allow_html=True)
st.sidebar.markdown(f"<div class='jf-user-chip'>● &nbsp; Signed in as <b>{st.session_state.username}</b></div>", unsafe_allow_html=True)

menu = st.sidebar.radio(
    "Workspace Navigation",
    [
        "Dashboard Overview",
        "Master Jobsite",
        "Master Data Unit",
        "Upload / Update Master MSE600",
        "Form Mob / Demob",
        "Log Transaksi Permanen",
        "Pengaturan Tampilan",
        "Tutup Proses DEMOB",
    ],
)

st.sidebar.markdown("<div class='jf-section-label'>System Actions</div>", unsafe_allow_html=True)

if st.sidebar.button("↻  Refresh Data Real-Time"):
    st.cache_data.clear()
    st.rerun()

if st.sidebar.button("⇥  Logout"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()


# =========================================================
# 1. DASHBOARD OVERVIEW
# =========================================================
st.markdown("<div class='jf-hero'><div class='jf-kicker'>Fleet intelligence platform</div><div class='jf-title'>Jobsite Fleet Management</div><div class='jf-subtitle'>Monitor unit movement, jobsite readiness, and DEMOB closure from one operational workspace.</div></div>", unsafe_allow_html=True)
if menu == "Dashboard Overview":
    st.title("Dashboard Fleet & Operational Overview")
    st.caption("Filter dashboard mengikuti data aktual pada Master MSE600, termasuk Equipment Status Description.")

    if df_master.empty:
        st.warning("Data Master MSE600 belum tersedia atau gagal dibaca. Periksa tab MSE600 dan konfigurasi Google Sheets.")
    else:
        data = df_master.copy()
        data["_StatusFilter"] = data["Status_Description"].replace("", "Tidak diketahui").fillna("Tidak diketahui")
        data["_LocationFilter"] = data["Project_Location"].replace("", "Tidak diketahui").fillna("Tidak diketahui")
        st.subheader("Filter Dashboard")
        f1, f2, f3 = st.columns([1.2, 1.2, 1.6])
        with f1:
            status_options = sorted(data["_StatusFilter"].astype(str).unique().tolist(), key=str.casefold)
            selected_status = st.multiselect("Status Description", status_options, default=status_options, key="dash_status_filter")
        with f2:
            location_options = sorted(data["_LocationFilter"].astype(str).unique().tolist(), key=str.casefold)
            selected_locations = st.multiselect("Lokasi / Jobsite", location_options, default=location_options, key="dash_location_filter")
        with f3:
            search = st.text_input("Cari nomor unit / nama / serial", key="dash_search")

        if selected_status:
            data = data[data["_StatusFilter"].isin(selected_status)]
        else:
            data = data.iloc[0:0]
        if selected_locations:
            data = data[data["_LocationFilter"].isin(selected_locations)]
        else:
            data = data.iloc[0:0]
        if search.strip():
            mask = pd.Series(False, index=data.index)
            for col in ["Equipment_No", "Equipment_Name", "Serial_Number_Info"]:
                mask |= data[col].fillna("").astype(str).str.contains(search.strip(), case=False, regex=False, na=False)
            data = data[mask]

        total_unit = len(data)
        status_code = data["Status_Code"].fillna("").astype(str).str.strip().str.upper()
        available_unit = int(status_code.isin(["AV", "AVAILABLE"]).sum())
        off_hire_unit = int(status_code.isin(["OH", "OFF HIRE", "OFF-HIRE", "OFFHIRE"]).sum())
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Unit sesuai filter", f"{total_unit:,}")
        col2.metric("Available (AV)", f"{available_unit:,}")
        col3.metric("Off Hire (OH)", f"{off_hire_unit:,}")
        col4.metric("Status Description unik", f"{data['_StatusFilter'].nunique():,}")

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Jumlah Unit per Status Description")
            sc = data["_StatusFilter"].value_counts().rename_axis("Status Description").reset_index(name="Jumlah Unit")
            if not sc.empty:
                st.plotly_chart(px.bar(sc, x="Status Description", y="Jumlah Unit", text="Jumlah Unit"), use_container_width=True)
            else:
                st.info("Tidak ada unit sesuai filter yang dipilih.")
        with c2:
            st.subheader("Sebaran Unit per Jobsite")
            loc = data["_LocationFilter"].value_counts().head(15).rename_axis("Jobsite").reset_index(name="Jumlah Unit")
            if not loc.empty:
                st.plotly_chart(px.bar(loc, x="Jumlah Unit", y="Jobsite", orientation="h", text="Jumlah Unit"), use_container_width=True)
            else:
                st.info("Tidak ada lokasi sesuai filter yang dipilih.")

        st.subheader("Detail Unit sesuai Filter")
        st.dataframe(data.drop(columns=["_StatusFilter", "_LocationFilter"], errors="ignore"), use_container_width=True, height=360, hide_index=True)
        st.caption(f"Menampilkan {len(data):,} unit setelah filter.")


# =========================================================
# 1A. MASTER JOBSITE
# =========================================================
elif menu == "Master Jobsite":
    st.title("Master Jobsite")
    st.caption("Daftar lokasi resmi yang digunakan pada pilihan Lokasi Asal dan Lokasi Tujuan di Form MOB/DEMOB.")
    try:
        jobsites = load_jobsite_names()
    except Exception as exc:
        jobsites = []
        st.error(f"Gagal memuat Master Jobsite: {exc}")

    with st.form("add_jobsite_form", clear_on_submit=True):
        new_jobsite = st.text_input("Nama Jobsite / Lokasi Baru", placeholder="Contoh: KPP INDE")
        add_clicked = st.form_submit_button("Tambah Jobsite", type="primary")
    if add_clicked:
        if not new_jobsite.strip():
            st.warning("Nama jobsite wajib diisi.")
        else:
            try:
                result = post_to_webapp({"action": "add_jobsite", "jobsite_name": new_jobsite.strip()})
                if api_success(result):
                    st.success(result.get("message", "Jobsite berhasil ditambahkan."))
                    load_jobsite_names.clear()
                    st.rerun()
                else:
                    st.error(result.get("message", "Jobsite gagal ditambahkan."))
            except Exception as exc:
                st.error(f"Gagal menambahkan jobsite: {exc}")

    st.markdown("---")
    st.subheader(f"Daftar Jobsite Aktif ({len(jobsites)})")
    if jobsites:
        st.dataframe(pd.DataFrame({"No": range(1, len(jobsites) + 1), "Jobsite_Name": jobsites}), use_container_width=True, hide_index=True)
        with st.form("remove_jobsite_form"):
            remove_name = st.selectbox("Pilih jobsite yang akan dihapus", jobsites)
            confirm_remove = st.checkbox("Saya yakin ingin menghapus lokasi ini dari pilihan form.")
            remove_clicked = st.form_submit_button("Hapus Jobsite Terpilih")
        if remove_clicked:
            if not confirm_remove:
                st.warning("Centang konfirmasi terlebih dahulu.")
            else:
                try:
                    result = post_to_webapp({"action": "remove_jobsite", "jobsite_name": remove_name})
                    if api_success(result):
                        st.success(result.get("message", "Jobsite berhasil dihapus."))
                        load_jobsite_names.clear()
                        st.rerun()
                    else:
                        st.error(result.get("message", "Jobsite gagal dihapus."))
                except Exception as exc:
                    st.error(f"Gagal menghapus jobsite: {exc}")
    else:
        st.info("Master Jobsite masih kosong. Tambahkan lokasi pertama menggunakan form di atas.")


# =========================================================
# 2. MASTER DATA UNIT
# =========================================================
elif menu == "Master Data Unit":
    st.title("Master Data Equipment (Live)")

    if df_master.empty:
        st.warning("Data Master belum tersedia. Periksa tab MSE600 atau upload file master.")
    else:
        search = st.text_input("Cari Unit No / Nama / Serial Number:")
        filtered = df_master.copy()

        if search.strip():
            search_term = search.strip()
            searchable_cols = ["Equipment_No", "Equipment_Name", "Serial_Number_Info"]
            mask = pd.Series(False, index=filtered.index)
            for col in searchable_cols:
                mask |= filtered[col].fillna("").astype(str).str.contains(
                    search_term, case=False, regex=False, na=False
                )
            filtered = filtered[mask]

        st.caption(f"Menampilkan {len(filtered):,} dari {len(df_master):,} unit.")
        st.dataframe(filtered, use_container_width=True, height=450, hide_index=True)


# =========================================================
# 3. UPLOAD / UPDATE MASTER MSE600
# =========================================================
elif menu == "Upload / Update Master MSE600":
    st.title("Upload & Perbarui Master Data MSE600")
    st.warning(
        "Upload akan mengganti data pada tab MSE600 jika Apps Script Anda "
        "memang dibuat untuk menimpa seluruh isi tab tersebut."
    )

    uploaded_file = st.file_uploader(
        "Pilih file Excel MSE600 (.xlsx atau .xls)",
        type=["xlsx", "xls"],
    )

    if uploaded_file is not None:
        try:
            uploaded_file.seek(0)
            preview_df = pd.read_excel(uploaded_file, header=None, dtype=object)
            preview_df = preview_df.fillna("")
            # Remove completely blank rows, but retain the source header rows.
            preview_df = preview_df.loc[~preview_df.astype(str).apply(
                lambda row: row.str.strip().eq("").all(), axis=1
            )].reset_index(drop=True)
            if preview_df.empty or preview_df.shape[1] < 2:
                st.error("File Excel kosong atau jumlah kolom tidak memadai.")
                st.stop()
            row_widths = {len(row) for row in preview_df.values.tolist()}
            if len(row_widths) != 1:
                st.error("Struktur kolom tidak konsisten. Periksa file Excel.")
                st.stop()
            st.caption(f"Preview file: {len(preview_df)} baris × {len(preview_df.columns)} kolom.")
            st.dataframe(preview_df.head(10), use_container_width=True, hide_index=True)

            if st.button("Simpan Master ke Cloud Permanen", type="primary"):
                rows = preview_df.astype(str).values.tolist()
                header_candidates = [" ".join(str(v).lower() for v in row) for row in rows[:30]]
                if not any(any(term in line for term in ["equipment", "equip no", "equipment no", "unit no"])
                           for line in header_candidates):
                    st.error("Header Equipment Number tidak ditemukan dalam 30 baris pertama. Upload dibatalkan.")
                    st.stop()
                payload = {
                    "action": "upload_master",
                    "rows": rows,
                    "Request_ID": str(uuid.uuid4()),
                }
                with st.spinner("Mengirim data ke Google Sheets..."):
                    result = post_to_webapp(payload)

                if api_success(result):
                    st.success(result.get("message", "Master MSE600 berhasil disimpan."))
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(result.get("message", "Apps Script menolak penyimpanan master."))
        except Exception as exc:
            st.error(f"Gagal membaca atau mengirim file: {exc}")

    st.markdown("---")
    if st.checkbox("🔍 Debug: lihat data mentah di Cloud"):
        conn = get_gsheets_connection()
        if conn is not None:
            try:
                raw = conn.read(worksheet=get_worksheet_id("mse600_gid"), ttl=0, header=None)
                st.write(f"Total baris di tab MSE600: {len(raw)}")
                st.dataframe(raw.head(10), use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error(f"Gagal membaca tab MSE600: {exc}")


# =========================================================
# 4. FORM MOB / DEMOB
# =========================================================
elif menu == "Form Mob / Demob":
    st.title("Form Mobilisasi & Demobilisasi")
    st.info("Saat transaksi berhasil, sistem mencatat log dan memperbarui Equipment Status Description serta Project_Location pada Master MSE600.")

    if df_master.empty:
        st.warning("Data Master MSE600 belum tersedia. Upload file master terlebih dahulu.")
    else:
        try:
            jobsites = load_jobsite_names()
        except Exception as exc:
            jobsites = []
            st.error(f"Master Jobsite tidak dapat dimuat: {exc}")

        if not jobsites:
            st.warning("Master Jobsite masih kosong. Buka menu Master Jobsite dan tambahkan lokasi terlebih dahulu.")
        else:
            valid_master = df_master[df_master["Equipment_No"].str.strip() != ""].copy().reset_index(drop=True)
            if valid_master.empty:
                st.warning("Tidak ada Equipment Number yang valid di master data.")
            else:
                unit_labels = []
                for _, row in valid_master.iterrows():
                    unit_no, unit_name = row["Equipment_No"], row["Equipment_Name"]
                    unit_labels.append(f"{unit_no} - {unit_name}" if unit_name else unit_no)

                with st.form("form_mob_demob", clear_on_submit=True):
                    st.subheader("Informasi Unit dan Transaksi")
                    c1, c2 = st.columns(2)
                    with c1:
                        selected_index = st.selectbox("Pilih Unit", options=list(range(len(unit_labels))), format_func=lambda i: unit_labels[i])
                        aksi = st.selectbox("Jenis Aksi", ["MOBILISASI (MOB)", "DEMOBILISASI (DEMOB)"])
                        tgl = st.date_input("Tanggal Transaksi", value=datetime.today().date())
                    with c2:
                        pic = st.text_input("PIC (terkunci sesuai user login)", value=st.session_state.username, disabled=True)
                        st.caption("PIC otomatis diambil dari akun yang sedang login dan tidak dapat diedit di form.")
                        ket = st.text_input("Keterangan (opsional)", placeholder="Catatan tambahan transaksi")

                    selected_unit = valid_master.iloc[selected_index]
                    current_location = str(selected_unit.get("Project_Location", "")).strip()
                    st.markdown("---")
                    st.subheader("Perpindahan Lokasi")
                    l1, l2 = st.columns(2)
                    with l1:
                        origin_default = jobsites.index(current_location) if current_location in jobsites else 0
                        asal = st.selectbox("Lokasi Asal", jobsites, index=origin_default, help="Pilihan diambil dari Master Jobsite.")
                    with l2:
                        tujuan = st.selectbox("Lokasi Tujuan", jobsites, index=origin_default if current_location in jobsites else min(1, len(jobsites)-1), help="Pilihan diambil dari Master Jobsite.")
                    if current_location and current_location not in jobsites:
                        st.warning(f"Lokasi unit saat ini '{current_location}' belum terdaftar di Master Jobsite. Perbarui master lokasi bila diperlukan.")
                    submitted = st.form_submit_button("Simpan Transaksi & Update Master", type="primary")

                if submitted:
                    selected_unit = valid_master.iloc[selected_index]
                    eq_no = str(selected_unit["Equipment_No"]).strip()
                    eq_name = str(selected_unit["Equipment_Name"]).strip()
                    if not asal or not tujuan:
                        st.warning("Lokasi Asal dan Lokasi Tujuan wajib dipilih.")
                    elif asal == tujuan:
                        st.warning("Lokasi asal dan tujuan sama. Pilih lokasi yang berbeda untuk transaksi perpindahan.")
                    else:
                        request_id = str(uuid.uuid4())
                        payload = {
                            "action": "mob_demob",
                            "Request_ID": request_id,
                            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "Tanggal_Transaksi": tgl.strftime("%Y-%m-%d"),
                            "Equipment_No": eq_no,
                            "Nama_Unit": eq_name,
                            "Jenis_Aksi": aksi,
                            "Lokasi_Asal": asal,
                            "Lokasi_Tujuan": tujuan,
                            "Keterangan": ket.strip(),
                            "PIC": st.session_state.username,
                        }
                        try:
                            with st.spinner("Menyimpan transaksi dan memperbarui database unit..."):
                                result = post_to_webapp(payload)
                            if api_success(result):
                                st.success(result.get("message", "Transaksi tersimpan dan master unit diperbarui."))
                                if result.get("master_updated"):
                                    st.success(f"Master MSE600 diperbarui: Equipment Status Description = {result.get('new_status_description', aksi)}; Project_Location = {tujuan}.")
                                else:
                                    st.warning("Log tersimpan, tetapi backend tidak mengonfirmasi pembaruan master. Periksa tab MSE600.")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(result.get("message", "Transaksi gagal disimpan."))
                        except Exception as exc:
                            st.error(f"Gagal menyimpan transaksi: {exc}")


# =========================================================
# 5. LOG TRANSAKSI PERMANEN
# =========================================================
elif menu == "Log Transaksi Permanen":
    st.title("Log Transaksi Real-Time")
    conn = get_gsheets_connection()

    if conn is not None:
        try:
            db_data = conn.read(worksheet=get_worksheet_id("log_trans_gid"), ttl=0)

            if db_data is None or db_data.empty:
                st.info("Belum ada data transaksi tercatat di tab Log_Trans.")
            else:
                if "Timestamp" in db_data.columns:
                    db_data = db_data.sort_values("Timestamp", ascending=False, kind="stable")
                st.caption(f"Total transaksi: {len(db_data):,}")
                st.dataframe(db_data, use_container_width=True, hide_index=True)

                csv_data = db_data.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "Export CSV",
                    data=csv_data,
                    file_name="log_mob_demob.csv",
                    mime="text/csv",
                )
        except Exception as exc:
            st.error(
                "Gagal membaca tab Log_Trans. Periksa nama worksheet, "
                f"izin akses, dan konfigurasi koneksi. Detail: {exc}"
            )


# =========================================================
# 6. SETTINGS: COMPANY BRANDING
# =========================================================
elif menu == "Pengaturan Tampilan":
    st.title("Pengaturan Tampilan")
    st.markdown("Unggah identitas visual agar dashboard terasa lebih sesuai dengan perusahaan.")
    st.warning("Logo dan background yang diunggah di sini tersimpan pada sesi browser Streamlit saat ini saja. Untuk permanen bagi semua pengguna, simpan aset di hosting/Google Drive dan konfigurasi URL tetap.")
    col_logo, col_bg = st.columns(2)
    with col_logo:
        st.subheader("Logo Perusahaan")
        logo_file = st.file_uploader("Upload logo (PNG/JPG)", type=["png", "jpg", "jpeg"], key="branding_logo_upload")
        if logo_file:
            st.session_state.company_logo_bytes = logo_file.getvalue()
        if st.session_state.company_logo_bytes:
            st.image(st.session_state.company_logo_bytes, caption="Preview logo", width=220)
            if st.button("Hapus logo dari sesi", key="clear_logo"):
                st.session_state.company_logo_bytes = None
                st.rerun()
    with col_bg:
        st.subheader("Background Dashboard")
        bg_file = st.file_uploader("Upload background (JPG/PNG)", type=["png", "jpg", "jpeg"], key="branding_bg_upload")
        if bg_file:
            st.session_state.background_bytes = bg_file.getvalue()
        if st.session_state.background_bytes:
            st.image(st.session_state.background_bytes, caption="Preview background", use_container_width=True)
            if st.button("Hapus background dari sesi", key="clear_bg"):
                st.session_state.background_bytes = None
                st.rerun()
    st.caption("Saran: gunakan logo PNG transparan dan background landscape dengan kontras rendah agar teks tetap terbaca.")

# =========================================================
# 7. CLOSE DEMOB PROCESS
# =========================================================
elif menu == "Tutup Proses DEMOB":
    st.title("Tutup Proses DEMOB")
    st.caption("Tutup transaksi DEMOB setelah unit dan dokumen sudah diverifikasi selesai. Tindakan ini mencatat waktu penutupan dan username PIC.")
    conn = get_gsheets_connection()
    if conn is None:
        st.error("Koneksi Google Sheets tidak tersedia untuk membaca transaksi.")
    else:
        try:
            logs = conn.read(worksheet=get_worksheet_id("log_trans_gid"), ttl=0)
            if logs is None or logs.empty:
                st.info("Belum ada transaksi.")
            else:
                if "Process_Status" not in logs.columns:
                    logs["Process_Status"] = "OPEN"
                logs["Process_Status"] = logs["Process_Status"].fillna("").astype(str).str.strip().str.upper()
                demobs = logs[logs["Jenis_Aksi"].astype(str).str.contains("DEMOB", case=False, na=False)].copy()
                demobs.loc[demobs["Process_Status"] == "", "Process_Status"] = "OPEN"
                open_demobs = demobs[demobs["Process_Status"] == "OPEN"]
                m1,m2,m3 = st.columns(3)
                m1.metric("Total DEMOB", len(demobs))
                m2.metric("OPEN", len(open_demobs))
                m3.metric("CLOSE", int((demobs["Process_Status"] == "CLOSE").sum()))
                if open_demobs.empty:
                    st.success("Tidak ada proses DEMOB berstatus OPEN.")
                else:
                    show_cols = [c for c in ["Tanggal_Transaksi","Equipment_No","Nama_Unit","Lokasi_Asal","Lokasi_Tujuan","PIC","Request_ID","Process_Status"] if c in open_demobs.columns]
                    st.dataframe(open_demobs[show_cols], use_container_width=True, hide_index=True)
                    options = open_demobs.to_dict("records")
                    labels = [f"{r.get('Equipment_No','')} | {r.get('Tanggal_Transaksi','')} | {r.get('Lokasi_Asal','')} → {r.get('Lokasi_Tujuan','')}" for r in options]
                    selected = st.selectbox("Pilih proses DEMOB yang selesai diverifikasi", range(len(options)), format_func=lambda i: labels[i])
                    confirm = st.checkbox("Saya sudah memverifikasi proses DEMOB dan menyetujui penutupan.")
                    if st.button("Tutup Proses DEMOB", type="primary", disabled=not confirm):
                        req_id = str(options[selected].get("Request_ID", "")).strip()
                        if not req_id:
                            st.error("Request_ID kosong; proses tidak dapat ditutup dengan aman.")
                        else:
                            response = post_to_webapp({"action":"close_demob","Request_ID":req_id,"Closed_By":st.session_state.username})
                            if api_success(response):
                                st.success(response.get("message", "Proses ditutup."))
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(response.get("message", "Gagal menutup proses DEMOB."))
        except Exception as exc:
            st.error(f"Gagal memuat atau memperbarui status DEMOB: {exc}")
