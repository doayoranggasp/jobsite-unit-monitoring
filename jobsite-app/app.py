
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime
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

st.markdown("""
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
""", unsafe_allow_html=True)

# =========================================================
# SESSION STATE
# =========================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""


# =========================================================
# API HELPERS
# =========================================================
def get_webapp_url():
    try:
        url = st.secrets["connections"]["gsheets"]["webapp_url"]
        if not url:
            raise ValueError("URL Apps Script kosong.")
        return str(url).strip()
    except Exception as e:
        raise RuntimeError(
            "Konfigurasi connections.gsheets.webapp_url "
            "tidak ditemukan di Streamlit Secrets."
        ) from e


def post_to_webapp(payload):
    try:
        response = requests.post(
            get_webapp_url(),
            json=payload,
            timeout=30,
        )
    except requests.RequestException as e:
        raise RuntimeError(
            f"Gagal menghubungi Google Apps Script: {e}"
        ) from e

    if not response.ok:
        raise RuntimeError(
            f"HTTP {response.status_code}: {response.text[:300]}"
        )

    try:
        result = response.json()
    except ValueError as e:
        raise RuntimeError(
            "Respons Apps Script bukan JSON yang valid: "
            + response.text[:300]
        ) from e

    if not isinstance(result, dict):
        raise RuntimeError("Format respons Apps Script tidak valid.")

    return result


def api_success(result):
    return str(result.get("result", "")).strip().lower() == "success"


def get_gsheets_connection():
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception as e:
        st.error(f"Koneksi Google Sheets gagal: {e}")
        return None


# =========================================================
# LOGIN & REGISTER
# =========================================================
if not st.session_state.logged_in:
    st.title("Login & Register - Jobsite Fleet System")
    st.write("Silakan masuk atau daftarkan akun baru.")

    tab_login, tab_register = st.tabs(["Login", "Register Akun Baru"])

    with tab_login:
        with st.form("form_login"):
            username = st.text_input("Username").strip()
            password = st.text_input("Password", type="password")
            submit_login = st.form_submit_button("Masuk ke Sistem")

        if submit_login:
            if not username or not password:
                st.warning("Username dan password wajib diisi.")
            else:
                try:
                    result = post_to_webapp({
                        "action": "login",
                        "username": username,
                        "password": password,
                    })

                    if api_success(result):
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.rerun()
                    else:
                        st.error(result.get("message", "Login gagal."))

                except Exception as e:
                    st.error(str(e))

    with tab_register:
        with st.form("form_register"):
            new_username = st.text_input("Username Baru").strip()
            new_password = st.text_input(
                "Password Baru", type="password"
            )
            confirm_password = st.text_input(
                "Ulangi Password", type="password"
            )
            submit_register = st.form_submit_button("Daftar Akun")

        if submit_register:
            if not new_username or not new_password or not confirm_password:
                st.warning("Semua kolom wajib diisi.")
            elif new_password != confirm_password:
                st.warning("Konfirmasi password tidak sama.")
            elif len(new_password) < 8:
                st.warning("Password minimal 8 karakter.")
            else:
                try:
                    result = post_to_webapp({
                        "action": "register",
                        "username": new_username,
                        "password": new_password,
                        "Timestamp": datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                    })

                    if api_success(result):
                        st.success(
                            "Pendaftaran berhasil. Silakan login."
                        )
                    else:
                        st.error(
                            result.get("message", "Pendaftaran gagal.")
                        )

                except Exception as e:
                    st.error(str(e))

    st.stop()


