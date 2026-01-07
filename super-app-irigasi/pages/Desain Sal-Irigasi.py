import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io

# ==========================================
# 1. FUNGSI PERHITUNGAN HIDROLIS (STANDAR KP-03)
# ==========================================

def get_freeboard_kp03(Q):
    """
    Menghitung Tinggi Jagaan (Freeboard) sesuai Tabel KP-03.
    Q dalam m3/dt, Output W dalam meter.
    """
    if Q < 0.5: return 0.20
    elif Q < 1.5: return 0.20
    elif Q < 5.0: return 0.25
    elif Q < 10.0: return 0.30
    elif Q < 15.0: return 0.40
    else: return 0.50

def solve_strickler_y(Q, b, m, k, S):
    """
    Menghitung tinggi muka air (y) dengan Rumus STRICKLER (KP-03).
    V = k * R^(2/3) * I^(1/2)
    """
    if Q <= 0 or b <= 0 or S <= 0: return 0.0
    
    y = 0.5 # Tebakan awal
    # Iterasi Newton-Raphson untuk konvergensi cepat
    for _ in range(50):
        A = (b + m * y) * y
        P = b + 2 * y * np.sqrt(1 + m**2)
        R = A / P if P > 0 else 0
        
        # Rumus Debit Strickler: Q = A * V
        # Q = A * k * R^(2/3) * S^(0.5)
        Q_calc = A * k * (R**(2/3)) * (S**0.5)
        
        if abs(Q_calc - Q) < 0.0001: break
        
        # Adjustment step
        if Q_calc == 0: y += 0.1
        else: y = y * (Q / Q_calc) ** 0.6
        
    return y

def cek_keamanan_desain(Q, b, m, y, k, S):
    """
    Audit keamanan desain berdasarkan kecepatan dan Bilangan Froude.
    """
    A = (b + m * y) * y
    V = Q / A if A > 0 else 0
    
    # 1. Hitung Froude Number (Fr) untuk cek aliran kritis
    # Lebar muka air atas (T)
    T = b + 2 * m * y
    D = A / T if T > 0 else 0 # Hydraulic Depth
    g = 9.81
    Fr = V / np.sqrt(g * D) if D > 0 else 0
    
    warnings = []
    status = "AMAN"
    
    # Cek 1: Froude (Stabilitas Aliran)
    if Fr >= 1.0:
        warnings.append(f"BAHAYA: Superkritis (Fr={Fr:.2f}). Loncatan air!")
        status = "KRITIS"
    elif Fr > 0.5:
        warnings.append(f"Info: Mendekati Kritis (Fr={Fr:.2f}).")

    # Cek 2: Kecepatan (Erosi & Sedimen)
    # Batas kecepatan (Asumsi k>=60 adalah Pasangan, k<60 Tanah)
    v_max = 2.0 if k >= 60 else 0.7
    v_min = 0.6
    
    if V > v_max:
        warnings.append(f"EROSI: V ({V:.2f}) > Izin ({v_max}).")
        if status != "KRITIS": status = "TIDAK AMAN"
    elif V < v_min:
        warnings.append(f"ENDAPAN: V ({V:.2f}) < Min ({v_min}).")
        if status == "AMAN": status = "PERHATIAN"
        
    return V, Fr, status, "; ".join(warnings)

# ==========================================
# 2. FUNGSI VISUALISASI
# ==========================================

def gambar_penampang_saluran(row):
    """Visualisasi Potongan Melintang"""
    b, m = row['Lebar (b)'], row['Talud (m)']
    h_total, y_air = row['Tinggi Total (h)'], row['Tinggi Air (y)']
    nama = row['Nama Saluran']
    
    fig, ax = plt.subplots(figsize=(7, 4))
    
    # Geometri
    x_talud_total = m * h_total
    x_talud_air = m * y_air
    
    # Koordinat Dinding
    p1 = (0, h_total)
    p2 = (x_talud_total, 0)
    p3 = (x_talud_total + b, 0)
    p4 = (x_talud_total + b + x_talud_total, h_total)
    
    # Gambar Dinding
    color_wall = 'red' if row['Status'] == 'KRITIS' else '#333'
    ax.add_patch(patches.Polygon([p1, p2, p3, p4], closed=False, edgecolor=color_wall, facecolor='none', linewidth=3))
    
    # Gambar Air
    wa1 = (x_talud_total - x_talud_air, y_air)
    wa2 = (x_talud_total, 0)
    wa3 = (x_talud_total + b, 0)
    wa4 = (x_talud_total + b + x_talud_air, y_air)
    ax.add_patch(patches.Polygon([wa1, wa2, wa3, wa4], closed=True, color='#00BFFF', alpha=0.6))
    
    # Garis Tanah
    ax.plot([-1, 0], [h_total, h_total], 'k--', lw=1)
    ax.plot([p4[0], p4[0]+1], [h_total, h_total], 'k--', lw=1)

    # Label
    ax.text(x_talud_total + b/2, y_air/2, f"V={row['Kecepatan (V)']} m/s\nFr={row['Froude (Fr)']}", ha='center', color='white', fontweight='bold', fontsize=9)
    ax.set_title(f"Penampang: {nama} ({row['Status']})")
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_ylim(-0.2, h_total * 1.3); ax.set_xlim(-1, p4[0]+1)
    return fig

