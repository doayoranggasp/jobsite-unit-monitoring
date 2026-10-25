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
