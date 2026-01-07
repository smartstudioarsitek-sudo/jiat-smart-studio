def generate_cross_section_dxf(df_hasil):
    """Membuat Potongan Melintang (Cross Section) Layout Grid"""
    if not EZDXF_AVAILABLE: return None
    
    doc = ezdxf.new('R2010')
    setup_linetypes(doc)
    setup_kp07_layers(doc)
    msp = doc.modelspace()
    
    # Konfigurasi Grid Layout
    start_x = 0
    start_y = 0
    grid_x_spacing = 50
    grid_y_spacing = 50
    col_limit = 2
    
    current_col = 0
    
    for i, row in df_hasil.iterrows():
        # Posisi Pusat Gambar
        cx = start_x + (current_col * grid_x_spacing)
        cy = start_y
        
        b = row['Lebar (b)']
        m = row['Talud (m)']
        h = row['Tinggi Total (h)']
        y_air = row['Tinggi Air (y)']
        w_tanggul = 1.0 
        
        # Koordinat Lokal
        x_bl = -b/2
        x_br = b/2
        x_tl = -b/2 - (m*h)
        x_tr = b/2 + (m*h)
        x_bank_l = x_tl - w_tanggul
        x_bank_r = x_tr + w_tanggul
        
        y_btm = 0
        y_top = h
        y_wtr = y_air
        
        # 1. Gambar Body Saluran
        points = [
            (cx + x_bank_l, cy + y_top),
            (cx + x_tl, cy + y_top),
            (cx + x_bl, cy + y_btm),
            (cx + x_br, cy + y_btm),
            (cx + x_tr, cy + y_top),
            (cx + x_bank_r, cy + y_top)
        ]
        msp.add_lwpolyline(points, dxfattribs={'layer': 'DESAIN_DASAR'})
        
        # 2. Gambar Muka Air
        x_wl = -b/2 - (m*y_air)
        x_wr = b/2 + (m*y_air)
        msp.add_line((cx + x_wl, cy + y_wtr), (cx + x_wr, cy + y_wtr), dxfattribs={'layer': 'DESAIN_AIR'})
        msp.add_lwpolyline([(cx, cy+y_wtr), (cx-0.2, cy+y_wtr+0.4), (cx+0.2, cy+y_wtr+0.4), (cx, cy+y_wtr)], close=True, dxfattribs={'layer': 'DESAIN_AIR'})

        # 3. Gambar Tanah Asli
        msp.add_line((cx + x_bank_l - 2, cy + y_top), (cx + x_bank_r + 2, cy + y_top), dxfattribs={'layer': 'TANAH_ASLI'})
        
        # 4. Anotasi Dimensi (PERBAIKAN UTAMA DISINI)
        # Menggunakan add_linear_dim yang valid
        # Format: base=(lokasi garis dimensi), p1=(titik ukur 1), p2=(titik ukur 2)
        try:
            msp.add_linear_dim(
                base=(cx, cy - 1.5),           # Garis dimensi ditaruh di bawah saluran
                p1=(cx + x_bl, cy + y_btm),    # Pojok kiri bawah saluran
                p2=(cx + x_br, cy + y_btm),    # Pojok kanan bawah saluran
                dxfattribs={'layer': 'DIMENSI'},
                text=f"b = {b:.2f}"            # Override teks (manual value agar aman)
            )
        except AttributeError:
            # Fallback manual jika versi ezdxf sangat lama atau metode tidak dikenali
            # Gambar garis dimensi manual
            msp.add_line((cx + x_bl, cy - 1.5), (cx + x_br, cy - 1.5), dxfattribs={'layer': 'DIMENSI'})
            msp.add_text(f"b = {b:.2f}", dxfattribs={'height': 0.5, 'layer': 'DIMENSI'}).set_placement((cx, cy - 1.2), align=TextEntityAlignment.MIDDLE_CENTER)

        # Info Teks
        msp.add_text(f"STA: {row['STA Awal']}", dxfattribs={'height': 1.0, 'layer': 'KOP_TEXT'}).set_placement((cx, cy - 3), align=TextEntityAlignment.MIDDLE_CENTER)
        msp.add_text(f"Elv. Dasar: {row['Elv Dasar Awal']:.2f}", dxfattribs={'height': 0.8, 'layer': 'KOP_TEXT'}).set_placement((cx, cy - 4.5), align=TextEntityAlignment.MIDDLE_CENTER)

        current_col += 1
        if current_col >= col_limit:
            current_col = 0
            start_y -= grid_y_spacing

    return doc