def gambar_profil_memanjang(df_hasil):
    """Visualisasi Long Section"""
    fig, ax = plt.subplots(figsize=(10, 4))
    
    stas = []
    elvs_dasar = []
    elvs_air = []
    elvs_tanggul = []
    
    for i, row in df_hasil.iterrows():
        stas.extend([row['STA Awal'], row['STA Akhir']])
        elvs_dasar.extend([row['Elv Dasar Awal'], row['Elv Dasar Akhir']])
        elvs_air.extend([row['Elv Dasar Awal'] + row['Tinggi Air (y)'], row['Elv Dasar Akhir'] + row['Tinggi Air (y)']])
        elvs_tanggul.extend([row['Elv Dasar Awal'] + row['Tinggi Total (h)'], row['Elv Dasar Akhir'] + row['Tinggi Total (h)']])

    ax.plot(stas, elvs_tanggul, 'k--', label='Tanggul Jagaan', alpha=0.5)
    ax.plot(stas, elvs_dasar, color='brown', linewidth=2, label='Dasar Saluran')
    ax.plot(stas, elvs_air, color='blue', linewidth=1, label='Muka Air')
    ax.fill_between(stas, elvs_dasar, elvs_air, color='cyan', alpha=0.3)
    
    ax.set_xlabel("Stationing (m)")
    ax.set_ylabel("Elevasi (+m)")
    ax.set_title("Profil Memanjang (Long Section)", fontweight='bold')
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.5)
    return fig

# ==========================================
# 3. SETUP HALAMAN & SIDEBAR
# ==========================================

st.set_page_config(page_title="Desain Irigasi KP-03", layout="wide")
st.title("🛠️ Desain Irigasi: Standar KP-03")
st.markdown("---")

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
    
    # 2. UPLOAD EXCEL (Fitur Upload)
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
                st.error("❌ Format Excel salah! Pastikan ada kolom 'Strickler (k)'.")
        except Exception as e:
            st.error(f"Gagal membaca file: {e}")

    st.info("""
    **Referensi Nilai k (Strickler):**
    * Pasangan Batu: **60**
    * Beton: **70**
    * Tanah Bersih: **40**
    """)

# ==========================================
# 4. DATA EDITOR
# ==========================================

if 'df_input' not in st.session_state:
    data_awal = {
        'Nama Saluran': ['Saluran A', 'Saluran B'],
        'Panjang (m)': [50.0, 50.0],
        'Offset (m)': [-0.50, -0.50],
        'Debit (Q)': [2.00, 2.00],
        'Lebar (b)': [1.00, 1.20],
        'Talud (m)': [1.0, 1.0],
        'Slope (S)': [0.001, 0.0015], 
        'Strickler (k)': [60, 60] # Default Batu Kali
    }
    st.session_state.df_input = pd.DataFrame(data_awal)

st.subheader("1. Input Data Desain")
st.caption("Gunakan **Offset negatif** (misal -0.50) untuk terjunan/drop.")

edited_df = st.data_editor(
    st.session_state.df_input,
    num_rows="dynamic",
    column_config={
        "Panjang (m)": st.column_config.NumberColumn(format="%.1f"),
        "Offset (m)": st.column_config.NumberColumn(format="%.2f", help="Beda tinggi lantai ke segmen berikutnya"),
        "Debit (Q)": st.column_config.NumberColumn(format="%.3f"),
        "Slope (S)": st.column_config.NumberColumn(format="%.5f"),
        "Strickler (k)": st.column_config.NumberColumn(min_value=20, max_value=100, step=1, help="Nilai kekasaran Strickler (KP-03)"),
    },
    hide_index=True
)

