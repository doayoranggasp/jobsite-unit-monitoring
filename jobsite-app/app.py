
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
from io import BytesIO

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

EXCEL_ENGINES = {
    "xlsx": "openpyxl",
    "xlsm": "openpyxl",
    "xls": "xlrd",
    "xlsb": "pyxlsb",
}

MASTER_COLUMNS = [
    "Equipment_No",
    "Equipment_Name",
    "Status_Code",
    "Status_Description",
    "Project_Location",
    "Serial_Number_Info",
]

# =========================================================
# SESSION STATE
# =========================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""


# =========================================================
# GOOGLE APPS SCRIPT API
# =========================================================
def get_webapp_url():
    try:
        url = st.secrets["connections"]["gsheets"]["webapp_url"]
        if not str(url).strip():
            raise ValueError("URL Apps Script kosong.")
        return str(url).strip()
    except Exception as exc:
        raise RuntimeError(
            "Secret connections.gsheets.webapp_url tidak ditemukan."
        ) from exc


def post_to_webapp(payload):
    try:
        response = requests.post(
            get_webapp_url(),
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Gagal menghubungi Apps Script: {exc}"
        ) from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "Respons Apps Script bukan JSON: "
            + response.text[:300]
        ) from exc

    if not isinstance(result, dict):
        raise RuntimeError("Format respons Apps Script tidak valid.")

    return result


def api_success(result):
    # Mendukung beberapa format respons Apps Script umum.
    status = str(
        result.get("result", result.get("status", ""))
    ).strip().lower()

    return (
        status in ("success", "ok", "true")
        or result.get("success") is True
    )


def get_gsheets_connection():
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception as exc:
        st.error(f"Koneksi Google Sheets gagal: {exc}")
        return None


# =========================================================
# EXCEL READER - XLS, XLSX, XLSM, XLSB
# =========================================================
def read_excel_file(uploaded_file):
    filename = uploaded_file.name.lower()

    if "." not in filename:
        raise ValueError("File tidak memiliki ekstensi.")

    extension = filename.rsplit(".", 1)[-1]

    if extension not in EXCEL_ENGINES:
        raise ValueError(
            "Format tidak didukung. Gunakan XLS, XLSX, XLSM, atau XLSB."
        )

    engine = EXCEL_ENGINES[extension]

    try:
        file_bytes = uploaded_file.getvalue()

        if not file_bytes:
            raise ValueError("File Excel kosong.")

        return pd.read_excel(
            BytesIO(file_bytes),
            header=None,
            engine=engine,
        )

    except ImportError as exc:
        raise RuntimeError(
            f"Library untuk format .{extension} belum terpasang. "
            "Periksa requirements.txt."
        ) from exc

    except Exception as exc:
        raise RuntimeError(
            f"Gagal membaca file .{extension}: {exc}"
        ) from exc


# =========================================================
# LOGIN & REGISTER
# =========================================================
if not st.session_state.logged_in:
    st.title("Jobsite Fleet Management System")
    st.write("Silakan login atau daftarkan akun baru.")

    tab_login, tab_register = st.tabs([
        "Login",
        "Register Akun Baru",
    ])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username").strip()
            password = st.text_input(
                "Password",
                type="password",
            )
            login_submit = st.form_submit_button("Login")

        if login_submit:
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
                        st.error(
                            result.get("message", "Login gagal.")
                        )
                except Exception as exc:
                    st.error(str(exc))

    with tab_register:
        with st.form("register_form"):
            new_username = st.text_input("Username Baru").strip()
            new_password = st.text_input(
                "Password Baru",
                type="password",
            )
            confirm_password = st.text_input(
                "Konfirmasi Password",
                type="password",
            )
            register_submit = st.form_submit_button("Daftar")

        if register_submit:
            if not new_username or not new_password:
                st.warning("Username dan password wajib diisi.")
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
                            "Registrasi berhasil. Silakan login."
                        )
                    else:
                        st.error(
                            result.get(
                                "message",
                                "Registrasi gagal."
                            )
                        )
                except Exception as exc:
                    st.error(str(exc))

    st.stop()


