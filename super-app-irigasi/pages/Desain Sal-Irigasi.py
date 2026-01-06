# ==========================================
# 5. LOGIKA PERHITUNGAN BERANTAI (CHAINING) - REVISI
# ==========================================

btn_run = st.button("▶️ HITUNG SEMUA (RUN)", type="primary", use_container_width=True)

if btn_run:
    hasil_list = []
    
    # Inisialisasi Variable "Estafet"
    current_sta = start_sta
    current_elv = start_elv
    
    for index, row in edited_df.iterrows():
        # 1. Ambil Data Input
        L = row['Panjang (m)']
        offset_input = row['Offset (m)'] # Nilai dari tabel (misal -1.5)
        Q = row['Debit (Q)']
        b = row['Lebar (b)']
        m = row['Talud (m)']
        S = row['Slope (S)']
        n = row['Manning (n)']
        
        # 2. Hitung Hidrolis (Manning)
        y_calc = solve_manning_y(Q, b, m, n, S)
        w_calc = get_freeboard_kp03(Q)
        h_calc = y_calc + w_calc
        
        # Hitung Luas Basah & Kecepatan
        area_basah = (b + m * y_calc) * y_calc
        v_calc = Q / area_basah if area_basah > 0 else 0
        
        # 3. Hitung STA & Elevasi (Logika Berantai)
        sta_awal = current_sta
        sta_akhir = current_sta + L
        
        elv_dasar_awal = current_elv
        # Rumus Turun Sepanjang Saluran: Elv Awal - (Panjang * Slope)
        elv_dasar_akhir = elv_dasar_awal - (L * S)
        
        # Simpan Hasil
        hasil_list.append({
            'Nama Saluran': row['Nama Saluran'],
            'STA Awal': round(sta_awal, 1),
            'STA Akhir': round(sta_akhir, 1),
            'Elv Dasar Awal': round(elv_dasar_awal, 3),
            'Elv Dasar Akhir': round(elv_dasar_akhir, 3),
            'Drop/Offset': offset_input,
            'Tinggi Air (y)': round(y_calc, 3),
            'Tinggi Total (h)': round(h_calc, 2),
            'Kecepatan (V)': round(v_calc, 2),
            # Data tambahan untuk visualisasi
            'Lebar (b)': b, 'Talud (m)': m, 'Jagaan (w)': round(w_calc, 2)
        })
        
        # 4. Update Titik Start untuk Saluran Berikutnya
        current_sta = sta_akhir
        
        # --- PERBAIKAN LOGIKA DISINI KAK ---
        # Karena input kakak negatif (-1.5), maka kita pakai TAMBAH (+)
        # 100 + (-1.5) = 98.5 (Turun)
        current_elv = elv_dasar_akhir + offset_input 

    st.session_state.df_hasil = pd.DataFrame(hasil_list)
    st.success("Perhitungan Berantai Selesai! Elevasi sekarang sudah turun.")