if not edited_df.equals(st.session_state.df_input):
    st.session_state.df_input = edited_df

# ==========================================
# 5. EKSEKUSI PERHITUNGAN
# ==========================================

btn_run = st.button("▶️ HITUNG & VERIFIKASI (RUN)", type="primary", use_container_width=True)

if btn_run:
    hasil_list = []
    curr_sta = start_sta
    curr_elv = start_elv
    
    for idx, row in edited_df.iterrows():
        # Input
        L, Q, b, m = row['Panjang (m)'], row['Debit (Q)'], row['Lebar (b)'], row['Talud (m)']
        S, k, offset = row['Slope (S)'], row['Strickler (k)'], row['Offset (m)']
        
        # 1. Hitung Hidrolis (Strickler)
        y_calc = solve_strickler_y(Q, b, m, k, S)
        w_calc = get_freeboard_kp03(Q)
        h_calc = y_calc + w_calc
        
        # 2. Cek Keamanan (Verifikasi KP-03)
        V_calc, Fr_calc, status, pesan = cek_keamanan_desain(Q, b, m, y_calc, k, S)
        
        # 3. Hitung Elevasi
        elv_awal = curr_elv
        elv_akhir = elv_awal - (L * S)
        
        hasil_list.append({
            'Nama Saluran': row['Nama Saluran'],
            'Status': status,
            'Peringatan': pesan,
            'STA Awal': round(curr_sta, 1),
            'STA Akhir': round(curr_sta + L, 1),
            'Elv Dasar Awal': round(elv_awal, 3),
            'Elv Dasar Akhir': round(elv_akhir, 3),
            'Tinggi Air (y)': round(y_calc, 3),
            'Tinggi Total (h)': round(h_calc, 2),
            'Kecepatan (V)': round(V_calc, 2),
            'Froude (Fr)': round(Fr_calc, 2),
            'Strickler (k)': k, 'Lebar (b)': b, 'Talud (m)': m
        })
        
        # Update Loop
        curr_sta += L
        curr_elv = elv_akhir + offset

    st.session_state.df_hasil = pd.DataFrame(hasil_list)
    
    # Cek Global Status
    if any(x in ['KRITIS', 'TIDAK AMAN'] for x in st.session_state.df_hasil['Status']):
        st.error("⚠️ Ditemukan desain yang TIDAK MEMENUHI kriteria KP-03. Periksa tabel di bawah.")
    else:
        st.success("✅ Semua saluran memenuhi kriteria hidrolis KP-03.")

# ==========================================
# 6. OUTPUT & LAPORAN
# ==========================================

if 'df_hasil' in st.session_state:
    df_res = st.session_state.df_hasil
    
    st.divider()
    st.subheader("2. Hasil Analisis Hidrolis")
    
    # Styling Tabel
    def highlight_status(val):
        color = 'red' if val == 'KRITIS' else 'orange' if val == 'TIDAK AMAN' else 'green'
        return f'color: {color}; font-weight: bold'

    st.dataframe(
        df_res.style.map(highlight_status, subset=['Status']),
        column_config={
            "Peringatan": st.column_config.TextColumn(width="large"),
            "Froude (Fr)": st.column_config.NumberColumn(help="Harus < 1.0 (Subkritis)"),
        },
        use_container_width=True, hide_index=True
    )
    
    col_g1, col_g2 = st.columns([2, 1])
    
    with col_g1:
        st.subheader("3. Profil Memanjang")
        st.pyplot(gambar_profil_memanjang(df_res))
        import ezdxf
from ezdxf.enums import TextEntityAlignment

