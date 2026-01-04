with rt_cs:
            st.markdown("### ❌ Cross Section: Desain vs Eksisting")
            if len(all_nodes_new) > 0:
                # --- MODIFIKASI MULAI: PILIH PER SEGMEN ---
                
                # 1. Ambil daftar nama segmen dari Input Data
                df_input = st.session_state['df_pro']
                seg_list = df_input['Nama Segmen'].tolist()
                
                # 2. Slider memilih Nama Segmen (bukan angka station)
                sel_seg = st.select_slider("Pilih Segmen", options=seg_list, key="slider_cs_new")
                
                # 3. Cari STA Awal dari segmen yang dipilih
                # Kita ambil row data input yang sesuai nama segmen
                row_seg = df_input[df_input['Nama Segmen'] == sel_seg].iloc[0]
                target_sta = row_seg['STA Awal (m)']
                
                # 4. Cari node hitungan yang posisinya paling dekat dengan STA Awal segmen tersebut
                # Kita pakai toleransi jarak 1 meter jaga-jaga kalau float tidak pas
                node_new = min(all_nodes_new, key=lambda n: abs(n['x'] - target_sta))
                
                # Cari node eksisting yang posisinya sama
                node_orig = next((n for n in all_nodes_ex if abs(n['x'] - node_new['x']) < 0.1), None)
                
                # Update variable agar plot grafik di bawahnya tetap jalan
                sel_sta_new = node_new['x'] 
                
                # --- MODIFIKASI SELESAI ---
                
                if node_new:
                    st.caption(f"Menampilkan Cross Section di STA {sel_sta_new:.2f} m (Awal Segmen {sel_seg})")
                    c1, c2 = st.columns([3, 1])
                    # ... (lanjutan kode plotting grafik di bawahnya biarkan sama)