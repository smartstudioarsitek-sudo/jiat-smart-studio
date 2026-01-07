import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io
import math

# --- 1. CONFIG DI PALING ATAS ---
st.set_page_config(page_title="Desain Irigasi KP-03", layout="wide")

# Coba import library ezdxf
try:
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    from ezdxf.tools.standards import setup_linetypes
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False

# ==========================================
# 2. FUNGSI PERHITUNGAN HIDROLIS (STANDAR KP-03)
# ==========================================

def get_freeboard_kp03(Q):
    if Q < 0.5: return 0.20
    elif Q < 1.5: return 0.20
    elif Q < 5.0: return 0.25
    elif Q < 10.0: return 0.30
    elif Q < 15.0: return 0.40
    else: return 0.50

def solve_strickler_y(Q, b, m, k, S):
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
    A = (b + m * y) * y
    V = Q / A if A > 0 else 0
    T = b + 2 * m * y
    D = A / T if T > 0 else 0 
    g = 9.81
    Fr = V / np.sqrt(g * D) if D > 0 else 0
    
    warnings = []
    status = "AMAN"
    
    if Fr >= 1.0:
        warnings.append(f"BAHAYA: Superkritis (Fr={Fr:.2f})")
        status = "KRITIS"
    elif Fr > 0.5:
        warnings.append(f"Info: Mendekati Kritis (Fr={Fr:.2f})")

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
# 3. FUNGSI GENERATE DXF (KP-07 SMART DATUM)
# ==========================================