# =========================================================
# LOAD MASTER MSE600
# =========================================================
@st.cache_data(ttl=60, show_spinner="Memuat master MSE600...")
def load_master_from_cloud():
    conn = st.connection("gsheets", type=GSheetsConnection)

    raw = conn.read(
        worksheet="MSE600",
        ttl=0,
        header=None,
    )

    if raw is None or raw.empty:
        return pd.DataFrame(columns=MASTER_COLUMNS)

    raw = raw.fillna("").astype(str)
    raw = raw.apply(lambda col: col.str.strip())

    # Cari baris header dalam 40 baris pertama.
    header_row = None

    equipment_aliases = {
        "equipment no",
        "equipment number",
        "equip no",
        "equipment_no",
    }

    for i in range(min(len(raw), 40)):
        row_values = {
            " ".join(
                str(value).lower().replace("_", " ").split()
            )
            for value in raw.iloc[i].tolist()
        }

        if row_values.intersection(equipment_aliases):
            header_row = i
            break

    if header_row is None:
        raise ValueError(
            "Header Equipment No tidak ditemukan pada 40 baris "
            "pertama worksheet MSE600."
        )

    headers = [
        " ".join(
            str(value).lower().replace("_", " ").split()
        )
        for value in raw.iloc[header_row].tolist()
    ]

    data = raw.iloc[header_row + 1:].reset_index(drop=True)

    aliases = {
        "Equipment_No": [
            "equipment no",
            "equipment number",
            "equip no",
        ],
        "Equipment_Name": [
            "equipment name",
            "equip name",
            "unit name",
        ],
        "Status_Code": [
            "status code",
            "equipment status code",
        ],
        "Status_Description": [
            "status description",
            "status desc",
        ],
        "Project_Location": [
            "project location",
            "location",
            "project",
        ],
        "Serial_Number_Info": [
            "serial number",
            "serial no",
            "serial number info",
        ],
    }

    # Posisi fallback mengikuti struktur script awal.
    fallback = {
        "Equipment_No": 0,
        "Equipment_Name": 2 if raw.shape[1] > 2 else 1,
        "Status_Code": 3,
        "Status_Description": 4,
        "Project_Location": 8 if raw.shape[1] > 8 else 5,
        "Serial_Number_Info": 11 if raw.shape[1] > 11 else 6,
    }

    output = {}

    for field, possible_headers in aliases.items():
        matched_index = next(
            (
                index
                for index, header in enumerate(headers)
                if header in possible_headers
            ),
            None,
        )

        index = (
            matched_index
            if matched_index is not None
            else fallback[field]
        )

        if index < data.shape[1]:
            output[field] = (
                data.iloc[:, index]
                .fillna("")
                .astype(str)
                .replace({"nan": "", "None": ""})
                .str.strip()
            )
        else:
            output[field] = pd.Series(
                [""] * len(data),
                dtype="object",
            )

    df = pd.DataFrame(output)

    invalid = df["Equipment_No"].str.lower().isin([
        "",
        "nan",
        "none",
        "equipment no",
        "equipment number",
        "equip no",
    ])

    return df.loc[~invalid].reset_index(drop=True)


try:
    df_master = load_master_from_cloud()
    master_error = None
except Exception as exc:
    df_master = pd.DataFrame(columns=MASTER_COLUMNS)
    master_error = f"{type(exc).__name__}: {exc}"


# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.title("Jobsite Fleet System")
st.sidebar.write(f"User: {st.session_state.username}")

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

if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()


