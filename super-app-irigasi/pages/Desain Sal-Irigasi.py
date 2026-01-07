import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io

# Coba import ezdxf, jika belum diinstall beri peringatan nanti
try:
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False

# ==========================================
# 1. FUNGSI PERHITUNGAN HIDROLIS (STANDAR KP-03)
# ==========================================

def get_freeboard_kp03(Q):
    """Menghitung Tinggi Jagaan sesuai KP-03"""
    if Q < 0.5: return 0.20
    elif Q < 1.5: return 0.20
    elif Q < 5.0: return 0.25
    elif Q < 10.0: return 0.30
    elif Q < 15.0: return 0.40
    else: return 0.50

def solve_strickler_y(Q, b, m, k, S):
    """Menghitung tinggi muka air (y) dengan Rumus STRICKLER"""
    if Q <= 0 or b <= 0 or S <= 0: return 0.0
    
    y = 0.5 
    for _ in range(50):
        A = (b + m * y) * y
        P = b + 2 * y * np.sqrt(1 + m**2)
        R = A / P if P > 0 else 0
        Q_calc = A * k * (R**(2/3)) * (S**0.5)
        
        if abs(Q_calc - Q) < 0.0001: break
        
        if Q_calc == 0: y += 0.1
        else: y = y * (Q / Q_calc) ** 0.6
    return y

def cek_keamanan_desain(Q, b, m, y, k, S):
    """Audit keamanan desain (Froude & Kecepatan)"""
    A = (b + m * y) * y
    V = Q / A if A > 0 else 0
    
    T = b + 2 * m * y
    D = A / T if T > 0 else 0 
    g = 9.81
    Fr = V / np.sqrt(g * D) if D > 0 else 0
    
    warnings = []
    status = "AMAN"
    
    # Cek Froude
    if Fr >= 1.0:
        warnings.append(f"BAHAYA: Superkritis (Fr={Fr:.2f})")
        status = "KRITIS"
    elif Fr > 0.5:
        warnings.append(f"Info: Mendekati Kritis (Fr={Fr:.2f})")

    # Cek Kecepatan
    v_max = 2.0 if k >= 60 else 0.7
    v_min = 0.6
    
    if V > v_max:
        warnings.append(f"EROSI: V ({V:.2f}) > {v_max}")
        if status != "KRITIS": status = "TIDAK AMAN"
    elif V < v_min:
        warnings.append(f"ENDAPAN: V ({V:.2f}) < {v_min}")
        if status == "AMAN": status = "PERHATIAN"
        
    return V, Fr, status, "; ".join(warnings)

# ==========================================
# 2. FUNGSI VISUALISASI & CAD (DXF)
# ==========================================

def gambar_penampang_saluran(row):
    """Visualisasi Cross Section (Matplotlib)"""
    b, m = row['Lebar (b)'], row['Talud (m)']
    h_total, y_air = row['Tinggi Total (h)'], row['Tinggi Air (y)']
    nama = row['Nama Saluran']
    
    fig, ax = plt.subplots(figsize=(7, 4))
    
    x_talud_total = m * h_total
    x_talud_air = m * y_air
    
    # Koordinat Dinding
    p1 = (0, h_total)
    p2 = (x_talud_total, 0)
    p3 = (x_talud_total + b, 0)
    p4 = (x_talud_total + b + x_talud_total, h_total)
    
    color_wall = 'red' if row['Status'] == 'KRITIS' else '#333'
    ax.add_patch(patches.Polygon([p1, p2, p3, p4], closed=False, edgecolor=color_wall, facecolor='none', linewidth=3))
    
    # Air
    wa1 = (x_talud_total - x_talud_air, y_air)
    wa2 = (x_talud_total, 0)
    wa3 = (x_talud_total + b, 0)
    wa4 = (x_talud_total + b + x_talud_air, y_air)
    ax.add_patch(patches.Polygon([wa1, wa2, wa3, wa4], closed=True, color='#00BFFF', alpha=0.6))
    
    # Garis Tanah
    ax.plot([-1, 0], [h_total, h_total], 'k--', lw=1)
    ax.plot([p4[0], p4[0]+1], [h_total, h_total], 'k--', lw=1)

    ax.text(x_talud_total + b/2, y_air/2, f"V={row['Kecepatan (V)']} m/s\nFr={row['Froude (Fr)']}", ha='center', color='white', fontweight='bold', fontsize=9)
    ax.set_title(f"Penampang: {nama}")
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_ylim(-0.2, h_total * 1.3); ax.set_xlim(-1, p4[0]+1)
    return fig