def generate_dxf_kp07(df_hasil):
    if not EZDXF_AVAILABLE: return None

    doc = ezdxf.new('R2010')
    setup_linetypes(doc)
    msp = doc.modelspace()

    # Setup Layer KP-07
    layers = [
        ('KOP_GRID', 8, 'CONTINUOUS'),      
        ('KOP_TEXT', 7, 'CONTINUOUS'),      
        ('TANAH_ASLI', 3, 'DASHED'),        
        ('DESAIN_DASAR', 1, 'CONTINUOUS'),  
        ('DESAIN_AIR', 5, 'DASHDOT'),       
        ('DESAIN_TANGGUL', 2, 'CONTINUOUS') 
    ]
    for name, color, ltype in layers:
        if name not in doc.layers:
            doc.layers.add(name, color=color, linetype=ltype)

    if 'KP_TEXT_STYLE' not in doc.styles:
        doc.styles.new('KP_TEXT_STYLE', dxfattribs={'font': 'Arial.ttf', 'width': 0.8})

    SCALE_H = 1.0   
    SCALE_V = 10.0  

    # Algoritma Smart Datum
    min_elev_dasar = min(df_hasil['Elv Dasar Awal'].min(), df_hasil['Elv Dasar Akhir'].min())
    datum_reference = np.floor((min_elev_dasar - 2.0) / 5.0) * 5.0
    
    # Layout Bands
    H_ROW = 15
    bands = {
        'JARAK':        {'y': -1 * H_ROW, 'label': 'JARAK (m)'},
        'ELV_TANAH':    {'y': -2 * H_ROW, 'label': 'ELV. TANAH (+m)'},
        'ELV_DESAIN':   {'y': -3 * H_ROW, 'label': 'ELV. DESAIN (+m)'},
        'ELV_AIR':      {'y': -4 * H_ROW, 'label': 'MUKA AIR (+m)'},
        'DIMENSI':      {'y': -5 * H_ROW, 'label': 'DIMENSI'}
    }
    
    min_y_band = bands['DIMENSI']['y']
    max_sta = df_hasil['STA Akhir'].max() * SCALE_H
    
    # Header Bands
    for key, info in bands.items():
        y_pos = info['y']
        msp.add_line((-30, y_pos), (max_sta, y_pos), dxfattribs={'layer': 'KOP_GRID'})
        msp.add_text(info['label'], dxfattribs={'height': 2.5, 'style': 'KP_TEXT_STYLE', 'layer': 'KOP_TEXT'}).set_placement((-2, y_pos + H_ROW/2), align=TextEntityAlignment.MIDDLE_RIGHT)

    msp.add_line((-30, 0), (max_sta, 0), dxfattribs={'layer': 'KOP_GRID', 'lineweight': 30})
    msp.add_text(f"DATUM: +{datum_reference:.2f}", dxfattribs={'height': 2.5, 'layer': 'KOP_TEXT'}).set_placement((-2, 2), align=TextEntityAlignment.MIDDLE_RIGHT)

    prev_x = None
    prev_y_dasar = None
    
    for i, row in df_hasil.iterrows():
        x_awal = row['STA Awal'] * SCALE_H
        x_akhir = row['STA Akhir'] * SCALE_H
        
        y_dasar_awal = (row['Elv Dasar Awal'] - datum_reference) * SCALE_V
        y_dasar_akhir = (row['Elv Dasar Akhir'] - datum_reference) * SCALE_V
        y_air_awal = (row['Elv Dasar Awal'] + row['Tinggi Air (y)'] - datum_reference) * SCALE_V
        y_air_akhir = (row['Elv Dasar Akhir'] + row['Tinggi Air (y)'] - datum_reference) * SCALE_V
        y_tanggul_awal = (row['Elv Dasar Awal'] + row['Tinggi Total (h)'] - datum_reference) * SCALE_V
        y_tanggul_akhir = (row['Elv Dasar Akhir'] + row['Tinggi Total (h)'] - datum_reference) * SCALE_V
        
        z_tanah_awal = row['Elv Dasar Awal'] + row['Tinggi Total (h)'] + 0.3
        z_tanah_akhir = row['Elv Dasar Akhir'] + row['Tinggi Total (h)'] + 0.3
        y_tanah_awal = (z_tanah_awal - datum_reference) * SCALE_V
        y_tanah_akhir = (z_tanah_akhir - datum_reference) * SCALE_V

        msp.add_line((x_awal, y_dasar_awal), (x_akhir, y_dasar_akhir), dxfattribs={'layer': 'DESAIN_DASAR', 'lineweight': 40})
        msp.add_line((x_awal, y_air_awal), (x_akhir, y_air_akhir), dxfattribs={'layer': 'DESAIN_AIR'})
        msp.add_line((x_awal, y_tanggul_awal), (x_akhir, y_tanggul_akhir), dxfattribs={'layer': 'DESAIN_TANGGUL'})
        msp.add_line((x_awal, y_tanah_awal), (x_akhir, y_tanah_akhir), dxfattribs={'layer': 'TANAH_ASLI'})
        
        if prev_x is not None and (abs(prev_y_dasar - y_dasar_awal) > 0.001):
             msp.add_line((prev_x, prev_y_dasar), (x_awal, y_dasar_awal), dxfattribs={'layer': 'DESAIN_DASAR'})

        def add_band_text(txt, x_pos, y_bottom):
            msp.add_text(txt, dxfattribs={'height': 1.8, 'rotation': 90, 'style': 'KP_TEXT_STYLE', 'layer': 'KOP_TEXT'}).set_placement((x_pos, y_bottom + H_ROW/2), align=TextEntityAlignment.MIDDLE_CENTER)

        msp.add_line((x_awal, min_y_band), (x_awal, max(y_tanah_awal, y_tanggul_awal) + 5), dxfattribs={'layer': 'KOP_GRID', 'linetype': 'DOT'})

        add_band_text(f"{row['STA Awal']:.0f}", x_awal, bands['JARAK']['y'])
        add_band_text(f"{z_tanah_awal:.2f}", x_awal, bands['ELV_TANAH']['y'])
        add_band_text(f"{row['Elv Dasar Awal']:.2f}", x_awal, bands['ELV_DESAIN']['y'])
        add_band_text(f"{(row['Elv Dasar Awal'] + row['Tinggi Air (y)']):.2f}", x_awal, bands['ELV_AIR']['y'])
        
        x_mid = (x_awal + x_akhir) / 2
        msp.add_text(f"b={row['Lebar (b)']}\nh={row['Tinggi Total (h)']}", dxfattribs={'height': 1.5, 'layer': 'KOP_TEXT'}).set_placement((x_mid, bands['DIMENSI']['y'] + H_ROW/2), align=TextEntityAlignment.MIDDLE_CENTER)

        prev_x = x_akhir
        prev_y_dasar = y_dasar_akhir

    msp.add_line((x_akhir, min_y_band), (x_akhir, max(y_tanah_akhir, y_tanggul_akhir) + 5), dxfattribs={'layer': 'KOP_GRID', 'linetype': 'DOT'})
    add_band_text(f"{row['STA Akhir']:.0f}", x_akhir, bands['JARAK']['y'])
    add_band_text(f"{z_tanah_akhir:.2f}", x_akhir, bands['ELV_TANAH']['y'])
    add_band_text(f"{row['Elv Dasar Akhir']:.2f}", x_akhir, bands['ELV_DESAIN']['y'])
    add_band_text(f"{(row['Elv Dasar Akhir'] + row['Tinggi Air (y)']):.2f}", x_akhir, bands['ELV_AIR']['y'])

    return doc

