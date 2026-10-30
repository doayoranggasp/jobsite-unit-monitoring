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
    :root { --navy:#14243a; --blue:#1769aa; --ink:#172b4d; --muted:#66758a; --line:#e5eaf1; --surface:#ffffff; --canvas:#f3f6fa; }
    .stApp { background:var(--canvas); color:var(--ink); }
    [data-testid="stHeader"] { background:rgba(243,246,250,.92); }
    [data-testid="stSidebar"] { background:#14243a; border-right:1px solid #263a55; }
    [data-testid="stSidebar"] * { color:#edf3fb !important; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label { padding:7px 10px; border-radius:8px; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background:#263d5b; }
    [data-testid="stSidebar"] hr { border-color:#344963; }
    [data-testid="stSidebar"] .stButton button { background:#2677c9; border:0; color:white !important; }
    .block-container { max-width:1500px; padding-top:2rem; padding-bottom:3rem; }
    h1,h2,h3 { color:#172b4d; letter-spacing:-.02em; }
    h1 { font-weight:750; }
    [data-testid="stMetric"] { background:#fff; border:1px solid var(--line); padding:17px 18px; border-radius:13px; box-shadow:0 2px 8px rgba(20,36,58,.04); }
    [data-testid="stMetricLabel"] { color:#66758a; font-weight:600; }
    [data-testid="stMetricValue"] { color:#172b4d; font-weight:750; }
    [data-testid="stForm"] { background:#fff; border:1px solid var(--line); padding:22px; border-radius:14px; }
    [data-testid="stDataFrame"] { background:#fff; border:1px solid var(--line); border-radius:12px; }
    .page-eyebrow { color:#1769aa; text-transform:uppercase; letter-spacing:.12em; font-size:.76rem; font-weight:800; margin-bottom:.35rem; }
    .page-subtitle { color:#66758a; margin-top:-.55rem; margin-bottom:1.3rem; }
    .section-card { background:#fff; border:1px solid #e5eaf1; border-radius:14px; padding:18px 20px; margin:10px 0 16px; }
    .section-card h3 { margin:0 0 5px 0; font-size:1.05rem; }
    .section-card p { color:#66758a; margin:0; font-size:.9rem; }
    .stButton button, .stFormSubmitButton button { border-radius:9px; font-weight:650; min-height:2.55rem; }
    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] { border-radius:8px; }
    div[data-testid="stAlert"] { border-radius:10px; }
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
if "user_role" not in st.session_state:
    st.session_state.user_role = "Operator"


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


def load_branding_assets():
    """Baca konfigurasi logo dan background dari worksheet App_Assets."""
    conn = get_gsheets_connection()
    if conn is None:
        return pd.DataFrame(columns=["Asset_Key", "Asset_URL", "Active", "Updated_By", "Updated_At"])
    gid = get_worksheet_id("branding_assets_gid")
    try:
        df = conn.read(worksheet=gid, ttl=60)
    except Exception:
        # Worksheet baru mungkin belum memiliki header/data.
        return pd.DataFrame(columns=["Asset_Key", "Asset_URL", "Active", "Updated_By", "Updated_At"])
    if df is None or df.empty:
        return pd.DataFrame(columns=["Asset_Key", "Asset_URL", "Active", "Updated_By", "Updated_At"])
    df.columns = [str(c).strip() for c in df.columns]
    for col in ["Asset_Key", "Asset_URL", "Active", "Updated_By", "Updated_At"]:
        if col not in df.columns:
            df[col] = ""
    return df[["Asset_Key", "Asset_URL", "Active", "Updated_By", "Updated_At"]].fillna("")


def get_branding_url(asset_key):
    """Ambil URL aset aktif dari database branding."""
    try:
        assets = load_branding_assets()
        if assets.empty:
            return ""
        rows = assets[assets["Asset_Key"].astype(str).str.strip().str.upper() == asset_key.upper()]
        if rows.empty:
            return ""
        row = rows.iloc[-1]
        active = str(row.get("Active", "TRUE")).strip().upper()
        if active in ["FALSE", "0", "NO", "NONAKTIF"]:
            return ""
        url = str(row.get("Asset_URL", "")).strip()
        return url if url.startswith(("https://", "http://")) else ""
    except Exception:
        return ""


def save_branding_assets(logo_url, background_url):
    """Simpan dua aset branding ke worksheet App_Assets."""
    conn = get_gsheets_connection()
    if conn is None:
        raise RuntimeError("Koneksi Google Sheets tidak tersedia.")
    gid = get_worksheet_id("branding_assets_gid")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = pd.DataFrame([
        {"Asset_Key": "COMPANY_LOGO", "Asset_URL": logo_url.strip(), "Active": "TRUE", "Updated_By": st.session_state.username, "Updated_At": now},
        {"Asset_Key": "APP_BACKGROUND", "Asset_URL": background_url.strip(), "Active": "TRUE", "Updated_By": st.session_state.username, "Updated_At": now},
    ])
    conn.update(worksheet=gid, data=rows)
    st.cache_data.clear()


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
                        st.session_state.user_role = str(result.get("role", "Operator"))
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
    status_desc_idx = find_col(["status description", "status desc"], 4)
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
logo_url = get_branding_url("COMPANY_LOGO")
background_url = get_branding_url("APP_BACKGROUND")
if logo_url:
    st.sidebar.image(logo_url, use_container_width=True)
st.sidebar.markdown("## JOBSITE FLEET")
st.sidebar.caption("OPERATIONS MANAGEMENT SYSTEM")
if background_url:
    st.markdown(f"""<style>.stApp {{ background-image: linear-gradient(rgba(244,247,251,.91), rgba(244,247,251,.91)), url('{background_url}'); background-size: cover; background-position: center; background-attachment: fixed; }}</style>""", unsafe_allow_html=True)
role = str(st.session_state.get("user_role", "Operator")).strip().lower()
is_supervisor = role in ["supervisor", "admin", "warehouse supervisor"]
st.sidebar.info(f"{st.session_state.username}  ·  {st.session_state.user_role}")
module = st.sidebar.radio("PILIH AREA KERJA", ["Unit Management", "Warehouse Management"], key="active_module_choice")
unit_pages = ["Dashboard Overview", "Master Jobsite", "Master Data Unit", "Upload / Update Master MSE600", "Form Mob / Demob", "Log Transaksi Permanen"]
# Dashboard temuan dapat dilihat seluruh user Warehouse; menu administrasi tetap khusus supervisor.
warehouse_pages = ["Bank Problem Dashboard", "Submit Bank Problem", "My Problem Tickets", "Follow Up Temuan"]
if is_supervisor:
    warehouse_pages += ["Master Kategori Problem", "Problem Analysis", "Branding & Tampilan"]
if module == "Warehouse Management":
    st.sidebar.markdown("### WAREHOUSE WORKSPACE")
    menu = st.sidebar.radio("Navigasi Warehouse", warehouse_pages, key="warehouse_navigation")
    st.sidebar.caption("Follow Up Temuan tersedia untuk seluruh tim Warehouse. Closing tiket khusus Supervisor/Admin.")
else:
    st.sidebar.markdown("### FLEET WORKSPACE")
    menu = st.sidebar.radio("Navigasi Unit", unit_pages, key="unit_navigation")
st.sidebar.markdown("---")
if st.sidebar.button("↻  Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
if st.sidebar.button("Keluar", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.user_role = "Operator"
    st.rerun()


# =========================================================
# 1. DASHBOARD OVERVIEW
# =========================================================
if menu == "Dashboard Overview":
    st.title("Dashboard Fleet & Operational Overview")
    st.caption("Filter dashboard mengikuti data aktual pada Master MSE600, termasuk Status_Description.")

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
    st.info("Saat transaksi berhasil, sistem mencatat log dan memperbarui Status_Description serta Project_Location pada Master MSE600.")

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
                                    st.success(f"Master MSE600 diperbarui: Status_Description = {result.get('new_status_description', aksi)}; Project_Location = {tujuan}.")
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
# WAREHOUSE MANAGEMENT - BANK PROBLEM TICKETING
# =========================================================
def bank_api(action, **kwargs):
    return post_to_webapp({"action": action, "username": st.session_state.username, "user_role": st.session_state.user_role, **kwargs})

def load_problem_categories():
    r = bank_api("get_problem_categories")
    if not api_success(r):
        raise RuntimeError(r.get("message", "Gagal memuat kategori"))
    return r.get("categories", [])

def load_problem_tickets(own_only=False):
    r = bank_api("get_problem_tickets", own_only=own_only)
    if not api_success(r):
        raise RuntimeError(r.get("message", "Gagal memuat tiket"))
    return pd.DataFrame(r.get("tickets", []))

def page_heading(eyebrow, title, subtitle):
    st.markdown(f'<div class="page-eyebrow">{eyebrow}</div><h1>{title}</h1><div class="page-subtitle">{subtitle}</div>', unsafe_allow_html=True)

def status_counts(frame):
    statuses = frame.get("Status", pd.Series(dtype=str)).fillna("").astype(str).str.upper().str.strip()
    return len(frame), int((statuses == "OPEN").sum()), int((statuses == "IN PROGRESS").sum()), int(statuses.isin(["CLOSE", "CLOSED"]).sum())

if menu == "Submit Bank Problem":
    page_heading("WAREHOUSE · TICKETING", "Buat Laporan Problem", "Catat kendala material dengan data yang jelas agar dapat ditindaklanjuti oleh Warehouse Supervisor.")
    st.markdown('<div class="section-card"><h3>Alur pelaporan</h3><p>Isi informasi material → jelaskan temuan → kirim tiket → pantau perkembangan pada menu My Problem Tickets.</p></div>', unsafe_allow_html=True)
    try:
        categories = load_problem_categories()
        active_categories = [x["category"] for x in categories if str(x.get("active", "TRUE")).upper() not in ["FALSE", "0", "NO"]]
    except Exception as exc:
        active_categories = []
        st.error(f"Kategori gagal dimuat: {exc}")
    with st.form("bank_problem_submit", clear_on_submit=True):
        st.subheader("01 · Identitas material")
        a, b = st.columns(2)
        with a:
            wr = st.text_input("Work Request (WR) *", placeholder="Contoh: WR-2026-00125", help="Masukkan nomor WR yang terkait dengan temuan.")
            stockcode = st.text_input("Stockcode *", placeholder="Masukkan nomor stockcode", help="Gunakan angka sesuai master material.")
        with b:
            category = st.selectbox("Kategori problem *", active_categories if active_categories else ["Kategori belum tersedia"])
            st.caption("Kategori digunakan untuk pengelompokan dan analisis temuan.")
        st.divider()
        st.subheader("02 · Detail kuantitas")
        c, d = st.columns(2)
        with c:
            qty_fisik = st.number_input("Qty fisik", min_value=0.0, step=1.0, help="Jumlah aktual hasil pengecekan fisik.")
        with d:
            qty_ellipse = st.number_input("Qty Ellipse", min_value=0.0, step=1.0, help="Jumlah yang tercatat pada sistem Ellipse.")
        st.divider()
        st.subheader("03 · Uraian temuan")
        description = st.text_area("Jelaskan problem yang ditemukan *", height=140, placeholder="Tuliskan kondisi aktual, lokasi/bin, kronologi pengecekan, dan dampak terhadap operasional.")
        st.caption("Pastikan uraian singkat, faktual, dan mudah dipahami oleh PIC tindak lanjut.")
        submit = st.form_submit_button("KIRIM LAPORAN PROBLEM", type="primary", use_container_width=True)
    if submit:
        if not wr.strip() or not stockcode.strip() or not description.strip():
            st.warning("Lengkapi WR, Stockcode, dan uraian problem terlebih dahulu.")
        elif not stockcode.strip().isdigit():
            st.warning("Stockcode harus berupa angka.")
        elif not active_categories:
            st.warning("Master kategori belum tersedia. Hubungi Warehouse Supervisor.")
        else:
            try:
                result = bank_api("create_problem_ticket", WR=wr.strip(), Stockcode=stockcode.strip(), Qty_Fisik=qty_fisik, Qty_Ellipse=qty_ellipse, Kategori=category, Uraian_Problem=description.strip())
                if api_success(result):
                    st.success(f"Laporan berhasil dikirim. Nomor tiket: {result.get('ticket_id')} · Status OPEN")
                    st.rerun()
                else:
                    st.error(result.get("message", "Gagal membuat tiket."))
            except Exception as exc:
                st.error(f"Pengiriman tiket gagal: {exc}")

elif menu == "My Problem Tickets":
    page_heading("WAREHOUSE · TRACKING", "Tiket Saya", "Pantau status dan tindak lanjut dari setiap laporan yang Anda kirim.")
    try:
        dfp = load_problem_tickets(own_only=True)
        if dfp.empty:
            st.info("Belum ada laporan problem. Gunakan menu Buat Laporan Problem untuk mengirim temuan pertama.")
        else:
            total, opened, progress, closed = status_counts(dfp)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total laporan", total); m2.metric("Open", opened); m3.metric("In Progress", progress); m4.metric("Closed", closed)
            show_cols = [c for c in ["Ticket_ID", "Timestamp", "WR", "Stockcode", "Kategori", "Status", "PIC", "Updated_Timestamp"] if c in dfp]
            st.dataframe(dfp[show_cols], use_container_width=True, hide_index=True)
            st.download_button("Unduh riwayat tiket (CSV)", dfp.to_csv(index=False).encode("utf-8-sig"), "riwayat_problem_tiket.csv", "text/csv")
    except Exception as exc:
        st.error(str(exc))

elif menu == "Bank Problem Dashboard":
    page_heading("WAREHOUSE · PERFORMANCE", "Dashboard Temuan Warehouse", "Ringkasan kondisi tiket, kategori temuan, dan aktivitas tindak lanjut secara real-time.")
    try:
        dfp = load_problem_tickets(False)
        if dfp.empty:
            st.info("Belum ada tiket problem yang tercatat.")
        else:
            total, opened, progress, closed = status_counts(dfp)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("TOTAL TEMUAN", total); m2.metric("OPEN", opened); m3.metric("IN PROGRESS", progress); m4.metric("CLOSED", closed)
            left, right = st.columns([1.15, 1])
            with left:
                st.markdown("#### Temuan berdasarkan kategori")
                if "Kategori" in dfp:
                    cat = dfp["Kategori"].fillna("Tidak dikategorikan").value_counts().rename_axis("Kategori").reset_index(name="Jumlah")
                    st.plotly_chart(px.bar(cat, x="Jumlah", y="Kategori", orientation="h", text="Jumlah", color_discrete_sequence=["#2878b8"]), use_container_width=True)
            with right:
                st.markdown("#### Komposisi status")
                if "Status" in dfp:
                    st.plotly_chart(px.pie(dfp, names="Status", hole=.58, color_discrete_sequence=["#e3a43b", "#2878b8", "#2d9b75"]), use_container_width=True)
            st.markdown("#### Tiket terbaru")
            show_cols = [c for c in ["Ticket_ID", "Timestamp", "WR", "Stockcode", "Kategori", "Status", "PIC", "Pelapor"] if c in dfp]
            st.dataframe(dfp[show_cols].head(15), use_container_width=True, hide_index=True)
            st.download_button("Export seluruh temuan (CSV)", dfp.to_csv(index=False).encode("utf-8-sig"), "bank_problem_all_tickets.csv", "text/csv")
    except Exception as exc:
        st.error(f"Dashboard gagal memuat data: {exc}")

elif menu in ["All Problem Tickets", "Follow Up Temuan"]:
    page_heading("WAREHOUSE · TICKET ACTION", "Follow Up Temuan", "Seluruh anggota Warehouse dapat memperbarui progres, PIC, analisis, dan tindakan perbaikan. Penutupan tiket hanya dapat dilakukan Supervisor/Admin.")
    try:
        dfp = load_problem_tickets(False)
        if dfp.empty:
            st.info("Belum ada tiket yang perlu ditindaklanjuti.")
        else:
            total, opened, progress, closed = status_counts(dfp)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total", total); m2.metric("Open", opened); m3.metric("In Progress", progress); m4.metric("Closed", closed)
            statuses = ["Semua status", "OPEN", "IN PROGRESS", "CLOSE"]
            filter_status = st.selectbox("Filter status tiket", statuses)
            view = dfp.copy()
            if filter_status != "Semua status" and "Status" in view:
                view = view[view["Status"].astype(str).str.upper() == filter_status]
            id_col = "Ticket_ID"
            if id_col not in view or view.empty:
                st.info("Tidak ada tiket pada filter tersebut.")
            else:
                cols = [c for c in ["Ticket_ID", "Timestamp", "WR", "Stockcode", "Kategori", "Status", "PIC"] if c in view]
                st.dataframe(view[cols], use_container_width=True, hide_index=True)
                ticket_ids = view[id_col].astype(str).tolist()
                selected = st.selectbox("Pilih nomor tiket untuk follow up", ticket_ids)
                row = dfp[dfp[id_col].astype(str) == selected].iloc[0]
                st.markdown('<div class="section-card"><h3>Detail temuan</h3><p>Periksa informasi laporan sebelum menentukan tindak lanjut.</p></div>', unsafe_allow_html=True)
                d1, d2, d3 = st.columns(3)
                d1.write("**WR**\n\n" + str(row.get("WR", "-")))
                d2.write("**Stockcode**\n\n" + str(row.get("Stockcode", "-")))
                d3.write("**Kategori**\n\n" + str(row.get("Kategori", "-")))
                q1, q2 = st.columns(2)
                q1.metric("Qty Fisik", row.get("Qty_Fisik", 0)); q2.metric("Qty Ellipse", row.get("Qty_Ellipse", 0))
                st.info(str(row.get("Uraian_Problem", "Tidak ada uraian.")))
                with st.form("ticket_followup"):
                    st.subheader("Form tindak lanjut tim Warehouse")
                    old_status = str(row.get("Status", "OPEN")).upper()
                    status_values = ["OPEN", "IN PROGRESS"] + (["CLOSE"] if is_supervisor else [])
                    if old_status in ["CLOSED", "CLOSE"] and not is_supervisor:
                        st.warning("Tiket ini sudah ditutup. Hubungi Supervisor/Admin jika perlu koreksi.")
                    status_new = st.selectbox("Status tiket", status_values, index=status_values.index(old_status) if old_status in status_values else 0, disabled=(old_status in ["CLOSED", "CLOSE"] and not is_supervisor))
                    pic = st.text_input("PIC / Penanggung jawab", value=str(row.get("PIC", "")), placeholder="Nama PIC / fungsi")
                    analysis = st.text_area("Analisis penyebab", value=str(row.get("Analisa_Supervisor", "")), height=100, placeholder="Tuliskan hasil verifikasi dan akar penyebab problem.")
                    action_text = st.text_area("Tindakan perbaikan", value=str(row.get("Tindakan_Perbaikan", "")), height=100, placeholder="Tuliskan tindakan korektif yang dilakukan atau direncanakan.")
                    closing = st.text_area("Catatan penyelesaian / closing remarks", value=str(row.get("Closing_Remarks", "")), height=85, placeholder="Wajib diisi saat status diubah menjadi CLOSE.")
                    save = st.form_submit_button("SIMPAN FOLLOW UP TIKET", type="primary", use_container_width=True)
                if save:
                    if status_new == "CLOSE" and (not closing.strip() or not pic.strip() or not action_text.strip()):
                        st.error("Sebelum tiket ditutup, PIC, tindakan perbaikan, dan closing remarks wajib diisi.")
                    elif status_new == "IN PROGRESS" and (not pic.strip() or not analysis.strip()):
                        st.error("Untuk status IN PROGRESS, PIC dan analisis penyebab wajib diisi.")
                    else:
                        res = bank_api("update_problem_ticket", Ticket_ID=selected, Status=status_new, PIC=pic, Analisa_Supervisor=analysis, Tindakan_Perbaikan=action_text, Closing_Remarks=closing)
                        if api_success(res):
                            st.success(res.get("message", "Tiket berhasil diperbarui.")); st.rerun()
                        else:
                            st.error(res.get("message", "Update tiket gagal."))
    except Exception as exc:
        st.error(f"Gagal memuat inbox tiket: {exc}")

elif menu == "Master Kategori Problem":
    page_heading("WAREHOUSE · CONFIGURATION", "Master Kategori Problem", "Kelola kategori agar klasifikasi dan analisis temuan tetap konsisten.")
    try:
        cats = load_problem_categories()
        st.dataframe(pd.DataFrame(cats), use_container_width=True, hide_index=True)
        with st.form("add_problem_category"):
            new_cat = st.text_input("Nama kategori baru", placeholder="Contoh: Material Preservation")
            add = st.form_submit_button("Tambah kategori", type="primary")
        if add:
            if not new_cat.strip():
                st.warning("Nama kategori wajib diisi.")
            else:
                res = bank_api("add_problem_category", category=new_cat.strip())
                if api_success(res): st.success(res.get("message", "Kategori ditambahkan.")); st.rerun()
                else: st.error(res.get("message", "Gagal menambah kategori."))
        active_names = [x["category"] for x in cats]
        if active_names:
            chosen = st.selectbox("Pilih kategori untuk mengubah status", active_names)
            active = st.toggle("Kategori aktif", value=next((str(x.get("active", "TRUE")).upper() not in ["FALSE", "0", "NO"] for x in cats if x["category"] == chosen), True))
            if st.button("Simpan status kategori", type="primary"):
                res = bank_api("set_problem_category", category=chosen, active=active)
                if api_success(res): st.success("Status kategori diperbarui."); st.rerun()
                else: st.error(res.get("message", "Gagal memperbarui kategori."))
    except Exception as exc:
        st.error(str(exc))

elif menu == "Problem Analysis":
    page_heading("WAREHOUSE · ANALYTICS", "Analisis Problem", "Identifikasi pola temuan untuk menentukan prioritas perbaikan inventory dan warehouse.")
    try:
        dfp = load_problem_tickets(False)
        if dfp.empty:
            st.info("Belum ada data untuk dianalisis.")
        else:
            left, right = st.columns(2)
            if "Kategori" in dfp:
                cat = dfp["Kategori"].fillna("Tidak dikategorikan").value_counts().rename_axis("Kategori").reset_index(name="Jumlah")
                left.plotly_chart(px.bar(cat, x="Kategori", y="Jumlah", color_discrete_sequence=["#2878b8"], title="Temuan berdasarkan kategori"), use_container_width=True)
            if "Status" in dfp:
                right.plotly_chart(px.pie(dfp, names="Status", hole=.55, title="Distribusi status tiket"), use_container_width=True)
            st.dataframe(dfp, use_container_width=True, hide_index=True)
    except Exception as exc:
        st.error(str(exc))

elif menu == "Branding & Tampilan":
    page_heading("SYSTEM · BRANDING", "Pengaturan Logo & Background", "Kelola identitas visual aplikasi melalui database Google Sheets. Gunakan URL gambar publik dari Google Drive atau server perusahaan.")
    try:
        current_assets = load_branding_assets()
        def current_asset(key):
            found = current_assets[current_assets["Asset_Key"].astype(str).str.upper() == key]
            return str(found.iloc[-1]["Asset_URL"]) if not found.empty else ""
        current_logo = current_asset("COMPANY_LOGO")
        current_bg = current_asset("APP_BACKGROUND")
        with st.form("branding_settings_form"):
            st.subheader("Identitas perusahaan")
            logo_input = st.text_input("URL Logo Perusahaan", value=current_logo, placeholder="https://...", help="Gunakan link gambar PNG/JPG yang dapat diakses publik.")
            bg_input = st.text_input("URL Background Aplikasi", value=current_bg, placeholder="https://...", help="Gunakan gambar landscape resolusi tinggi; sistem memberi lapisan putih transparan agar teks tetap terbaca.")
            save_branding = st.form_submit_button("SIMPAN BRANDING", type="primary", use_container_width=True)
        if current_logo:
            st.markdown("**Preview logo saat ini**")
            st.image(current_logo, width=180)
        if current_bg:
            st.markdown("**Preview background saat ini**")
            st.image(current_bg, use_container_width=True)
        if save_branding:
            for label, url in [("Logo", logo_input), ("Background", bg_input)]:
                if url.strip() and not url.strip().startswith(("https://", "http://")):
                    st.error(f"URL {label} harus diawali http:// atau https://")
                    st.stop()
            save_branding_assets(logo_input, bg_input)
            st.success("Pengaturan logo dan background berhasil disimpan ke database App_Assets.")
            st.rerun()
        st.info("Database yang digunakan: worksheet App_Assets. Kolom: Asset_Key, Asset_URL, Active, Updated_By, Updated_At. Upload gambar ke Google Drive, atur akses Viewer/Anyone with the link, lalu masukkan URL gambar langsung di atas.")
    except Exception as exc:
        st.error(f"Pengaturan branding gagal dimuat/disimpan: {exc}")

