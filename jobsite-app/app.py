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
        raise RuntimeError("Format respons Apps Script tidak sesuai; seharusnya objek JSON.")

    return result


def api_success(result):
    """Mendukung format respons backend result=success."""
    return str(result.get("result", "")).strip().lower() == "success"


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
st.sidebar.title("Jobsite Fleet System")
st.sidebar.info(f"Operator: {st.session_state.username}")

menu = st.sidebar.radio(
    "Navigasi Menu",
    [
        "Dashboard Overview",
        "Master Data Unit",
        "Upload / Update Master MSE600",
        "Form Mob / Demob",
        "Log Transaksi Permanen",
    ],
)

st.sidebar.markdown("---")

if st.sidebar.button("Refresh Data Real-Time"):
    st.cache_data.clear()
    st.rerun()

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()


# =========================================================
# 1. DASHBOARD OVERVIEW
# =========================================================
if menu == "Dashboard Overview":
    st.title("Dashboard Fleet & Operational Overview")
    st.markdown("---")

    if df_master.empty:
        st.warning(
            "Data Master MSE600 belum tersedia atau gagal dibaca. "
            "Periksa tab MSE600 dan konfigurasi Google Sheets."
        )
    else:
        status_code = df_master["Status_Code"].fillna("").astype(str).str.strip().str.upper()
        total_unit = len(df_master)
        available_unit = int(status_code.isin(["AV", "AVAILABLE"]).sum())
        off_hire_unit = int(status_code.isin(["OH", "OFF HIRE", "OFF-HIRE", "OFFHIRE"]).sum())
        other_unit = total_unit - available_unit - off_hire_unit

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Unit Jobsite", f"{total_unit:,} Unit")
        col2.metric("Available (AV)", f"{available_unit:,} Unit")
        col3.metric("Off Hire (OH)", f"{off_hire_unit:,} Unit")
        col4.metric("Status Lainnya", f"{other_unit:,} Unit")

        st.markdown("---")
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("Distribusi Status Unit")
            status_label = df_master["Status_Description"].replace("", "Tidak diketahui")
            if status_label.eq("Tidak diketahui").all():
                status_label = status_code.replace("", "Tidak diketahui")
            sc = status_label.value_counts().rename_axis("Status").reset_index(name="Jumlah")
            if not sc.empty:
                st.plotly_chart(
                    px.pie(sc, names="Status", values="Jumlah", hole=0.4),
                    use_container_width=True,
                )
            else:
                st.info("Belum ada data status untuk ditampilkan.")

        with c2:
            st.subheader("Top Sebaran Project / Lokasi")
            locations = df_master["Project_Location"].replace("", "Tidak diketahui")
            loc = locations.value_counts().head(10).rename_axis("Lokasi").reset_index(name="Jumlah")
            if not loc.empty:
                st.plotly_chart(
                    px.bar(loc, x="Jumlah", y="Lokasi", orientation="h"),
                    use_container_width=True,
                )
            else:
                st.info("Belum ada data lokasi untuk ditampilkan.")


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
    st.title("Input Mobilisasi & Demobilisasi")

    if df_master.empty:
        st.warning("Data Master belum tersedia. Upload file Excel MSE600 terlebih dahulu.")
    else:
        valid_master = df_master[df_master["Equipment_No"].str.strip() != ""].copy()
        valid_master = valid_master.reset_index(drop=True)

        if valid_master.empty:
            st.warning("Tidak ada Equipment Number yang valid di master data.")
        else:
            # Label hanya untuk tampilan; data unit diambil berdasarkan index pilihan.
            unit_labels = []
            for _, row in valid_master.iterrows():
                unit_no = row["Equipment_No"]
                unit_name = row["Equipment_Name"]
                unit_labels.append(f"{unit_no} - {unit_name}" if unit_name else unit_no)

            with st.form("form_mob", clear_on_submit=True):
                col1, col2 = st.columns(2)

                with col1:
                    selected_index = st.selectbox(
                        "Pilih Unit:",
                        options=list(range(len(unit_labels))),
                        format_func=lambda i: unit_labels[i],
                    )
                    aksi = st.selectbox(
                        "Jenis Aksi:",
                        ["MOBILISASI (MOB)", "DEMOBILISASI (DEMOB)"],
                    )
                    asal = st.text_input("Lokasi Asal:")

                with col2:
                    tgl = st.date_input("Tanggal:", value=datetime.today().date())
                    pic = st.text_input("PIC:", value=st.session_state.username)
                    tujuan = st.text_input("Lokasi Tujuan:")

                ket = st.text_area("Keterangan:")
                submitted = st.form_submit_button("Simpan Log Transaksi")

            if submitted:
                selected_unit = valid_master.iloc[selected_index]
                eq_no = selected_unit["Equipment_No"]
                eq_name = selected_unit["Equipment_Name"]

                if not asal.strip() or not tujuan.strip() or not pic.strip():
                    st.warning("Lokasi Asal, Lokasi Tujuan, dan PIC wajib diisi.")
                else:
                    payload = {
                        "action": "mob_demob",
                        "Request_ID": str(uuid.uuid4()),
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Tanggal_Transaksi": tgl.strftime("%Y-%m-%d"),
                        "Equipment_No": eq_no,
                        "Nama_Unit": eq_name,
                        "Jenis_Aksi": aksi,
                        "Lokasi_Asal": asal.strip(),
                        "Lokasi_Tujuan": tujuan.strip(),
                        "Keterangan": ket.strip(),
                        "PIC": pic.strip(),
                    }

                    try:
                        with st.spinner("Menyimpan transaksi..."):
                            result = post_to_webapp(payload)

                        if api_success(result):
                            st.success(
                                result.get(
                                    "message",
                                    f"Transaksi {aksi} untuk unit {eq_no} berhasil dicatat.",
                                )
                            )
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
