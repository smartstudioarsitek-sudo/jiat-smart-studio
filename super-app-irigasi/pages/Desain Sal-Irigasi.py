# --- SIDEBAR: KONFIGURASI & FILE ---
with st.sidebar:
    st.header("1. Konfigurasi Trase")
    start_sta = st.number_input("STA Awal (m)", value=0.0)
    start_elv = st.number_input("Elevasi Awal (+m)", value=100.00)
    
    st.divider()
    st.header("📂 Menu File")
    
    # 1. DOWNLOAD TEMPLATE (Format Baru dengan Strickler k)
    df_template = pd.DataFrame({
        'Nama Saluran': ['Saluran 1', 'Saluran 2'],
        'Panjang (m)': [50.0, 50.0],
        'Offset (m)': [-0.10, -0.50],
        'Debit (Q)': [1.5, 2.0], 
        'Lebar (b)': [1.0, 1.2], 
        'Talud (m)': [1.0, 1.0], 
        'Slope (S)': [0.001, 0.001], 
        'Strickler (k)': [60, 40]  # Kolom Penting: k bukan n
    })
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer) as writer: df_template.to_excel(writer, index=False)
    st.download_button(
        label="📥 Download Template Excel",
        data=buffer.getvalue(),
        file_name="template_irigasi_kp03.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
    
    # 2. UPLOAD EXCEL (Fitur yang Hilang Tadi)
    uploaded_file = st.file_uploader("Upload Data Excel", type=['xlsx'])
    
    if uploaded_file:
        try:
            df_uploaded = pd.read_excel(uploaded_file)
            # Validasi kolom wajib agar tidak error saat Run
            required = ['Nama Saluran', 'Panjang (m)', 'Debit (Q)', 'Lebar (b)', 'Slope (S)', 'Strickler (k)']
            if all(col in df_uploaded.columns for col in required):
                st.session_state.df_input = df_uploaded
                st.success("✅ Data Excel berhasil dimuat!")
            else:
                st.error("❌ Format Excel salah! Pastikan menggunakan Template di atas (Kolom Strickler k wajib ada).")
        except Exception as e:
            st.error(f"Gagal membaca file: {e}")

    st.info("""
    **Referensi Nilai k (Strickler):**
    * Pasangan Batu: **60**
    * Beton: **70**
    * Tanah Bersih: **40**
    """)