def gambar_profil_memanjang(df_hasil):
    """Visualisasi Long Section (Matplotlib)"""
    fig, ax = plt.subplots(figsize=(10, 4))
    
    stas, elvs_dasar, elvs_air, elvs_tanggul = [], [], [], []
    
    for i, row in df_hasil.iterrows():
        stas.extend([row['STA Awal'], row['STA Akhir']])
        elvs_dasar.extend([row['Elv Dasar Awal'], row['Elv Dasar Akhir']])
        elvs_air.extend([row['Elv Dasar Awal'] + row['Tinggi Air (y)'], row['Elv Dasar Akhir'] + row['Tinggi Air (y)']])
        elvs_tanggul.extend([row['Elv Dasar Awal'] + row['Tinggi Total (h)'], row['Elv Dasar Akhir'] + row['Tinggi Total (h)']])

    ax.plot(stas, elvs_tanggul, 'k--', label='Tanggul', alpha=0.5)
    ax.plot(stas, elvs_dasar, color='brown', linewidth=2, label='Dasar')
    ax.plot(stas, elvs_air, color='blue', linewidth=1, label='Muka Air')
    ax.fill_between(stas, elvs_dasar, elvs_air, color='cyan', alpha=0.3)
    
    ax.set_xlabel("Stationing (m)")
    ax.set_ylabel("Elevasi (+m)")
    ax.set_title("Profil Memanjang", fontweight='bold')
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.5)
    return fig