def gambar_penampang_saluran(row):
    b, m = row['Lebar (b)'], row['Talud (m)']
    h_total, y_air = row['Tinggi Total (h)'], row['Tinggi Air (y)']
    nama = row['Nama Saluran']
    
    fig, ax = plt.subplots(figsize=(7, 4))
    x_talud_total = m * h_total
    x_talud_air = m * y_air
    
    p1 = (0, h_total)
    p2 = (x_talud_total, 0)
    p3 = (x_talud_total + b, 0)
    p4 = (x_talud_total + b + x_talud_total, h_total)
    
    color_wall = 'red' if row['Status'] == 'KRITIS' else '#333'
    ax.add_patch(patches.Polygon([p1, p2, p3, p4], closed=False, edgecolor=color_wall, facecolor='none', linewidth=3))
    
    wa1 = (x_talud_total - x_talud_air, y_air)
    wa2 = (x_talud_total, 0)
    wa3 = (x_talud_total + b, 0)
    wa4 = (x_talud_total + b + x_talud_air, y_air)
    ax.add_patch(patches.Polygon([wa1, wa2, wa3, wa4], closed=True, color='#00BFFF', alpha=0.6))
    
    ax.plot([-1, 0], [h_total, h_total], 'k--', lw=1)
    ax.plot([p4[0], p4[0]+1], [h_total, h_total], 'k--', lw=1)

    ax.text(x_talud_total + b/2, y_air/2, f"V={row['Kecepatan (V)']} m/s\nFr={row['Froude (Fr)']}", ha='center', color='white', fontweight='bold', fontsize=9)
    ax.set_title(f"Penampang: {nama}")
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_ylim(-0.2, h_total * 1.3); ax.set_xlim(-1, p4[0]+1)
    return fig

def gambar_profil_memanjang(df_hasil):
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
    ax.set_xlabel("Stationing (m)"); ax.set_ylabel("Elevasi (+m)"); ax.set_title("Profil Memanjang", fontweight='bold')
    ax.legend(); ax.grid(True, linestyle='--', alpha=0.5)
    return fig

# ==========================================
# 4. HALAMAN UTAMA & SIDEBAR
# ==========================================

st.title("🛠️ Desain Irigasi: Standar KP-03")
st.markdown("---")

