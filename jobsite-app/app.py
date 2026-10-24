import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# ==========================================
# CONFIG & PAGE SETUP
# ==========================================
st.set_page_config(
    page_title="Jobsite Equipment Monitoring & Mob-Demob",
    page_icon="🚜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS untuk Tampilan Expert & Modern
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .metric-card {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border-left: 5px solid #007bff;
    }
    .stButton>button {
        width: 100%;
        background-color: #007bff;
        color: white;
        border-radius: 8px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# DATA LOADING & PARSING FUNCTION
# ==========================================
@st.cache_data
def load_and_clean_data(file_path):
    try:
        # Load raw excel tanpa header bawaan
        df_raw = pd.read_excel(file_path, header=None)
        
        # Eliminasi header laporan Ellipse (baris 0-2)
        df_content = df_raw.iloc[3:].copy()
        
        # Pemetaan kolom standar MSE600
        # Col 0: Equipment No, Col 2: Name/Description, Col 3: Status Code, Col 4: Status Name, 
        # Col 7: Site Code, Col 8: Site Name/Project, Col 11: Serial Number/Spec
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
    except Exception as e:
        st.error(f"Error membaca file database: {e}")
        return pd.DataFrame()

# ==========================================
# SESSION STATE SETUP FOR MOB / DEMOB LOGS
# ==========================================
if 'mob_demob_logs' not in st.session_state:
    st.session_state['mob_demob_logs'] = pd.DataFrame(columns=[
        'Tanggal_Transaksi', 'Equipment_No', 'Nama_Unit', 'Jenis_Aksi', 
        'Lokasi_Asal', 'Lokasi_Tujuan', 'Keterangan', 'PIC'
    ])

# ==========================================
# SIDEBAR NAVIGATION
# ==========================================
st.sidebar.title("🚜 Jobsite Fleet System")
st.sidebar.caption("Sistem Monitoring MSE600 & Mob-Demob")

uploaded_file = st.sidebar.file_uploader("Upload Database (MSE600.xlsx)", type=["xlsx", "xls"])

menu = st.sidebar.radio(
    "Navigasi Menu",
    ["📊 Dashboard Overview", "🔍 Data Master Unit", "🚚 Mobilisasi & Demobilisasi", "📜 Riwayat Transaksi"]
)

# Load Data
if uploaded_file is not None:
    df = load_and_clean_data(uploaded_file)
else:
    # Menggunakan file bawaan jika diunggah di server
    df = load_and_clean_data("MSE600 (1).xlsx")

# ==========================================
# MENU 1: DASHBOARD OVERVIEW
# ==========================================
if menu == "📊 Dashboard Overview":
    st.title("📊 Dashboard Monitoring Equipment Jobsite")
    st.markdown("---")

    if not df.empty:
        # Ringkasan KPI Cards
        total_unit = len(df)
        available_unit = len(df[df['Status_Code'] == 'AV'])
        off_hire_unit = len(df[df['Status_Code'] == 'OH'])
        other_unit = total_unit - (available_unit + off_hire_unit)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Unit Jobsite", f"{total_unit} Unit")
        col2.metric("Available (AV)", f"{available_unit} Unit", delta=f"{(available_unit/total_unit)*100:.1f}%")
        col3.metric("Off Hire (OH)", f"{off_hire_unit} Unit", delta=f"-{(off_hire_unit/total_unit)*100:.1f}%")
        col4.metric("Status Lainnya", f"{other_unit} Unit")

        st.markdown("---")

        # Grafik Distribusi Status Unit & Subcontractor/Project
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.subheader("Distribusi Status Operational Unit")
            status_counts = df['Status_Description'].value_counts().reset_index()
            status_counts.columns = ['Status', 'Jumlah']
            fig_status = px.pie(
                status_counts, 
                names='Status', 
                values='Jumlah', 
                hole=0.4, 
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            st.plotly_chart(fig_status, use_container_width=True)

        with chart_col2:
            st.subheader("Top 10 Sebaran Project/Subcontractor")
            site_counts = df['Project_Location'].value_counts().head(10).reset_index()
            site_counts.columns = ['Project / Location', 'Jumlah Unit']
            fig_site = px.bar(
                site_counts, 
                x='Jumlah Unit', 
                y='Project / Location', 
                orientation='h',
                color='Jumlah Unit',
                color_continuous_scale='Blues'
            )
            fig_site.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_site, use_container_width=True)
    else:
        st.warning("Data tidak tersedia. Silakan unggah file database MSE600.xlsx pada sidebar.")

# ==========================================
# MENU 2: DATA MASTER UNIT
# ==========================================
elif menu == "🔍 Data Master Unit":
    st.title("🔍 Data Master Equipment & Status")
    st.markdown("Filter dan pencarian rinci untuk seluruh unit di jobsite.")

    if not df.empty:
        # Filter Section
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            status_filter = st.multiselect(
                "Filter Status Unit:", 
                options=df['Status_Description'].unique(),
                default=df['Status_Description'].unique()
            )
        with f_col2:
            search_query = st.text_input("Cari No Equipment / Nama Unit / SN:")

        # Applying Filters
        filtered_df = df[df['Status_Description'].isin(status_filter)]
        if search_query:
            filtered_df = filtered_df[
                filtered_df['Equipment_No'].str.contains(search_query, case=False) |
                filtered_df['Equipment_Name'].str.contains(search_query, case=False) |
                filtered_df['Serial_Number_Info'].str.contains(search_query, case=False)
            ]

        st.dataframe(filtered_df, use_container_width=True, height=450)
        
        # Download Data
        csv = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Export Filtered Data ke CSV", csv, "filtered_unit_data.csv", "text/csv")
    else:
        st.warning("Data kosong.")

# ==========================================
# MENU 3: MOBILISASI & DEMOBILISASI
# ==========================================
elif menu == "🚚 Mobilisasi & Demobilisasi":
    st.title("🚚 Form Mobilisasi & Demobilisasi Unit")
    st.markdown("Catat pergerakan masuk (Mob) dan keluar (Demob) unit jobsite secara real-time.")

    if not df.empty:
        with st.form("form_mob_demob", clear_on_submit=True):
            col_a, col_b = st.columns(2)

            with col_a:
                unit_selected = st.selectbox(
                    "Pilih Unit / Equipment No:",
                    options=df['Equipment_No'] + " - " + df['Equipment_Name']
                )
                jenis_aksi = st.selectbox("Jenis Transaksi:", ["MOBILISASI (MOB)", "DEMOBILISASI (DEMOB)"])
                lokasi_asal = st.text_input("Lokasi Asal (Origin):")
                
            with col_b:
                tanggal = st.date_input("Tanggal Pelaksanaan:", datetime.today())
                pic = st.text_input("Nama PIC / Penanggung Jawab:")
                lokasi_tujuan = st.text_input("Lokasi Tujuan (Destination):")

            keterangan = st.text_area("Keterangan Catatan / Condition Report:")
            
            submit_btn = st.form_submit_dict = st.form_submit_button("💾 Simpan Transaksi Mob/Demob")

            if submit_btn:
                eq_no = unit_selected.split(" - ")[0]
                eq_name = unit_selected.split(" - ")[1]
                
                new_data = {
                    'Tanggal_Transaksi': tanggal.strftime("%Y-%m-%d"),
                    'Equipment_No': eq_no,
                    'Nama_Unit': eq_name,
                    'Jenis_Aksi': jenis_aksi,
                    'Lokasi_Asal': lokasi_asal,
                    'Lokasi_Tujuan': lokasi_tujuan,
                    'Keterangan': keterangan,
                    'PIC': pic
                }
                
                # Append ke session state dataframe
                st.session_state['mob_demob_logs'] = pd.concat(
                    [st.session_state['mob_demob_logs'], pd.DataFrame([new_data])], 
                    ignore_index=True
                )
                st.success(f"Berhasil mencatat transaksi {jenis_aksi} untuk unit {eq_no}!")

# ==========================================
# MENU 4: RIWAYAT TRANSAKSI
# ==========================================
elif menu == "📜 Riwayat Transaksi":
    st.title("📜 Log Riwayat Mobilisasi & Demobilisasi")
    st.markdown("Daftar catatan pergerakan unit yang telah diinput.")

    logs_df = st.session_state['mob_demob_logs']

    if not logs_df.empty:
        st.dataframe(logs_df, use_container_width=True)
        
        # Download Button Log Transaksi
        log_csv = logs_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Export Log Transaksi (CSV)", log_csv, "log_mob_demob.csv", "text/csv")
    else:
        st.info("Belum ada riwayat transaksi mobilisasi/demobilisasi yang dicatat pada sesi ini.")