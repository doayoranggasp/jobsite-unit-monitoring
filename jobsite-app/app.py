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
    st.markdown("Silakan masuk menggunakan akun Anda atau daftarkan akun baru untuk mulai mengakses dashboard.")
    
    auth_tab1, auth_tab2 = st.tabs(["Login", "Register Akun Baru"])
    
    with auth_tab1:
        with st.form("login_form"):
            l_user = st.text_input("Username")
            l_pass = st.text_input("Password", type="password")
            l_btn = st.form_submit_button("Masuk ke Sistem")
            
            if l_btn:
                if not l_user or not l_pass:
                    st.warning("Username dan Password wajib diisi!")
                else:
                    payload = {
                        "action": "login",
                        "username": l_user,
                        "password": l_pass
                    }
                    try:
                        webapp_url = st.secrets["connections"]["gsheets"]["webapp_url"]
                        res = requests.post(webapp_url, json=payload)
                        res_json = res.json()
                        
                        if res_json.get("result") == "success":
                            st.session_state.logged_in = True
                            st.session_state.username = l_user.strip()
                            st.success(f"Login Berhasil! Selamat datang, {l_user}.")
                            st.rerun()
                        else:
                            st.error(res_json.get("message", "Username atau Password salah!"))
                    except Exception as err:
                        st.error(f"Gagal terhubung ke server: {err}")

    with auth_tab2:
        with st.form("register_form"):
            r_user = st.text_input("Buat Username Baru")
            r_pass = st.text_input("Buat Password Baru", type="password")
            r_btn = st.form_submit_button("Daftar Akun")
            
            if r_btn:
                if not r_user or not r_pass:
                    st.warning("Semua kolom wajib diisi!")
                else:
                    payload = {
                        "action": "register",
                        "username": r_user,
                        "password": str(r_pass),
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    try:
                        webapp_url = st.secrets["connections"]["gsheets"]["webapp_url"]
                        res = requests.post(webapp_url, json=payload)
                        res_json = res.json()
                        if res_json.get("result") == "success":
                            st.success("Pendaftaran berhasil! Silakan pindah ke tab Login.")
                        else:
                            st.warning(res_json.get('message', 'Gagal mendaftar.'))
                    except Exception as err:
                        st.error(f"Error koneksi: {err}")
    st.stop()

# ==========================================
# APLIKASI UTAMA (AUTO-DETECT MASTER PARSER)
# ==========================================
@st.cache_data
def load_master_from_cloud():
    conn = get_gsheets_connection()
    if conn:
        try:
            df_raw = conn.read(worksheet="MSE600", ttl=0, header=None)
            if df_raw.empty:
                return pd.DataFrame()
            
            # Deteksi otomatis baris awal data berdasarkan isi sel pertama
            start_row = 3
            if len(df_raw) > 0:
                val_col0 = str(df_raw.iloc[0, 0]).lower()
                if 'equip' in val_col0 or 'unit' in val_col0 or 'no' in val_col0 or len(df_raw) < 4:
                    start_row = 0  # Jika baris pertama sudah berupa header atau data langsung
            
            df_content = df_raw.iloc[start_row:].copy()
            cols = df_content.shape[1]
            
            cleaned_df = pd.DataFrame({
                'Equipment_No': df_content.iloc[:, 0].astype(str) if cols > 0 else "",
                'Equipment_Name': df_content.iloc[:, 2].astype(str) if cols > 2 else (df_content.iloc[:, 1].astype(str) if cols > 1 else ""),
                'Status_Code': df_content.iloc[:, 3].astype(str) if cols > 3 else "",
                'Status_Description': df_content.iloc[:, 4].astype(str) if cols > 4 else "",
                'Site_Code': df_content.iloc[:, 7].astype(str) if cols > 7 else "",
                'Project_Location': df_content.iloc[:, 8].astype(str) if cols > 8 else (df_content.iloc[:, 5].astype(str) if cols > 5 else ""),
                'Serial_Number_Info': df_content.iloc[:, 11].astype(str) if cols > 11 else (df_content.iloc[:, 6].astype(str) if cols > 6 else "")
            })
            
            # Bersihkan baris kosong atau baris header tiruan
            cleaned_df = cleaned_df[~cleaned_df['Equipment_No'].isin(['nan', '', 'Equipment_No', 'Equipment No', 'Equip No', 'Equipment', 'None'])]
            cleaned_df.dropna(subset=['Equipment_No'], inplace=True)
            return cleaned_df
        except Exception as e:
            return pd.DataFrame()
    return pd.DataFrame()

df_master = load_master_from_cloud()

# Sidebar Navigation
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
# MENU 1: DASHBOARD OVERVIEW
# ------------------------------------------
if menu == "Dashboard Overview":
    st.title("Dashboard Fleet & Operational Overview")
    st.markdown("---")

    if df_master.empty:
        st.warning("Belum ada Data Master MSE600 di Google Sheets. Silakan upload file Excel master Anda melalui menu Upload / Update Master MSE600 di sidebar.")
    else:
        total_unit = len(df_master)
        available_unit = len(df_master[df_master['Status_Code'] == 'AV'])
        off_hire_unit = len(df_master[df_master['Status_Code'] == 'OH'])
        other_unit = total_unit - (available_unit + off_hire_unit)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Unit Jobsite", f"{total_unit} Unit")
        col2.metric("Available (AV)", f"{available_unit} Unit", delta=f"{(available_unit/total_unit)*100:.1f}%")
        col3.metric("Off Hire (OH)", f"{off_hire_unit} Unit", delta=f"-{(off_hire_unit/total_unit)*100:.1f}%")
        col4.metric("Status Lainnya", f"{other_unit} Unit")

        st.markdown("---")
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.subheader("Distribusi Status Unit")
            status_counts = df_master['Status_Description'].value_counts().reset_index()
            status_counts.columns = ['Status', 'Jumlah']
            fig_status = px.pie(status_counts, names='Status', values='Jumlah', hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig_status, use_container_width=True)

        with chart_col2:
            st.subheader("Top 10 Sebaran Project / Subcontractor")
            site_counts = df_master['Project_Location'].value_counts().head(10).reset_index()
            site_counts.columns = ['Project / Location', 'Jumlah Unit']
            fig_site = px.bar(site_counts, x='Jumlah Unit', y='Project / Location', orientation='h', color='Jumlah Unit', color_continuous_scale='Blues')
            fig_site.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_site, use_container_width=True)

