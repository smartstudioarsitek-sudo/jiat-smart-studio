def generate_dxf_kp07(df_hasil):
    """
    Generate Long Section DXF sesuai Standar KP-07 dengan Smart Datum.
    """
    if not EZDXF_AVAILABLE: 
        return None

    # 1. SETUP DOKUMEN & STANDAR
    doc = ezdxf.new('R2010')
    setup_linetypes(doc) # Load linetypes standar (DASHED, CENTER, dll)
    msp = doc.modelspace()

    # Setup Layer sesuai KP-07 (Warna ACI: 1=Merah, 2=Kuning, 3=Hijau, 7=Putih/Hitam, 8=Abu)
    layers = [
        ('KOP_GRID', 8, 'CONTINUOUS'),      # Garis Grid Tipis
        ('KOP_TEXT', 7, 'CONTINUOUS'),      # Teks Data
        ('TANAH_ASLI', 3, 'DASHED'),        # Hijau, Putus-putus (Existing)
        ('DESAIN_DASAR', 1, 'CONTINUOUS'),  # Merah (Rencana Dasar)
        ('DESAIN_AIR', 5, 'DASHDOT'),       # Biru (Muka Air)
        ('DESAIN_TANGGUL', 2, 'CONTINUOUS') # Kuning (Tanggul)
    ]
    for name, color, ltype in layers:
        if name not in doc.layers:
            doc.layers.add(name, color=color, linetype=ltype)

    # Setup Text Style
    if 'KP_TEXT_STYLE' not in doc.styles:
        doc.styles.new('KP_TEXT_STYLE', dxfattribs={'font': 'Arial.ttf', 'width': 0.8})

    # 2. KONFIGURASI SKALA & DATUM (INTI PERMASALAHAN)
    # Skala: Horizontal 1:1000, Vertikal 1:100 (Distorsi 10x agar terlihat jelas)
    SCALE_H = 1.0   # 1 unit DXF = 1 meter Horizontal
    SCALE_V = 10.0  # 1 unit DXF = 1 meter Vertikal (Exaggerated)

    # ALGORITMA SMART DATUM:
    # Mencari elevasi terendah, lalu membulatkan ke bawah kelipatan 5 terdekat.
    # Ini memastikan gambar selalu proporsional di atas kolom data.
    min_elev_dasar = min(df_hasil['Elv Dasar Awal'].min(), df_hasil['Elv Dasar Akhir'].min())
    # Asumsi tanah asli sedikit di atas desain, tapi kita ambil buffer aman
    datum_reference = np.floor((min_elev_dasar - 2.0) / 5.0) * 5.0
    
    # 3. SETUP AREA GAMBAR (Layout Bands)
    # Posisi Y untuk baris-baris data (relatif terhadap Y=0 graph)
    Y_GRAPH_ZERO = 0
    H_ROW = 15 # Tinggi baris teks data (dalam unit gambar)
    
    bands = {
        'JARAK':        {'y': -1 * H_ROW, 'label': 'JARAK (m)'},
        'ELV_TANAH':    {'y': -2 * H_ROW, 'label': 'ELV. TANAH (+m)'},
        'ELV_DESAIN':   {'y': -3 * H_ROW, 'label': 'ELV. DESAIN (+m)'},
        'ELV_AIR':      {'y': -4 * H_ROW, 'label': 'MUKA AIR (+m)'},
        'DIMENSI':      {'y': -5 * H_ROW, 'label': 'DIMENSI'}
    }
    
    min_y_band = bands['DIMENSI']['y']
    
    # Gambar Garis Horizontal Tabel (Header)
    max_sta = df_hasil['STA Akhir'].max() * SCALE_H
    
    # Label Header Kiri
    for key, info in bands.items():
        y_pos = info['y']
        # Garis horizontal
        msp.add_line((-30, y_pos), (max_sta, y_pos), dxfattribs={'layer': 'KOP_GRID'})
        # Teks Judul Kolom
        msp.add_text(info['label'], dxfattribs={
            'height': 2.5, 
            'style': 'KP_TEXT_STYLE', 
            'layer': 'KOP_TEXT'
        }).set_placement((-2, y_pos + H_ROW/2), align=TextEntityAlignment.MIDDLE_RIGHT)

    # Garis penutup atas tabel (batas bawah grafik)
    msp.add_line((-30, Y_GRAPH_ZERO), (max_sta, Y_GRAPH_ZERO), dxfattribs={'layer': 'KOP_GRID', 'lineweight': 30})
    
    # Info Datum
    msp.add_text(f"DATUM: +{datum_reference:.2f}", dxfattribs={'height': 2.5, 'layer': 'KOP_TEXT'}).set_placement((-2, Y_GRAPH_ZERO + 2), align=TextEntityAlignment.MIDDLE_RIGHT)

    # 4. GAMBAR TRASE & DATA
    prev_x = None
    prev_y_dasar = None
    
    for i, row in df_hasil.iterrows():
        # Koordinat X
        x_awal = row['STA Awal'] * SCALE_H
        x_akhir = row['STA Akhir'] * SCALE_H
        
        # Koordinat Y (Relatif terhadap Datum & Skala Vertikal)
        y_dasar_awal = (row['Elv Dasar Awal'] - datum_reference) * SCALE_V
        y_dasar_akhir = (row['Elv Dasar Akhir'] - datum_reference) * SCALE_V
        
        y_air_awal = (row['Elv Dasar Awal'] + row['Tinggi Air (y)'] - datum_reference) * SCALE_V
        y_air_akhir = (row['Elv Dasar Akhir'] + row['Tinggi Air (y)'] - datum_reference) * SCALE_V
        
        y_tanggul_awal = (row['Elv Dasar Awal'] + row['Tinggi Total (h)'] - datum_reference) * SCALE_V
        y_tanggul_akhir = (row['Elv Dasar Akhir'] + row['Tinggi Total (h)'] - datum_reference) * SCALE_V
        
        # Simulasi Tanah Asli (Biasanya dari data ukur, disini kita asumsi rata tanggul + 0.3m)
        z_tanah_awal = row['Elv Dasar Awal'] + row['Tinggi Total (h)'] + 0.3
        z_tanah_akhir = row['Elv Dasar Akhir'] + row['Tinggi Total (h)'] + 0.3
        y_tanah_awal = (z_tanah_awal - datum_reference) * SCALE_V
        y_tanah_akhir = (z_tanah_akhir - datum_reference) * SCALE_V

        # --- A. GAMBAR GARIS PROFIL ---
        # Dasar Saluran
        msp.add_line((x_awal, y_dasar_awal), (x_akhir, y_dasar_akhir), dxfattribs={'layer': 'DESAIN_DASAR', 'lineweight': 40})
        # Muka Air
        msp.add_line((x_awal, y_air_awal), (x_akhir, y_air_akhir), dxfattribs={'layer': 'DESAIN_AIR'})
        # Tanggul
        msp.add_line((x_awal, y_tanggul_awal), (x_akhir, y_tanggul_akhir), dxfattribs={'layer': 'DESAIN_TANGGUL'})
        # Tanah Asli
        msp.add_line((x_awal, y_tanah_awal), (x_akhir, y_tanah_akhir), dxfattribs={'layer': 'TANAH_ASLI'})
        
        # Sambungan Vertikal (Jika ada terjunan/perubahan dimensi mendadak)
        if prev_x is not None and (abs(prev_y_dasar - y_dasar_awal) > 0.001):
             msp.add_line((prev_x, prev_y_dasar), (x_awal, y_dasar_awal), dxfattribs={'layer': 'DESAIN_DASAR'})

        # --- B. TEKS DATA VERTIKAL (BANDS) ---
        # Helper function untuk teks vertikal
        def add_band_text(txt, x_pos, y_bottom):
            msp.add_text(txt, dxfattribs={
                'height': 1.8, 
                'rotation': 90, 
                'style': 'KP_TEXT_STYLE',
                'layer': 'KOP_TEXT'
            }).set_placement((x_pos, y_bottom + H_ROW/2), align=TextEntityAlignment.MIDDLE_CENTER)

        # Kita hanya menulis data di titik AWAL setiap segmen (Stationing)
        # Grid Vertikal
        msp.add_line((x_awal, min_y_band), (x_awal, max(y_tanah_awal, y_tanggul_awal) + 5), dxfattribs={'layer': 'KOP_GRID', 'linetype': 'DOT'})

        # Isi Teks
        add_band_text(f"{row['STA Awal']:.0f}", x_awal, bands['JARAK']['y'])
        add_band_text(f"{z_tanah_awal:.2f}", x_awal, bands['ELV_TANAH']['y'])
        add_band_text(f"{row['Elv Dasar Awal']:.2f}", x_awal, bands['ELV_DESAIN']['y'])
        add_band_text(f"{(row['Elv Dasar Awal'] + row['Tinggi Air (y)']):.2f}", x_awal, bands['ELV_AIR']['y'])
        
        # Dimensi ditulis di tengah bentang
        x_mid = (x_awal + x_akhir) / 2
        dim_txt = f"b={row['Lebar (b)']}\nh={row['Tinggi Total (h)']}"
        msp.add_text(dim_txt, dxfattribs={'height': 1.5, 'layer': 'KOP_TEXT'}).set_placement(
            (x_mid, bands['DIMENSI']['y'] + H_ROW/2), align=TextEntityAlignment.MIDDLE_CENTER)

        # Update tracking variables
        prev_x = x_akhir
        prev_y_dasar = y_dasar_akhir

    # Penutup di STA Akhir
    msp.add_line((x_akhir, min_y_band), (x_akhir, max(y_tanah_akhir, y_tanggul_akhir) + 5), dxfattribs={'layer': 'KOP_GRID', 'linetype': 'DOT'})
    add_band_text(f"{row['STA Akhir']:.0f}", x_akhir, bands['JARAK']['y'])
    add_band_text(f"{z_tanah_akhir:.2f}", x_akhir, bands['ELV_TANAH']['y'])
    add_band_text(f"{row['Elv Dasar Akhir']:.2f}", x_akhir, bands['ELV_DESAIN']['y'])
    add_band_text(f"{(row['Elv Dasar Akhir'] + row['Tinggi Air (y)']):.2f}", x_akhir, bands['ELV_AIR']['y'])

    return doc