# =========================================================
# MASTER MSE600
# =========================================================
@st.cache_data(ttl=60, show_spinner="Memuat master MSE600...")
def load_master_from_cloud():
    columns = [
        "Equipment_No",
        "Equipment_Name",
        "Status_Code",
        "Status_Description",
        "Project_Location",
        "Serial_Number_Info",
    ]

    conn = st.connection("gsheets", type=GSheetsConnection)

    raw = conn.read(
        worksheet="MSE600",
        ttl=0,
        header=None,
    )

    if raw is None or raw.empty:
        return pd.DataFrame(columns=columns)

    raw = raw.fillna("").astype(str)
    raw = raw.apply(lambda col: col.str.strip())

    # Cari baris header.
    header_row = None
    for i in range(min(len(raw), 40)):
        values = [
            " ".join(str(v).lower().replace("_", " ").split())
            for v in raw.iloc[i].tolist()
        ]

        if any(
            v in ["equipment no", "equipment number", "equip no"]
            for v in values
        ):
            header_row = i
            break

    if header_row is None:
        raise ValueError(
            "Header Equipment No tidak ditemukan pada "
            "40 baris pertama tab MSE600."
        )

    headers = [
        " ".join(str(v).lower().replace("_", " ").split())
        for v in raw.iloc[header_row].tolist()
    ]

    data = raw.iloc[header_row + 1:].reset_index(drop=True)

    aliases = {
        "Equipment_No": [
            "equipment no", "equipment number", "equip no"
        ],
        "Equipment_Name": [
            "equipment name", "equip name", "unit name"
        ],
        "Status_Code": [
            "status code", "equipment status code"
        ],
        "Status_Description": [
            "status description", "status desc"
        ],
        "Project_Location": [
            "project location", "location", "project"
        ],
        "Serial_Number_Info": [
            "serial number", "serial no", "serial number info"
        ],
    }

    # Fallback berdasarkan struktur kolom script awal.
    fallback = {
        "Equipment_No": 0,
        "Equipment_Name": 2 if raw.shape[1] > 2 else 1,
        "Status_Code": 3,
        "Status_Description": 4,
        "Project_Location": 8 if raw.shape[1] > 8 else 5,
        "Serial_Number_Info": 11 if raw.shape[1] > 11 else 6,
    }

    result = {}

    for field, possible_names in aliases.items():
        index = next(
            (
                j for j, header in enumerate(headers)
                if header in possible_names
            ),
            fallback[field],
        )

        if index < data.shape[1]:
            result[field] = (
                data.iloc[:, index]
                .fillna("")
                .astype(str)
                .replace({"nan": "", "None": ""})
                .str.strip()
            )
        else:
            result[field] = pd.Series(
                [""] * len(data), dtype="object"
            )

    df = pd.DataFrame(result)

    invalid = df["Equipment_No"].str.lower().isin([
        "", "nan", "none", "equipment no",
        "equipment number", "equip no"
    ])

    df = df.loc[~invalid].copy()

    return df.reset_index(drop=True)


# Jangan biarkan kegagalan master menghentikan seluruh aplikasi.
try:
    df_master = load_master_from_cloud()
    master_error = None
except Exception as e:
    df_master = pd.DataFrame(columns=[
        "Equipment_No", "Equipment_Name", "Status_Code",
        "Status_Description", "Project_Location",
        "Serial_Number_Info",
    ])
    master_error = f"{type(e).__name__}: {e}"


# =========================================================
# SIDEBAR NAVIGATION
# =========================================================
st.sidebar.title("Jobsite Fleet System")
st.sidebar.info(f"Operator: {st.session_state.username}")

if master_error:
    st.sidebar.error("Master MSE600 gagal dimuat.")
