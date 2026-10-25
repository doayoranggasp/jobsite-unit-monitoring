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

def get_gsheets_connection():
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except:
        return None

# ==========================================
# LOAD MASTER DARI GOOGLE SHEETS PERMANEN
# ==========================================
@st.cache_data
def load_master_from_cloud():
    conn = get_gsheets_connection()
    if conn:
        try:
            df_raw = conn.read(worksheet="MSE600", ttl=0, header=None)
            if df_raw.empty or len(df_raw) < 4:
                return pd.DataFrame()
            
            df_content = df_raw.iloc[3:].copy()
            cleaned_df = pd.DataFrame({
                'Equipment_No': df_content[0].astype(str),
                'Equipment_Name': df_content[2].astype(str),
                'Status_Code': df_content[3].astype(str),
                'Status_Description': df_content[4].astype(str),
                'Site_Code': df_content[7].astype(str),
                'Project_Location': df_content[8].astype(str),
                'Serial_Number_Info': df_content[11].astype(str)
            })
            cleaned_df.dropna(subset=['Equipment_No'], inplace=True)
            return cleaned_df
        except:
            return pd.DataFrame()
    return pd.DataFrame()

df_master = load_master_from_cloud()

# ==========================================
# SIDEBAR NAVIGATION & UPLOAD MASTER
# ==========================================
st.sidebar.title("🚜 Jobsite Fleet System")
st.sidebar.caption("System Monitoring & Mob-Demob Real-Time")

menu = st.sidebar.radio(
    "Navigasi Menu",
    ["📊 Dashboard Overview", "🔍 Master Data Unit", "🚚 Form Mob / Demob", "📜 Log Transaksi Permanen"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("📂 Pengaturan Master MSE600")
uploaded_file = st.sidebar.file_uploader("Upload Excel MSE600 Baru (.xlsx)", type=["xlsx", "xls"])

if uploaded_file is not None:
    if st.sidebar.button("💾 Simpan Master ke Cloud Permanen"):
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
                st.sidebar.success("✅ Master MSE600 berhasil disimpan permanen di Cloud!")
                st.cache_data.clear()
                st.rerun()
            else:
                st.sidebar.error("Gagal menyimpan ke cloud.")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")

if st.sidebar.button("🔄 Refresh Data Real-Time"):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# MENU 1: DASHBOARD OVERVIEW
# ==========================================
if menu == "📊 Dashboard Overview":
    st.title("📊 Dashboard Fleet & Operational Overview")
    st.markdown("---")

    if df_master.empty:
        st.warning("⚠️ Belum ada Data Master **MSE600** di Google Sheets. Silakan upload file Excel master Anda melalui menu di sidebar kiri lalu klik 'Simpan Master ke Cloud Permanen'.")
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

# ==========================================
# MENU 2: MASTER DATA UNIT
# ==========================================
elif menu == "🔍 Master Data Unit":
    st.title("🔍 Master Data Equipment Ellipse (Live)")
    
    if df_master.empty:
        st.warning("⚠️ Data Master belum tersedia. Silakan upload via sidebar.")
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

# ==========================================
# MENU 3: FORM MOBILISASI & DEMOBILISASI
# ==========================================
elif menu == "🚚 Form Mob / Demob":
    st.title("🚚 Input Mobilisasi & Demobilisasi (Auto-Update)")
    st.markdown("Input transaksi akan mencatat log DAN otomatis memperbarui status/lokasi unit di Cloud.")

    if df_master.empty:
        st.warning("⚠️ Data Master belum tersedia. Upload file Excel MSE600 terlebih dahulu di sidebar.")
    else:
        with st.form("form_mob_demob", clear_on_submit=True):
            col_a, col_b = st.columns(2)

            with col_a:
                unit_selected = st.selectbox("Pilih Equipment No & Nama:", options=df_master['Equipment_No'] + " - " + df_master['Equipment_Name'])
                jenis_aksi = st.selectbox("Jenis Transaksi:", ["MOBILISASI (MOB)", "DEMOBILISASI (DEMOB)"])
                lokasi_asal = st.text_input("Lokasi Asal (Origin):")
                
            with col_b:
                tanggal = st.date_input("Tanggal Pelaksanaan:", datetime.today())
                pic = st.text_input("Nama PIC / Penanggung Jawab:")
                lokasi_tujuan = st.text_input("Lokasi Tujuan (Destination):")

            keterangan = st.text_area("Keterangan Catatan / Condition Report:")
            submit_btn = st.form_submit_button("💾 Simpan Permanen ke Cloud")

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
                        st.success(f"✅ Berhasil! Transaksi {jenis_aksi} unit {eq_no} tersimpan dan Master Cloud ter-update!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Gagal mengirim data. Code: {response.status_code}")
                except Exception as err:
                    st.error(f"Terjadi kesalahan koneksi: {err}")

# ==========================================
# MENU 4: LOG TRANSAKSI PERMANEN
# ==========================================
elif menu == "📜 Log Transaksi Permanen":
    st.title("📜 Log Transaksi Real-Time (Google Sheets)")
    
    conn = get_gsheets_connection()
    if conn:
        try:
            db_data = conn.read(worksheet="Log_Trans", ttl=0)
            st.dataframe(db_data, use_container_width=True)
            
            csv = db_data.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export Log Database (CSV)", csv, "log_database_mob_demob.csv", "text/csv")
        except:
            st.info("Belum ada transaksi di tab Log_Trans.")