# =========================================================
# DASHBOARD
# =========================================================
if menu == "Dashboard Overview":
    st.title("Dashboard Fleet Overview")

    if master_error:
        st.error(f"Gagal membaca master: {master_error}")

    elif df_master.empty:
        st.warning("Data master MSE600 kosong.")

    else:
        status = (
            df_master["Status_Code"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )

        total = len(df_master)
        available = int((status == "AV").sum())
        off_hire = int((status == "OH").sum())
        other = total - available - off_hire

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Unit", f"{total:,}")
        c2.metric("Available (AV)", f"{available:,}")
        c3.metric("Off Hire (OH)", f"{off_hire:,}")
        c4.metric("Status Lainnya", f"{other:,}")

        left, right = st.columns(2)

        with left:
            st.subheader("Distribusi Status")

            descriptions = (
                df_master["Status_Description"]
                .replace("", "Tidak diketahui")
            )

            if descriptions.eq("Tidak diketahui").all():
                descriptions = status.replace("", "Tidak diketahui")

            chart_data = (
                descriptions.value_counts()
                .rename_axis("Status")
                .reset_index(name="Jumlah")
            )

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
            st.subheader("Distribusi Lokasi")

            locations = (
                df_master["Project_Location"]
                .replace("", "Tidak diketahui")
            )

            chart_data = (
                locations.value_counts()
                .head(10)
                .rename_axis("Lokasi")
                .reset_index(name="Jumlah")
            )

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
# MASTER DATA UNIT
# =========================================================
elif menu == "Master Data Unit":
    st.title("Master Data Unit")

    if master_error:
        st.error(master_error)

    elif df_master.empty:
        st.warning("Data master belum tersedia.")

    else:
        search = st.text_input(
            "Cari Unit No / Nama / Serial Number"
        )

        filtered = df_master.copy()

        if search.strip():
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
                        search.strip(),
                        case=False,
                        regex=False,
                        na=False,
                    )
                )

            filtered = filtered.loc[mask]

        st.caption(f"Jumlah unit ditemukan: {len(filtered):,}")

        st.dataframe(
            filtered,
            use_container_width=True,
            height=450,
            hide_index=True,
        )


# =========================================================
# UPLOAD MASTER MSE600 - ALL EXCEL FORMATS
# =========================================================
elif menu == "Upload / Update Master MSE600":
    st.title("Upload / Update Master MSE600")

    st.info(
        "Format yang didukung: XLS, XLSX, XLSM, dan XLSB."
    )

    uploaded_file = st.file_uploader(
        "Pilih file Excel MSE600",
        type=["xls", "xlsx", "xlsm", "xlsb"],
        accept_multiple_files=False,
    )

    if uploaded_file is not None:
        try:
            preview_df = read_excel_file(uploaded_file)

            if preview_df.empty:
                st.warning("File Excel tidak berisi data.")
            else:
                st.success(
                    f"File berhasil dibaca: {uploaded_file.name}"
                )
                st.caption(
                    f"{len(preview_df):,} baris × "
                    f"{len(preview_df.columns):,} kolom"
                )

                st.dataframe(
                    preview_df.head(20),
                    use_container_width=True,
                )

                if st.button(
                    "Simpan Master ke Cloud Permanen",
                    type="primary",
                ):
                    # Perhatikan batas ukuran payload Apps Script.
                    payload = {
                        "action": "upload_master",
                        "rows": (
                            preview_df
                            .fillna("")
                            .astype(str)
                            .values
                            .tolist()
                        ),
                    }

                    try:
                        with st.spinner(
                            "Mengirim data ke Google Sheets..."
                        ):
                            result = post_to_webapp(payload)

                        if api_success(result):
                            st.success(
                                result.get(
                                    "message",
                                    "Master berhasil dikirim."
                                )
                            )
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(
                                result.get(
                                    "message",
                                    "Apps Script melaporkan kegagalan."
                                )
                            )

                    except Exception as exc:
                        st.error(
                            f"Gagal menyimpan master: {exc}"
                        )

        except Exception as exc:
            st.error(str(exc))

    st.divider()

    with st.expander("Debug: Lihat data mentah MSE600"):
        conn = get_gsheets_connection()

        if conn is not None:
            try:
                raw = conn.read(
                    worksheet="MSE600",
                    ttl=0,
                    header=None,
                )
                st.write(f"Jumlah baris: {len(raw)}")
                st.dataframe(
                    raw.head(20),
                    use_container_width=True,
                )
            except Exception as exc:
                st.error(str(exc))