with st.sidebar:
    st.header("1. Konfigurasi Trase")
    start_sta = st.number_input("STA Awal (m)", value=0.0)
    start_elv = st.number_input("Elevasi Awal (+m)", value=100.00)
    
    st.divider()
    st.header("📂 Menu File")
    
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
    
    uploaded_file = st.file_uploader("Upload Data Excel", type=['xlsx'])
    if uploaded_file:
        try:
            df_uploaded = pd.read_excel(uploaded_file)
            st.session_state.df_input = df_uploaded
            st.success("✅ Data Excel dimuat!")
        except Exception as e:
            st.error(f"Gagal: {e}")

# Data Editor
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

if st.button("▶️ HITUNG & VERIFIKASI (RUN)", type="primary", use_container_width=True):
    hasil_list = []
    curr_sta = start_sta
    curr_elv = start_elv
    
    for idx, row in edited_df.iterrows():
        try:
            L, Q, b, m = float(row['Panjang (m)']), float(row['Debit (Q)']), float(row['Lebar (b)']), float(row['Talud (m)'])
            S, k, offset = float(row['Slope (S)']), float(row['Strickler (k)']), float(row['Offset (m)'])
        except:
            st.error(f"Data baris ke-{idx+1} tidak valid (harus angka).")
            continue
            
        y_calc = solve_strickler_y(Q, b, m, k, S)
        w_calc = get_freeboard_kp03(Q)
        h_calc = y_calc + w_calc
        V_calc, Fr_calc, status, pesan = cek_keamanan_desain(Q, b, m, y_calc, k, S)
        
        elv_awal = curr_elv
        elv_akhir = elv_awal - (L * S)
        
        hasil_list.append({
            'Nama Saluran': row['Nama Saluran'],
            'Status': status, 'Peringatan': pesan,
            'STA Awal': round(curr_sta, 1), 'STA Akhir': round(curr_sta + L, 1),
            'Elv Dasar Awal': round(elv_awal, 3), 'Elv Dasar Akhir': round(elv_akhir, 3),
            'Tinggi Air (y)': round(y_calc, 3), 'Tinggi Total (h)': round(h_calc, 2),
            'Kecepatan (V)': round(V_calc, 2), 'Froude (Fr)': round(Fr_calc, 2),
            'Strickler (k)': k, 'Lebar (b)': b, 'Talud (m)': m
        })
        curr_sta += L
        curr_elv = elv_akhir + offset

    st.session_state.df_hasil = pd.DataFrame(hasil_list)
    st.success("✅ Perhitungan Selesai.")

if 'df_hasil' in st.session_state:
    df_res = st.session_state.df_hasil
    st.divider()
    st.subheader("2. Hasil Analisis")
    st.dataframe(df_res, use_container_width=True, hide_index=True)
    
    col_g1, col_g2 = st.columns([2, 1])
    with col_g1:
        st.pyplot(gambar_profil_memanjang(df_res))
    with col_g2:
        pilih_sal = st.selectbox("Pilih Penampang:", df_res['Nama Saluran'])
        if pilih_sal:
            row_vis = df_res[df_res['Nama Saluran'] == pilih_sal].iloc[0]
            st.pyplot(gambar_penampang_saluran(row_vis))

    st.subheader("5. Ekspor Data")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        output = io.BytesIO()
        with pd.ExcelWriter(output) as writer: 
            df_res.to_excel(writer, sheet_name='Rekap', index=False)
        st.download_button("💾 Download Excel", output.getvalue(), "Laporan.xlsx", use_container_width=True)

    with col_d2:
        if EZDXF_AVAILABLE:
            try:
                doc_dxf = generate_dxf_kp07(df_res)
                output_dxf = io.StringIO()
                doc_dxf.write(output_dxf)
                st.download_button("📐 Download CAD (.dxf)", output_dxf.getvalue().encode('utf-8'), "LongSection.dxf", "application/dxf", type="primary", use_container_width=True)
            except Exception as e:
                st.error(f"Error DXF: {e}")
        else:
            st.warning("Library 'ezdxf' belum terinstall.")