# ------------------------------------------
# MENU 2: MASTER DATA UNIT
# ------------------------------------------
elif menu == "Master Data Unit":
    st.title("Master Data Equipment Ellipse (Live)")
    
    if df_master.empty:
        st.warning("Data Master belum tersedia. Silakan upload file Excel MSE600 melalui menu di sidebar.")
    else:
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            status_filter = st.multiselect("Filter Status Unit:", options=df_master['Status_Description'].unique(), default=df_master['Status_Description'].unique())
        with f_col2:
            search_query = st.text_input("Cari Unit No / Nama / Serial Number:")

        filtered_df = df_master[df_master['Status_Description'].isin(status_filter)]
        if search_query:
            filtered_df = filtered_df[
                filtered_df['Equipment_No'].str.contains(search_query, case=False) |
                filtered_df['Equipment_Name'].str.contains(search_query, case=False) |
                filtered_df['Serial_Number_Info'].str.contains(search_query, case=False)
            ]

        st.dataframe(filtered_df, use_container_width=True, height=450)

# ------------------------------------------
# MENU 3: UPLOAD / UPDATE MASTER MSE600
# ------------------------------------------
elif menu == "Upload / Update Master MSE600":
    st.title("Upload & Perbarui Master Data MSE600")
    st.markdown("Pilih file Excel laporan Ellipse Anda untuk disimpan permanen ke dalam Google Sheets.")
    
    uploaded_file = st.file_uploader("Upload Excel MSE600 (.xlsx)", type=["xlsx", "xls"])
    if uploaded_file is not None:
        if st.button("Simpan Master ke Cloud Permanen"):
            try:
                df_raw_upload = pd.read_excel(uploaded_file, header=None)
                rows_data = df_raw_upload.fillna("").values.tolist()
                
                payload = {
                    "action": "upload_master",
                    "rows": rows_data
                }
                webapp_url = st.secrets["connections"]["gsheets"]["webapp_url"]
                res = requests.post(webapp_url, json=payload)
                if res.status_code == 200:
                    st.success("Master MSE600 berhasil disimpan permanen di Cloud!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Gagal menyimpan ke cloud.")
            except Exception as e:
                st.error(f"Error: {e}")