def generate_dxf_kp07(df_hasil):
    """
    Menggenerate file DXF sesuai standar KP-07 (Bab V Laporan).
    Fitur:
    1. Layers (Grid, Tanah, Desain, Air, Teks)
    2. Profil Memanjang (Long Section) dengan Skala Distorsi Vertikal 10x
    3. Kop Tabel Data (Bands) di bawah grafik
    """
    # 1. Inisialisasi Canvas (Bab 5.2)
    doc = ezdxf.new('R2010') # Versi CAD yang umum
    msp = doc.modelspace()
    
    # Setup Layers Sesuai KP-07
    # Warna: 1=Red, 2=Yellow, 3=Green, 4=Cyan, 5=Blue, 7=White/Black, 8=Gray
    doc.layers.add(name='GRID', color=8, linetype='DOT')
    doc.layers.add(name='TANAH_ASLI', color=3, linetype='DASHED') 
    doc.layers.add(name='DESAIN_SALURAN', color=4) # Cyan (Continuous)
    doc.layers.add(name='MUKA_AIR', color=5, linetype='DASHDOT') 
    doc.layers.add(name='TEKS', color=7)
    doc.layers.add(name='KOP_TABEL', color=7)

    # Konfigurasi Skala & Layout
    SCALE_X = 1.0    # 1:1000 atau 1:2000 horizontal
    SCALE_Y = 10.0   # Distorsi Vertikal 10x (Standar Irigasi)
    DATUM_Y = 0.0    # Titik 0,0 grafik
    
    # Posisi Baris Tabel (Bands) di bawah grafik (koordinat Y negatif)
    Y_BAND_STA = -20
    Y_BAND_ELV_TANAH = -30
    Y_BAND_ELV_DESAIN = -40
    Y_BAND_ELV_AIR = -50
    Y_BAND_DIMENSI = -60
    
    # Buat Garis Grid Horizontal untuk Tabel
    for y in [Y_BAND_STA, Y_BAND_ELV_TANAH, Y_BAND_ELV_DESAIN, Y_BAND_ELV_AIR, Y_BAND_DIMENSI]:
        msp.add_line((0, y), (df_hasil['STA Akhir'].max() * SCALE_X, y), dxfattribs={'layer': 'KOP_TABEL'})
        
    # Label Judul Baris (Kiri)
    msp.add_text("STATION", height=2).set_placement((-2, Y_BAND_STA + 2), align=TextEntityAlignment.MIDDLE_RIGHT)
    msp.add_text("ELV. TANAH", height=2).set_placement((-2, Y_BAND_ELV_TANAH + 2), align=TextEntityAlignment.MIDDLE_RIGHT)
    msp.add_text("ELV. DESAIN", height=2).set_placement((-2, Y_BAND_ELV_DESAIN + 2), align=TextEntityAlignment.MIDDLE_RIGHT)
    msp.add_text("MUKA AIR", height=2).set_placement((-2, Y_BAND_ELV_AIR + 2), align=TextEntityAlignment.MIDDLE_RIGHT)

    # === LOOPING DATA STASIUN (Bab 5.2) ===
    prev_x = None
    prev_y_dasar = None
    prev_y_air = None
    prev_y_tanah = None
    
    for i, row in df_hasil.iterrows():
        # Koordinat X
        x_awal = row['STA Awal'] * SCALE_X
        x_akhir = row['STA Akhir'] * SCALE_X
        
        # Koordinat Y (Elevasi * Distorsi)
        y_dasar_awal = row['Elv Dasar Awal'] * SCALE_Y
        y_dasar_akhir = row['Elv Dasar Akhir'] * SCALE_Y
        
        y_air_awal = (row['Elv Dasar Awal'] + row['Tinggi Air (y)']) * SCALE_Y
        y_air_akhir = (row['Elv Dasar Akhir'] + row['Tinggi Air (y)']) * SCALE_Y
        
        # Asumsi Tanah Asli (Karena input terbatas, kita simulasikan Tanah = Tanggul + 0.2m)
        elv_tanah_awal = row['Elv Dasar Awal'] + row['Tinggi Total (h)'] + 0.2
        elv_tanah_akhir = row['Elv Dasar Akhir'] + row['Tinggi Total (h)'] + 0.2
        y_tanah_awal = elv_tanah_awal * SCALE_Y
        y_tanah_akhir = elv_tanah_akhir * SCALE_Y
        
        # 1. GAMBAR GARIS PROFIL
        # Garis Dasar (Cyan)
        msp.add_line((x_awal, y_dasar_awal), (x_akhir, y_dasar_akhir), dxfattribs={'layer': 'DESAIN_SALURAN', 'lw': 50})
        # Garis Air (Biru Dashdot)
        msp.add_line((x_awal, y_air_awal), (x_akhir, y_air_akhir), dxfattribs={'layer': 'MUKA_AIR'})
        # Garis Tanah (Hijau Dashed)
        msp.add_line((x_awal, y_tanah_awal), (x_akhir, y_tanah_akhir), dxfattribs={'layer': 'TANAH_ASLI'})
        
        # Hubungkan segmen putus (Vertical Drop jika ada terjunan)
        if prev_x is not None:
             msp.add_line((prev_x, prev_y_dasar), (x_awal, y_dasar_awal), dxfattribs={'layer': 'DESAIN_SALURAN'}) # Drop Walls
             msp.add_line((prev_x, prev_y_tanah), (x_awal, y_tanah_awal), dxfattribs={'layer': 'TANAH_ASLI'})
        
        # 2. GENERASI KOLOM DATA (TEXT VERTIKAL)
        # Fungsi helper untuk nulis teks vertikal di kolom
        def add_band_text(text, x_pos, y_base):
            msp.add_text(text, height=1.5, rotation=90).set_placement(
                (x_pos, y_base + 1), align=TextEntityAlignment.MIDDLE_CENTER
            )

        # Tulis data di Titik Awal segmen
        add_band_text(f"{row['STA Awal']:.1f}", x_awal, Y_BAND_STA)
        add_band_text(f"{elv_tanah_awal:.2f}", x_awal, Y_BAND_ELV_TANAH)
        add_band_text(f"{row['Elv Dasar Awal']:.2f}", x_awal, Y_BAND_ELV_DESAIN)
        add_band_text(f"{(row['Elv Dasar Awal']+row['Tinggi Air (y)']):.2f}", x_awal, Y_BAND_ELV_AIR)
        
        # Garis Grid Vertikal
        msp.add_line((x_awal, Y_BAND_DIMENSI), (x_awal, max(y_tanah_awal, y_tanah_akhir)), dxfattribs={'layer': 'GRID'})

        # Update Previous Points
        prev_x = x_akhir
        prev_y_dasar = y_dasar_akhir
        prev_y_air = y_air_akhir
        prev_y_tanah = y_tanah_akhir

    # Tulis data titik terakhir
    msp.add_line((x_akhir, Y_BAND_DIMENSI), (x_akhir, max(y_tanah_awal, y_tanah_akhir)), dxfattribs={'layer': 'GRID'})
    add_band_text(f"{row['STA Akhir']:.1f}", x_akhir, Y_BAND_STA)
    add_band_text(f"{elv_tanah_akhir:.2f}", x_akhir, Y_BAND_ELV_TANAH)
    add_band_text(f"{row['Elv Dasar Akhir']:.2f}", x_akhir, Y_BAND_ELV_DESAIN)
    add_band_text(f"{(row['Elv Dasar Akhir']+row['Tinggi Air (y)']):.2f}", x_akhir, Y_BAND_ELV_AIR)

    # Info Dimensi (Horizontal Text di tengah segmen)
    msp.add_text(f"b={row['Lebar (b)']} m\nh={row['Tinggi Total (h)']} m", height=1.5).set_placement(
        ((x_awal+x_akhir)/2, Y_BAND_DIMENSI + 4), align=TextEntityAlignment.MIDDLE_CENTER
    )

    return doc
        
    with col_g2:
        st.subheader("4. Detail Penampang")
        pilih_sal = st.selectbox("Pilih Saluran:", df_res['Nama Saluran'])
        if pilih_sal:
            row_vis = df_res[df_res['Nama Saluran'] == pilih_sal].iloc[0]
            st.pyplot(gambar_penampang_saluran(row_vis))
            
            # Kartu Info Teknis
            st.info(f"""
            **Analisis {pilih_sal}:**
            - Kecepatan: {row_vis['Kecepatan (V)']} m/s
            - Froude: {row_vis['Froude (Fr)']}
            - **Status: {row_vis['Status']}**
            """)

    st.divider()
    st.subheader("5. Simpan Laporan")
    
    # TOMBOL DOWNLOAD LAPORAN (Fitur Save)
    output = io.BytesIO()
    with pd.ExcelWriter(output) as writer: 
        # Sheet 1: Hasil Rekap
        df_res.to_excel(writer, sheet_name='Rekap Desain', index=False)
        # Sheet 2: Data Input (Untuk referensi)
        st.session_state.df_input.to_excel(writer, sheet_name='Data Input', index=False)
        
    st.download_button(
        label="💾 DOWNLOAD LAPORAN LENGKAP (.xlsx)",
        data=output.getvalue(),
        file_name="Laporan_Desain_Irigasi_KP03.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary", 
        use_container_width=True
    )