def generate_dxf_kp07(df_hasil):
    """Generate File DXF sesuai KP-07"""
    if not EZDXF_AVAILABLE:
        return None

    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # Layers
    doc.layers.add(name='GRID', color=8, linetype='DOT')
    doc.layers.add(name='TANAH_ASLI', color=3, linetype='DASHED') 
    doc.layers.add(name='DESAIN_SALURAN', color=4) 
    doc.layers.add(name='MUKA_AIR', color=5, linetype='DASHDOT') 
    doc.layers.add(name='TEKS', color=7)
    doc.layers.add(name='KOP_TABEL', color=7)

    SCALE_X, SCALE_Y = 1.0, 10.0
    
    # Posisi Band
    Y_BAND_STA = -20
    Y_BAND_ELV_TANAH = -30
    Y_BAND_ELV_DESAIN = -40
    Y_BAND_ELV_AIR = -50
    Y_BAND_DIMENSI = -60
    
    # Garis Tabel
    max_x = df_hasil['STA Akhir'].max() * SCALE_X
    for y in [Y_BAND_STA, Y_BAND_ELV_TANAH, Y_BAND_ELV_DESAIN, Y_BAND_ELV_AIR, Y_BAND_DIMENSI]:
        msp.add_line((0, y), (max_x, y), dxfattribs={'layer': 'KOP_TABEL'})
        
    # Label Kiri
    msp.add_text("STATION", height=2).set_placement((-2, Y_BAND_STA + 2), align=TextEntityAlignment.MIDDLE_RIGHT)
    msp.add_text("ELV. TANAH", height=2).set_placement((-2, Y_BAND_ELV_TANAH + 2), align=TextEntityAlignment.MIDDLE_RIGHT)
    msp.add_text("ELV. DESAIN", height=2).set_placement((-2, Y_BAND_ELV_DESAIN + 2), align=TextEntityAlignment.MIDDLE_RIGHT)

    prev_x = None
    prev_y_dasar = None
    prev_y_tanah = None
    
    for i, row in df_hasil.iterrows():
        x_awal = row['STA Awal'] * SCALE_X
        x_akhir = row['STA Akhir'] * SCALE_X
        
        y_dasar_awal = row['Elv Dasar Awal'] * SCALE_Y
        y_dasar_akhir = row['Elv Dasar Akhir'] * SCALE_Y
        y_air_awal = (row['Elv Dasar Awal'] + row['Tinggi Air (y)']) * SCALE_Y
        y_air_akhir = (row['Elv Dasar Akhir'] + row['Tinggi Air (y)']) * SCALE_Y
        
        # Asumsi Tanah
        elv_tanah_awal = row['Elv Dasar Awal'] + row['Tinggi Total (h)'] + 0.2
        elv_tanah_akhir = row['Elv Dasar Akhir'] + row['Tinggi Total (h)'] + 0.2
        y_tanah_awal = elv_tanah_awal * SCALE_Y
        y_tanah_akhir = elv_tanah_akhir * SCALE_Y
        
        # Gambar Garis
        msp.add_line((x_awal, y_dasar_awal), (x_akhir, y_dasar_akhir), dxfattribs={'layer': 'DESAIN_SALURAN', 'lw': 50})
        msp.add_line((x_awal, y_air_awal), (x_akhir, y_air_akhir), dxfattribs={'layer': 'MUKA_AIR'})
        msp.add_line((x_awal, y_tanah_awal), (x_akhir, y_tanah_akhir), dxfattribs={'layer': 'TANAH_ASLI'})
        
        # Drop Structure (Terjunan)
        if prev_x is not None:
             msp.add_line((prev_x, prev_y_dasar), (x_awal, y_dasar_awal), dxfattribs={'layer': 'DESAIN_SALURAN'})
             msp.add_line((prev_x, prev_y_tanah), (x_awal, y_tanah_awal), dxfattribs={'layer': 'TANAH_ASLI'})
        
        # Teks Data
        def add_text(txt, x, y):
            msp.add_text(txt, height=1.5, rotation=90).set_placement((x, y+1), align=TextEntityAlignment.MIDDLE_CENTER)

        add_text(f"{row['STA Awal']:.1f}", x_awal, Y_BAND_STA)
        add_text(f"{elv_tanah_awal:.2f}", x_awal, Y_BAND_ELV_TANAH)
        add_text(f"{row['Elv Dasar Awal']:.2f}", x_awal, Y_BAND_ELV_DESAIN)
        
        msp.add_line((x_awal, Y_BAND_DIMENSI), (x_awal, max(y_tanah_awal, y_tanah_akhir)), dxfattribs={'layer': 'GRID'})

        prev_x = x_akhir
        prev_y_dasar = y_dasar_akhir
        prev_y_tanah = y_tanah_akhir

    # Akhiran
    msp.add_line((x_akhir, Y_BAND_DIMENSI), (x_akhir, max(y_tanah_awal, y_tanah_akhir)), dxfattribs={'layer': 'GRID'})
    add_text(f"{row['STA Akhir']:.1f}", x_akhir, Y_BAND_STA)
    
    return doc

# ==========================================
# 3. SETUP HALAMAN & SIDEBAR
# ==========================================

st.set_page_config(page_title="Desain Irigasi KP-03", layout="wide")
st.title("🛠️ Desain Irigasi: Standar KP-03")
st.markdown("---")

with st.sidebar:
    st.header("1. Konfigurasi Trase")
    start_sta = st.number_input("STA Awal (m)", value=0.0)
    start_elv = st.number_input("Elevasi Awal (+m)", value=100.00)
    
    st.divider()
    st.header("📂 Menu File")
    
    # Template
    df_template = pd.DataFrame({
        'Nama Saluran': ['Saluran 1', 'Saluran 2'],
        'Panjang (m)': [50.0, 50.0],
        'Offset (m)': [-0.10, -0.50],
        'Debit (Q)': [1.5, 2.0], 
        'Lebar (b)': [1.0, 1.2], 
        'Talud (m)': [1.0, 1.0], 
        'Slope (S)': [0.001, 0.001], 
        'Strickler (k)': [60, 40]
    })
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer) as writer: df_template.to_excel(writer, index=False)
    st.download_button("📥 Download Template Excel", buffer.getvalue(), "template_irigasi_kp03.xlsx")
    
    # Upload
    uploaded_file = st.file_uploader("Upload Data Excel", type=['xlsx'])
    if uploaded_file:
        try:
            df_uploaded = pd.read_excel(uploaded_file)
            required = ['Nama Saluran', 'Panjang (m)', 'Debit (Q)', 'Lebar (b)', 'Slope (S)', 'Strickler (k)']
            if all(col in df_uploaded.columns for col in required):
                st.session_state.df_input = df_uploaded
                st.success("✅ Data Excel berhasil dimuat!")
            else:
                st.error("❌ Format Excel salah! Pastikan kolom lengkap.")
        except Exception as e:
            st.error(f"Gagal membaca file: {e}")

    st.info("**Referensi k:**\n* Batu: 60\n* Beton: 70\n* Tanah: 40")

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
        'Strickler (k)': [60, 60]
    }
    st.session_state.df_input = pd.DataFrame(data_awal)