# ------------------------------------------
# MENU 4: FORM MOBILISASI & DEMOBILISASI
# ------------------------------------------
elif menu == "Form Mob / Demob":
    st.title("Input Mobilisasi & Demobilisasi")
    st.markdown("Setiap input transaksi akan mencatat log DAN memperbarui lokasi serta status unit di Master Cloud secara otomatis.")

    if df_master.empty:
        st.warning("Data Master belum tersedia. Upload file Excel MSE600 terlebih dahulu di menu Upload / Update Master MSE600.")
    else:
        with st.form("form_mob_demob", clear_on_submit=True):
            col_a, col_b = st.columns(2)

            with col_a:
                unit_selected = st.selectbox("Pilih Equipment No & Nama:", options=df_master['Equipment_No'] + " - " + df_master['Equipment_Name'])
                jenis_aksi = st.selectbox("Jenis Transaksi:", ["MOBILISASI (MOB)", "DEMOBILISASI (DEMOB)"])
                lokasi_asal = st.text_input("Lokasi Asal (Origin):")
                
            with col_b:
                tanggal = st.date_input("Tanggal Pelaksanaan:", datetime.today())
                pic = st.text_input("Nama PIC / Penanggung Jawab:", value=st.session_state.username)
                lokasi_tujuan = st.text_input("Lokasi Tujuan (Destination):")

            keterangan = st.text_area("Keterangan Catatan / Condition Report:")
            submit_btn = st.form_submit_button("Simpan Permanen ke Cloud")

            if submit_btn:
                eq_no = unit_selected.split(" - ")[0]
                eq_name = unit_selected.split(" - ")[1]
                
                payload = {
                    "action": "mob_demob",
                    'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'Tanggal_Transaksi': tanggal.strftime("%Y-%m-%d"),
                    'Equipment_No': eq_no,
                    'Nama_Unit': eq_name,
                    'Jenis_Aksi': jenis_aksi,
                    'Lokasi_Asal': lokasi_asal,
                    'Lokasi_Tujuan': lokasi_tujuan,
                    'Keterangan': keterangan,
                    'PIC': pic
                }

                try:
                    webapp_url = st.secrets["connections"]["gsheets"]["webapp_url"]
                    response = requests.post(webapp_url, json=payload)
                    if response.status_code == 200:
                        st.success(f"Berhasil! Transaksi {jenis_aksi} unit {eq_no} tersimpan dan Master Cloud ter-update!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Gagal mengirim data. Code: {response.status_code}")
                except Exception as err:
                    st.error(f"Terjadi kesalahan koneksi: {err}")

# ------------------------------------------
# MENU 5: LOG TRANSAKSI PERMANEN
# ------------------------------------------
elif menu == "Log Transaksi Permanen":
    st.title("Log Transaksi Real-Time (Google Sheets)")
    
    conn = get_gsheets_connection()
    if conn:
        try:
            db_data = conn.read(worksheet="Log_Trans", ttl=0)
            st.dataframe(db_data, use_container_width=True)
            
            csv = db_data.to_csv(index=False).encode('utf-8')
            st.download_button("Export Log Database (CSV)", csv, "log_database_mob_demob.csv", "text/csv")
        except:
            st.info("Belum ada transaksi di tab Log_Trans.")