# =========================================================
# MOB / DEMOB FORM
# =========================================================
elif menu == "Form Mob / Demob":
    st.title("Form Mobilisasi / Demobilisasi")

    if master_error:
        st.error(f"Master unit gagal dimuat: {master_error}")

    elif df_master.empty:
        st.warning("Data master MSE600 belum tersedia.")

    else:
        valid_master = df_master[
            df_master["Equipment_No"]
            .fillna("")
            .astype(str)
            .str.strip()
            .ne("")
        ].reset_index(drop=True)

        if valid_master.empty:
            st.warning("Tidak ada unit valid dalam master.")
        else:
            labels = []

            for _, row in valid_master.iterrows():
                number = row["Equipment_No"]
                name = row["Equipment_Name"]
                labels.append(
                    f"{number} - {name}" if name else number
                )

            with st.form("mob_demob_form", clear_on_submit=True):
                col1, col2 = st.columns(2)

                with col1:
                    selected_index = st.selectbox(
                        "Pilih Unit",
                        options=list(range(len(labels))),
                        format_func=lambda index: labels[index],
                    )

                    action = st.selectbox(
                        "Jenis Transaksi",
                        [
                            "MOBILISASI (MOB)",
                            "DEMOBILISASI (DEMOB)",
                        ],
                    )

                    origin = st.text_input("Lokasi Asal")

                with col2:
                    transaction_date = st.date_input(
                        "Tanggal Transaksi",
                        value=datetime.today().date(),
                    )

                    pic = st.text_input(
                        "PIC",
                        value=st.session_state.username,
                    )

                    destination = st.text_input("Lokasi Tujuan")

                notes = st.text_area("Keterangan")
                submit_transaction = st.form_submit_button(
                    "Simpan Transaksi"
                )

            if submit_transaction:
                unit = valid_master.iloc[selected_index]

                if (
                    not origin.strip()
                    or not destination.strip()
                    or not pic.strip()
                ):
                    st.warning(
                        "Lokasi asal, lokasi tujuan, dan PIC wajib diisi."
                    )

                else:
                    payload = {
                        "action": "mob_demob",
                        "Timestamp": datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "Tanggal_Transaksi": (
                            transaction_date.strftime("%Y-%m-%d")
                        ),
                        "Equipment_No": unit["Equipment_No"],
                        "Nama_Unit": unit["Equipment_Name"],
                        "Jenis_Aksi": action,
                        "Lokasi_Asal": origin.strip(),
                        "Lokasi_Tujuan": destination.strip(),
                        "Keterangan": notes.strip(),
                        "PIC": pic.strip(),
                    }

                    try:
                        with st.spinner(
                            "Menyimpan transaksi..."
                        ):
                            result = post_to_webapp(payload)

                        if api_success(result):
                            st.success(
                                result.get(
                                    "message",
                                    "Transaksi berhasil disimpan."
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

                    except Exception as exc:
                        st.error(
                            f"Gagal menyimpan transaksi: {exc}"
                        )


# =========================================================
# LOG TRANSAKSI PERMANEN
# =========================================================
elif menu == "Log Transaksi Permanen":
    st.title("Log Transaksi Permanen")

    conn = get_gsheets_connection()

    if conn is not None:
        try:
            log_df = conn.read(
                worksheet="Log_Trans",
                ttl=0,
            )

            if log_df is None or log_df.empty:
                st.info(
                    "Belum ada transaksi di worksheet Log_Trans."
                )
            else:
                st.caption(
                    f"Total transaksi: {len(log_df):,}"
                )

                st.dataframe(
                    log_df,
                    use_container_width=True,
                    hide_index=True,
                )

                st.download_button(
                    "Download Log CSV",
                    data=log_df.to_csv(
                        index=False
                    ).encode("utf-8-sig"),
                    file_name="log_transaksi_mob_demob.csv",
                    mime="text/csv",
                )

        except Exception as exc:
            st.error(
                f"Gagal membaca Log_Trans: "
                f"{type(exc).__name__}: {exc}"
            )
