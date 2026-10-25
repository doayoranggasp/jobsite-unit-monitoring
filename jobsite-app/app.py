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