else:
    st.sidebar.success(f"Master MSE600: {len(df_master)} unit")

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

    if master_error:
        st.error(f"Gagal membaca master MSE600: {master_error}")
        st.info(
            "Periksa nama tab MSE600, konfigurasi koneksi, "
            "dan header kolom pada Google Sheets."
        )

    elif df_master.empty:
        st.warning("Data master MSE600 kosong.")

    else:
        status_code = (
            df_master["Status_Code"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )

        total = len(df_master)
        available = int((status_code == "AV").sum())
        off_hire = int((status_code == "OH").sum())
        other = total - available - off_hire

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Unit Jobsite", f"{total:,} Unit")
        c2.metric("Available (AV)", f"{available:,} Unit")
        c3.metric("Off Hire (OH)", f"{off_hire:,} Unit")
        c4.metric("Status Lainnya", f"{other:,} Unit")

        left, right = st.columns(2)

        with left:
            st.subheader("Distribusi Status Unit")
            labels = df_master["Status_Description"].replace(
                "", "Tidak diketahui"
            )
            if labels.eq("Tidak diketahui").all():
                labels = status_code.replace("", "Tidak diketahui")

            chart_data = labels.value_counts().rename_axis(
                "Status"
            ).reset_index(name="Jumlah")

            st.plotly_chart(
                px.pie(
                    chart_data,
                    names="Status",
                    values="Jumlah",
                    hole=0.4,
                ),
                use_container_width=True,
            )

        with right:
            st.subheader("Top Sebaran Project / Lokasi")
            locations = df_master["Project_Location"].replace(
                "", "Tidak diketahui"
            )
            chart_data = locations.value_counts().head(10).rename_axis(
                "Lokasi"
            ).reset_index(name="Jumlah")

            st.plotly_chart(
                px.bar(
                    chart_data,
                    x="Jumlah",
                    y="Lokasi",
                    orientation="h",
                ),
                use_container_width=True,
            )


# =========================================================
# 2. MASTER DATA UNIT
# =========================================================
elif menu == "Master Data Unit":
    st.title("Master Data Equipment")

    if master_error:
        st.error(f"Gagal membaca master MSE600: {master_error}")
    elif df_master.empty:
        st.warning("Data master belum tersedia.")
    else:
        search = st.text_input(
            "Cari Unit No / Nama / Serial Number:"
        )

        filtered = df_master.copy()

        if search.strip():
            keyword = search.strip()
            mask = pd.Series(False, index=filtered.index)

            for col in [
                "Equipment_No",
                "Equipment_Name",
                "Serial_Number_Info",
            ]:
                mask |= (
                    filtered[col]
                    .fillna("")
                    .astype(str)
                    .str.contains(
                        keyword,
                        case=False,
                        regex=False,
                        na=False,
                    )
                )

            filtered = filtered.loc[mask]

        st.caption(
            f"Menampilkan {len(filtered):,} dari {len(df_master):,} unit."
        )
        st.dataframe(
            filtered,
            use_container_width=True,
            height=450,
            hide_index=True,
        )


# =========================================================
# 3. UPLOAD / UPDATE MASTER MSE600
# =========================================================
elif menu == "Upload / Update Master MSE600":
    st.title("Upload & Perbarui Master Data MSE600")

    uploaded_file = st.file_uploader(
        "Pilih file Excel MSE600",
        type=["xlsx", "xls"],
    )

    if uploaded_file is not None:
        try:
            preview_df = pd.read_excel(
                uploaded_file,
                header=None,
            )

            st.caption(
                f"Preview: {len(preview_df)} baris × "
                f"{len(preview_df.columns)} kolom"
            )
            st.dataframe(
                preview_df.head(10),
                use_container_width=True,
            )

            if st.button(
                "Simpan Master ke Cloud Permanen",
                type="primary",
            ):
                payload = {
                    "action": "upload_master",
                    "rows": preview_df.fillna("").astype(str).values.tolist(),
                }

                with st.spinner("Menyimpan master ke Google Sheets..."):
                    result = post_to_webapp(payload)

                if api_success(result):
                    st.success(
                        result.get(
                            "message",
                            "Master berhasil disimpan."
                        )
                    )
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(
                        result.get(
                            "message",
                            "Apps Script menolak penyimpanan."
                        )
                    )

        except Exception as e:
            st.error(f"Gagal membaca atau mengirim file: {e}")

    st.divider()

    if st.checkbox("Debug: Lihat Data Mentah di Cloud"):
        conn = get_gsheets_connection()

        if conn is not None:
            try:
                raw = conn.read(
                    worksheet="MSE600",
                    ttl=0,
                    header=None,
                )
                st.write(f"Total baris: {len(raw)}")
                st.dataframe(raw.head(20), use_container_width=True)
            except Exception as e:
                st.error(f"Gagal membaca MSE600: {e}")


# =========================================================
# 4. FORM MOB / DEMOB
# =========================================================
elif menu == "Form Mob / Demob":
    st.title("Input Mobilisasi & Demobilisasi")

    if master_error:
        st.error(f"Master unit gagal dimuat: {master_error}")

    elif df_master.empty:
        st.warning("Upload atau periksa master MSE600 terlebih dahulu.")

    else:
        valid_master = df_master[
            df_master["Equipment_No"].fillna("").astype(str).str.strip() != ""
        ].reset_index(drop=True)

        if valid_master.empty:
            st.warning("Tidak ada Equipment Number yang valid.")
        else:
            labels = []
            for _, row in valid_master.iterrows():
                number = row["Equipment_No"]
                name = row["Equipment_Name"]
                labels.append(f"{number} - {name}" if name else number)

            with st.form("form_mob", clear_on_submit=True):
                col1, col2 = st.columns(2)

                with col1:
                    selected_index = st.selectbox(
                        "Pilih Unit",
                        options=list(range(len(labels))),
                        format_func=lambda i: labels[i],
                    )
                    action = st.selectbox(
                        "Jenis Aksi",
                        [
                            "MOBILISASI (MOB)",
                            "DEMOBILISASI (DEMOB)",
                        ],
                    )
                    origin = st.text_input("Lokasi Asal")

                with col2:
                    date = st.date_input(
                        "Tanggal",
                        value=datetime.today().date(),
                    )
                    pic = st.text_input(
                        "PIC",
                        value=st.session_state.username,
                    )
                    destination = st.text_input("Lokasi Tujuan")

                notes = st.text_area("Keterangan")
                submitted = st.form_submit_button("Simpan Log Transaksi")

            if submitted:
                unit = valid_master.iloc[selected_index]

                if not origin.strip() or not destination.strip() or not pic.strip():
                    st.warning(
                        "Lokasi Asal, Lokasi Tujuan, dan PIC wajib diisi."
                    )
                else:
                    payload = {
                        "action": "mob_demob",
                        "Timestamp": datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "Tanggal_Transaksi": date.strftime("%Y-%m-%d"),
                        "Equipment_No": unit["Equipment_No"],
                        "Nama_Unit": unit["Equipment_Name"],
                        "Jenis_Aksi": action,
                        "Lokasi_Asal": origin.strip(),
                        "Lokasi_Tujuan": destination.strip(),
                        "Keterangan": notes.strip(),
                        "PIC": pic.strip(),
                    }

                    try:
                        with st.spinner("Menyimpan transaksi..."):
                            result = post_to_webapp(payload)

                        if api_success(result):
                            st.success(
                                result.get(
                                    "message",
                                    "Transaksi berhasil dicatat."
                                )
                            )
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(
                                result.get(
                                    "message",
                                    "Transaksi gagal disimpan."
                                )
                            )

                    except Exception as e:
                        st.error(f"Gagal menyimpan transaksi: {e}")


# =========================================================
# 5. LOG TRANSAKSI PERMANEN
# =========================================================
elif menu == "Log Transaksi Permanen":
    st.title("Log Transaksi Real-Time")

    conn = get_gsheets_connection()

    if conn is not None:
        try:
            db_data = conn.read(
                worksheet="Log_Trans",
                ttl=0,
            )

            if db_data is None or db_data.empty:
                st.info("Belum ada transaksi pada tab Log_Trans.")
            else:
                st.caption(f"Total transaksi: {len(db_data):,}")
                st.dataframe(
                    db_data,
                    use_container_width=True,
                    hide_index=True,
                )

                csv_data = db_data.to_csv(
                    index=False
                ).encode("utf-8-sig")

                st.download_button(
                    "Export CSV",
                    data=csv_data,
                    file_name="log_mob_demob.csv",
                    mime="text/csv",
                )

        except Exception as e:
            st.error(
                f"Gagal membaca tab Log_Trans: {type(e).__name__}: {e}"
            )