st.subheader("1. Input Data Desain")
edited_df = st.data_editor(st.session_state.df_input, num_rows="dynamic", hide_index=True)

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
        L, Q, b, m = row['Panjang (m)'], row['Debit (Q)'], row['Lebar (b)'], row['Talud (m)']
        S, k, offset = row['Slope (S)'], row['Strickler (k)'], row['Offset (m)']
        
        y_calc = solve_strickler_y(Q, b, m, k, S)
        w_calc = get_freeboard_kp03(Q)
        h_calc = y_calc + w_calc
        V_calc, Fr_calc, status, pesan = cek_keamanan_desain(Q, b, m, y_calc, k, S)
        
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
        curr_sta += L
        curr_elv = elv_akhir + offset

    st.session_state.df_hasil = pd.DataFrame(hasil_list)
    
    if any(x in ['KRITIS', 'TIDAK AMAN'] for x in st.session_state.df_hasil['Status']):
        st.error("⚠️ Desain TIDAK MEMENUHI kriteria KP-03.")
    else:
        st.success("✅ Semua saluran AMAN.")

# ==========================================
# 6. OUTPUT & LAPORAN
# ==========================================

if 'df_hasil' in st.session_state:
    df_res = st.session_state.df_hasil
    
    st.divider()
    st.subheader("2. Hasil Analisis Hidrolis")
    
    # Tabel
    def highlight_status(val):
        color = 'red' if val == 'KRITIS' else 'orange' if val == 'TIDAK AMAN' else 'green'
        return f'color: {color}; font-weight: bold'

    st.dataframe(df_res.style.map(highlight_status, subset=['Status']), use_container_width=True, hide_index=True)
    
    # Grafik (Kolom 1 & 2)
    col_g1, col_g2 = st.columns([2, 1])
    
    with col_g1:
        st.subheader("3. Profil Memanjang")
        st.pyplot(gambar_profil_memanjang(df_res))
        
    with col_g2:
        st.subheader("4. Detail Penampang")
        pilih_sal = st.selectbox("Pilih Saluran:", df_res['Nama Saluran'])
        if pilih_sal:
            row_vis = df_res[df_res['Nama Saluran'] == pilih_sal].iloc[0]
            st.pyplot(gambar_penampang_saluran(row_vis))
            st.info(f"V: {row_vis['Kecepatan (V)']} m/s | Fr: {row_vis['Froude (Fr)']}")

    st.divider()
    st.subheader("5. Ekspor Data")
    
    col_d1, col_d2 = st.columns(2)
    
    # Tombol Download Excel
    with col_d1:
        output = io.BytesIO()
        with pd.ExcelWriter(output) as writer: 
            df_res.to_excel(writer, sheet_name='Rekap', index=False)
            st.session_state.df_input.to_excel(writer, sheet_name='Input', index=False)
        st.download_button("💾 Download Excel (.xlsx)", output.getvalue(), "Laporan_Irigasi.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    # Tombol Download DXF
    with col_d2:
        if EZDXF_AVAILABLE:
            try:
                doc_dxf = generate_dxf_kp07(df_res)
                if doc_dxf:
                    output_dxf = io.BytesIO()
                    doc_dxf.write(output_dxf)
                    st.download_button("📐 Download CAD (.dxf)", output_dxf.getvalue(), "LongSection_KP07.dxf", "application/dxf", type="primary", use_container_width=True)
            except Exception as e:
                st.error(f"Error DXF: {e}")
        else:
            st.warning("Library 'ezdxf' belum terinstall. Jalankan 'pip install ezdxf' di terminal.")
