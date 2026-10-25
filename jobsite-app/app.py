import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(
    page_title="Jobsite Fleet Management System",
    page_icon="🚜",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button {
        width: 100%;
        background-color: #007bff;
        color: white;
        border-radius: 8px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# Session State Inisialisasi
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

def get_gsheets_connection():
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except:
        return None

# ==========================================
# HALAMAN LOGIN & REGISTER
# ==========================================
if not st.session_state.logged_in:
    st.title("Login & Register - Jobsite Fleet System")
    st.markdown("Silakan masuk menggunakan akun terdaftar atau buat akun baru.")
    
    tab_login, tab_reg = st.tabs(["Login", "Register Akun Baru"])
    
    with tab_login:
        with st.form("form_login"):
            l_user = st.text_input("Username")
            l_pass = st.text_input("Password", type="password")
            btn_login = st.form_submit_button("Masuk ke Sistem")
            
            if btn_login:
                if not l_user or not l_pass:
                    st.warning("Username dan Password wajib diisi!")
                else:
                    try:
                        webapp_url = st.secrets["connections"]["gsheets"]["webapp_url"]
                        res = requests.post(webapp_url, json={"action": "login", "username": l_user, "password": l_pass})
                        res_json = res.json()
                        if res_json.get("result") == "success":
                            st.session_state.logged_in = True
                            st.session_state.username = l_user.strip()
                            st.success("Login Berhasil!")
                            st.rerun()
                        else:
                            st.error(res_json.get("message", "Login gagal."))
                    except Exception as e:
                        st.error(f"Error koneksi: {e}")

    with tab_reg:
        with st.form("form_reg"):
            r_user = st.text_input("Username Baru")
            r_pass = st.text_input("Password Baru", type="password")
            btn_reg = st.form_submit_button("Daftar Akun")
            
            if btn_reg:
                if not r_user or not r_pass:
                    st.warning("Semua kolom wajib diisi!")
                else:
                    try:
                        webapp_url = st.secrets["connections"]["gsheets"]["webapp_url"]
                        payload = {
                            "action": "register",
                            "username": r_user,
                            "password": str(r_pass),
                            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        res = requests.post(webapp_url, json=payload)
                        res_json = res.json()
                        if res_json.get("result") == "success":
                            st.success("Pendaftaran berhasil! Silakan pindah ke tab Login.")
                        else:
                            st.warning(res_json.get("message", "Gagal mendaftar."))
                    except Exception as e:
                        st.error(f"Error koneksi: {e}")
    st.stop()

# ==========================================
# PARSER MASTER CERDAS & OTOMATIS
# ==========================================
@st.cache_data
def load_master_from_cloud():
    conn = get_gsheets_connection()
    if not conn:
        return pd.DataFrame()
    try:
        df_raw = conn.read(worksheet="MSE600", ttl=0, header=None)
        if df_raw.empty or len(df_raw) < 1:
            return pd.DataFrame()
        
        # Cari baris yang berisi header tabel secara otomatis
        header_row = 0
        for i in range(len(df_raw)):
            row_text = " ".join(df_raw.iloc[i].astype(str).values).lower()
            if "equip" in row_text or "unit" in row_text or "no" in row_text:
                header_row = i
                break
        
        # Ambil data setelah baris header
        df_cleaned = df_raw.iloc[header_row + 1:].copy().reset_index(drop=True)
        if df_cleaned.empty:
            return pd.DataFrame()
            
        ncols = df_cleaned.shape[1]
        
        def get_col(idx):
            if ncols > idx:
                return df_cleaned.iloc[:, idx].astype(str).str.strip()
            return pd.Series([""] * len(df_cleaned))
        
        result_df = pd.DataFrame({
            'Equipment_No': get_col(0),
            'Equipment_Name': get_col(2) if ncols > 2 else get_col(1),
            'Status_Code': get_col(3),
            'Status_Description': get_col(4),
            'Project_Location': get_col(8) if ncols > 8 else get_col(5),
            'Serial_Number_Info': get_col(11) if ncols > 11 else get_col(6)
        })
        
        # Bersihkan baris kosong atau teks header yang ikut terbawa
        result_df = result_df[
            (result_df['Equipment_No'] != '') & 
            (result_df['Equipment_No'].str.lower() != 'nan') & 
            (result_df['Equipment_No'].str.lower() != 'none') &
            (~result_df['Equipment_No'].str.lower().str.contains('equipment|equip|no|unit'))
        ]
        return result_df
    except Exception as e:
        return pd.DataFrame()

df_master = load_master_from_cloud()

# ==========================================
# SIDEBAR NAVIGATION
# ==========================================
st.sidebar.title("Jobsite Fleet System")
st.sidebar.info(f"Operator: {st.session_state.username}")

menu = st.sidebar.radio(
    "Navigasi Menu",
    [
        "Dashboard Overview", 
        "Master Data Unit", 
        "Upload / Update Master MSE600", 
        "Form Mob / Demob", 
        "Log Transaksi Permanen"
    ]
)

st.sidebar.markdown("---")
if st.sidebar.button("Refresh Data Real-Time"):
    st.cache_data.clear()
    st.rerun()

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

# ------------------------------------------
# 1. DASHBOARD OVERVIEW
# ------------------------------------------
if menu == "Dashboard Overview":
    st.title("Dashboard Fleet & Operational Overview")
    st.markdown("---")

    if df_master.empty:
        st.warning("Belum ada Data Master MSE600 atau format kolom belum terbaca. Silakan upload ulang file Excel Anda melalui menu **Upload / Update Master MSE600** di sidebar.")
    else:
        total_unit = len(df_master)
        available_unit = len(df_master[df_master['Status_Code'].str.upper() == 'AV'])
        off_hire_unit = len(df_master[df_master['Status_Code'].str.upper() == 'OH'])
        other_unit = total_unit - (available_unit + off_hire_unit)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Unit Jobsite", f"{total_unit} Unit")
        col2.metric("Available (AV)", f"{available_unit} Unit")
        col3.metric("Off Hire (OH)", f"{off_hire_unit} Unit")
        col4.metric("Status Lainnya", f"{other_unit} Unit")

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Distribusi Status Unit")
            sc = df_master['Status_Description'].value_counts().reset_index()
            sc.columns = ['Status', 'Jumlah']
            st.plotly_chart(px.pie(sc, names='Status', values='Jumlah', hole=0.4), use_container_width=True)
        with c2:
            st.subheader("Top Sebaran Project / Lokasi")
            loc = df_master['Project_Location'].value_counts().head(10).reset_index()
            loc.columns = ['Lokasi', 'Jumlah']
            st.plotly_chart(px.bar(loc, x='Jumlah', y='Lokasi', orientation='h'), use_container_width=True)

# ------------------------------------------
# 2. MASTER DATA UNIT
# ------------------------------------------
elif menu == "Master Data Unit":
    st.title("Master Data Equipment (Live)")
    if df_master.empty:
        st.warning("Data Master belum tersedia. Silakan upload file Excel MSE600.")
    else:
        search = st.text_input("Cari Unit No / Nama / Serial Number:")
        filtered = df_master
        if search:
            filtered = df_master[
                df_master['Equipment_No'].str.contains(search, case=False) |
                df_master['Equipment_Name'].str.contains(search, case=False) |
                df_master['Serial_Number_Info'].str.contains(search, case=False)
            ]
        st.dataframe(filtered, use_container_width=True, height=450)

# ------------------------------------------
# 3. UPLOAD / UPDATE MASTER MSE600
# ------------------------------------------
elif menu == "Upload / Update Master MSE600":
    st.title("Upload & Perbarui Master Data MSE600")
    uploaded_file = st.file_uploader("Pilih file Excel MSE600 (.xlsx)", type=["xlsx", "xls"])
    
    if uploaded_file is not None:
        if st.button("Simpan Master ke Cloud Permanen"):
            try:
                df_raw_upload = pd.read_excel(uploaded_file, header=None)
                payload = {
                    "action": "upload_master",
                    "rows": df_raw_upload.fillna("").values.tolist()
                }
                res = requests.post(st.secrets["connections"]["gsheets"]["webapp_url"], json=payload)
                if res.status_code == 200:
                    st.success("Master MSE600 berhasil disimpan permanen ke Google Sheets!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Gagal menyimpan ke cloud.")
            except Exception as e:
                st.error(f"Error: {e}")
                
    st.markdown("---")
    if st.checkbox("🔍 Debug Lihat Data Mentah di Cloud"):
        conn = get_gsheets_connection()
        if conn:
            try:
                raw = conn.read(worksheet="MSE600", ttl=0, header=None)
                st.write(f"Total Baris di Tab MSE600: {len(raw)}")
                st.dataframe(raw.head(10), use_container_width=True)
            except Exception as e:
                st.error(f"Gagal baca: {e}")

# ------------------------------------------
# 4. FORM MOB / DEMOB
# ------------------------------------------
elif menu == "Form Mob / Demob":
    st.title("Input Mobilisasi & Demobilisasi")
    if df_master.empty:
        st.warning("Data Master belum tersedia. Upload file Excel MSE600 terlebih dahulu.")
    else:
        with st.form("form_mob", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                unit_opt = st.selectbox("Pilih Unit:", options=df_master['Equipment_No'] + " - " + df_master['Equipment_Name'])
                aksi = st.selectbox("Jenis Aksi:", ["MOBILISASI (MOB)", "DEMOBILISASI (DEMOB)"])
                asal = st.text_input("Lokasi Asal:")
            with col2:
                tgl = st.date_input("Tanggal:", datetime.today())
                pic = st.text_input("PIC:", value=st.session_state.username)
                tujuan = st.text_input("Lokasi Tujuan:")
            ket = st.text_area("Keterangan:")
            
            sub = st.form_submit_button("Simpan Log Transaksi")
            if sub:
                eq_no = unit_opt.split(" - ")[0]
                eq_name = unit_opt.split(" - ")[1]
                payload = {
                    "action": "mob_demob",
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Tanggal_Transaksi": tgl.strftime("%Y-%m-%d"),
                    "Equipment_No": eq_no,
                    "Nama_Unit": eq_name,
                    "Jenis_Aksi": aksi,
                    "Lokasi_Asal": asal,
                    "Lokasi_Tujuan": tujuan,
                    "Keterangan": ket,
                    "PIC": pic
                }
                try:
                    res = requests.post(st.secrets["connections"]["gsheets"]["webapp_url"], json=payload)
                    if res.status_code == 200:
                        st.success(f"Transaksi {aksi} untuk unit {eq_no} berhasil dicatat permanen!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Gagal mencatat transaksi.")
                except Exception as e:
                    st.error(f"Error: {e}")

# ------------------------------------------
# 5. LOG TRANSAKSI PERMANEN
# ------------------------------------------
elif menu == "Log Transaksi Permanen":
    st.title("Log Transaksi Real-Time")
    conn = get_gsheets_connection()
    if conn:
        try:
            db_data = conn.read(worksheet="Log_Trans", ttl=0)
            st.dataframe(db_data, use_container_width=True)
            csv = db_data.to_csv(index=False).encode('utf-8')
            st.download_button("Export CSV", csv, "log_mob_demob.csv", "text/csv")
        except Exception:
            st.info("Belum ada data transaksi tercatat.")
