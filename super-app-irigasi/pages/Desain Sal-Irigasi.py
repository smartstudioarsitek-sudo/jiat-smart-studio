import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import json

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="JIAT Smart Studio - Desain Irigasi", layout="wide", page_icon="🌊")

# Cek library ezdxf
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
    """Menghitung Tinggi Jagaan (Fb) berdasarkan Debit (Q)"""
    if Q < 0.5: return 0.20
    elif Q < 1.5: return 0.20
    elif Q < 5.0: return 0.25
    elif Q < 10.0: return 0.30
    elif Q < 15.0: return 0.40
    else: return 0.50

def solve_strickler_y(Q, b, m, k, S):
    """Mencari tinggi muka air (y) dengan iterasi"""
    if Q <= 0 or b <= 0 or S <= 0: return 0.0
    y = 0.5
    for _ in range(50):
        A = (b + m * y) * y
        P = b + 2 * y * np.sqrt(1 + m**2)
        if P == 0: break
        R = A / P
        Q_calc = A * k * (R**(2/3)) * (S**0.5)
        if abs(Q_calc - Q) < 0.0001: break
        if Q_calc == 0: y += 0.1
        else: y = y * (Q / Q_calc) ** 0.6
    return y

def cek_keamanan_desain(Q, b, m, y, k, S):
    """Mengecek Froude Number dan Kecepatan"""
    A = (b + m * y) * y
    if A <= 0: return 0, 0, "ERROR", "Dimensi tidak valid"
    
    V = Q / A
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
# 3. FUNGSI GENERATE DXF
# ==========================================

def setup_kp07_layers(doc):
    layers = [
        ('KOP_GRID', 8, 'CONTINUOUS'),      
        ('KOP_TEXT', 2, 'CONTINUOUS'),      
        ('TANAH_ASLI', 9, 'DASHED'),        
        ('DESAIN_DASAR', 4, 'CONTINUOUS'),  
        ('DESAIN_AIR', 5, 'DASHDOT'),       
        ('DESAIN_TANGGUL', 3, 'CONTINUOUS'),
        ('DIMENSI', 1, 'CONTINUOUS')        
    ]
    for name, color, ltype in layers:
        if name not in doc.layers:
            doc.layers.add(name, color=color, linetype=ltype)
    
    if 'KP_TEXT_STYLE' not in doc.styles:
        doc.styles.new('KP_TEXT_STYLE', dxfattribs={'font': 'Arial.ttf', 'width': 0.8})

def generate_long_section_dxf(df_hasil):
    if not EZDXF_AVAILABLE: return None
    doc = ezdxf.new('R2010')
    setup_linetypes(doc)
    setup_kp07_layers(doc)
    msp = doc.modelspace()

    SCALE_H = 1.0; SCALE_V = 10.0 
    FONT_SIZE_HEADER = 9.0; FONT_SIZE_DATA = 6.0; FONT_SIZE_DIM = 6.0; H_ROW = 20 
    
    min_elev_dasar = min(df_hasil['Elv Dasar Awal'].min(), df_hasil['Elv Dasar Akhir'].min())
    datum_reference = np.floor((min_elev_dasar - 2.0) / 5.0) * 5.0
    
    bands = {
        'JARAK':        {'y': -1 * H_ROW, 'label': 'JARAK (m)'},
        'ELV_TANAH':    {'y': -2 * H_ROW, 'label': 'ELV. TANAH (+m)'},
        'ELV_DESAIN':   {'y': -3 * H_ROW, 'label': 'ELV. DESAIN (+m)'},
        'ELV_AIR':      {'y': -4 * H_ROW, 'label': 'MUKA AIR (+m)'},
        'DIMENSI':      {'y': -5 * H_ROW, 'label': 'DIMENSI'}
    }
    
    min_y_band = bands['DIMENSI']['y']
    max_sta = df_hasil['STA Akhir'].max() * SCALE_H
    
    for key, info in bands.items():
        y_pos = info['y']
        msp.add_line((-50, y_pos), (max_sta, y_pos), dxfattribs={'layer': 'KOP_GRID'})
        msp.add_text(info['label'], dxfattribs={'height': FONT_SIZE_HEADER, 'style': 'KP_TEXT_STYLE', 'layer': 'KOP_TEXT'}).set_placement((-2, y_pos + H_ROW/3), align=TextEntityAlignment.MIDDLE_RIGHT)

    msp.add_line((-50, 0), (max_sta, 0), dxfattribs={'layer': 'KOP_GRID', 'lineweight': 30})
    msp.add_text(f"DATUM: +{datum_reference:.2f}", dxfattribs={'height': FONT_SIZE_HEADER, 'layer': 'KOP_TEXT'}).set_placement((-2, 2), align=TextEntityAlignment.MIDDLE_RIGHT)

    prev_x = None; prev_y_dasar = None
    
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
            msp.add_text(txt, dxfattribs={'height': FONT_SIZE_DATA, 'rotation': 90, 'style': 'KP_TEXT_STYLE', 'layer': 'KOP_TEXT'}).set_placement((x_pos, y_bottom + H_ROW/2), align=TextEntityAlignment.MIDDLE_CENTER)

        msp.add_line((x_awal, min_y_band), (x_awal, max(y_tanah_awal, y_tanggul_awal) + 5), dxfattribs={'layer': 'KOP_GRID', 'linetype': 'DOT'})

        add_band_text(f"{row['STA Awal']:.0f}", x_awal, bands['JARAK']['y'])
        add_band_text(f"{z_tanah_awal:.2f}", x_awal, bands['ELV_TANAH']['y'])
        add_band_text(f"{row['Elv Dasar Awal']:.2f}", x_awal, bands['ELV_DESAIN']['y'])
        add_band_text(f"{(row['Elv Dasar Awal'] + row['Tinggi Air (y)']):.2f}", x_awal, bands['ELV_AIR']['y'])
        
        x_mid = (x_awal + x_akhir) / 2
        msp.add_text(f"b={row['Lebar (b)']}\nh={row['Tinggi Total (h)']}", dxfattribs={'height': FONT_SIZE_DIM, 'layer': 'KOP_TEXT'}).set_placement((x_mid, bands['DIMENSI']['y'] + H_ROW/2), align=TextEntityAlignment.MIDDLE_CENTER)

        prev_x = x_akhir; prev_y_dasar = y_dasar_akhir

    msp.add_line((x_akhir, min_y_band), (x_akhir, max(y_tanah_akhir, y_tanggul_akhir) + 5), dxfattribs={'layer': 'KOP_GRID', 'linetype': 'DOT'})
    add_band_text(f"{row['STA Akhir']:.0f}", x_akhir, bands['JARAK']['y'])
    add_band_text(f"{z_tanah_akhir:.2f}", x_akhir, bands['ELV_TANAH']['y'])
    add_band_text(f"{row['Elv Dasar Akhir']:.2f}", x_akhir, bands['ELV_DESAIN']['y'])
    add_band_text(f"{(row['Elv Dasar Akhir'] + row['Tinggi Air (y)']):.2f}", x_akhir, bands['ELV_AIR']['y'])
    return doc

def generate_cross_section_dxf(df_hasil):
    if not EZDXF_AVAILABLE: return None
    doc = ezdxf.new('R2010')
    setup_linetypes(doc)
    setup_kp07_layers(doc)
    msp = doc.modelspace()
    
    FONT_SIZE_CROSS = 0.15; DIM_ARROW_SIZE = 0.15       
    start_x = 0; start_y = 0; grid_x_spacing = 50; grid_y_spacing = 50
    col_limit = 2; current_col = 0
    
    for i, row in df_hasil.iterrows():
        cx = start_x + (current_col * grid_x_spacing); cy = start_y
        b = row['Lebar (b)']; m = row['Talud (m)']; h = row['Tinggi Total (h)']; y_air = row['Tinggi Air (y)']
        w_tanggul = 1.0 
        x_bl = -b/2; x_br = b/2; x_tl = -b/2 - (m*h); x_tr = b/2 + (m*h)
        x_bank_l = x_tl - w_tanggul; x_bank_r = x_tr + w_tanggul
        y_btm = 0; y_top = h; y_wtr = y_air
        
        points = [(cx + x_bank_l, cy + y_top), (cx + x_tl, cy + y_top), (cx + x_bl, cy + y_btm),
                  (cx + x_br, cy + y_btm), (cx + x_tr, cy + y_top), (cx + x_bank_r, cy + y_top)]
        msp.add_lwpolyline(points, dxfattribs={'layer': 'DESAIN_DASAR'})
        
        x_wl = -b/2 - (m*y_air); x_wr = b/2 + (m*y_air)
        msp.add_line((cx + x_wl, cy + y_wtr), (cx + x_wr, cy + y_wtr), dxfattribs={'layer': 'DESAIN_AIR'})
        msp.add_lwpolyline([(cx, cy+y_wtr), (cx-0.2, cy+y_wtr+0.4), (cx+0.2, cy+y_wtr+0.4), (cx, cy+y_wtr)], close=True, dxfattribs={'layer': 'DESAIN_AIR'})
        msp.add_line((cx + x_bank_l - 2, cy + y_top), (cx + x_bank_r + 2, cy + y_top), dxfattribs={'layer': 'TANAH_ASLI'})
        
        try:
            msp.add_linear_dim(base=(cx, cy - 1.0), p1=(cx + x_bl, cy + y_btm), p2=(cx + x_br, cy + y_btm), 
                dxfattribs={'layer': 'DIMENSI'}, text=f"b={b:.2f}",
                override={'dimtxt': FONT_SIZE_CROSS, 'dimtsz': 0, 'dimasz': DIM_ARROW_SIZE, 'dimdec': 2, 'dimtad': 1})
        except:
            msp.add_line((cx + x_bl, cy - 1.0), (cx + x_br, cy - 1.0), dxfattribs={'layer': 'DIMENSI'})
            msp.add_text(f"b = {b:.2f}", dxfattribs={'height': FONT_SIZE_CROSS, 'layer': 'DIMENSI'}).set_placement((cx, cy - 0.8), align=TextEntityAlignment.MIDDLE_CENTER)

        msp.add_text(f"STA: {row['STA Awal']}", dxfattribs={'height': FONT_SIZE_CROSS, 'layer': 'KOP_TEXT'}).set_placement((cx, cy - 2.5), align=TextEntityAlignment.MIDDLE_CENTER)
        msp.add_text(f"Elv. Dasar: {row['Elv Dasar Awal']:.2f}", dxfattribs={'height': FONT_SIZE_CROSS, 'layer': 'KOP_TEXT'}).set_placement((cx, cy - 3.0), align=TextEntityAlignment.MIDDLE_CENTER)

        current_col += 1
        if current_col >= col_limit: current_col = 0; start_y -= grid_y_spacing
    return doc

# ==========================================
# 4. USER INTERFACE (UI)
# ==========================================
st.title("🛠️ Desain Irigasi & Ekspor Data")
st.markdown("---")

# --- INISIALISASI SESSION STATE ---
if 'df_input' not in st.session_state:
    data_awal = {
        'Nama Saluran': ['Saluran Induk 1', 'Saluran Induk 2'],
        'Panjang (m)': [50.0, 50.0],
        'Offset (m)': [0.00, -0.50], 
        'Debit (Q)': [2.50, 2.50],
        'Lebar (b)': [1.50, 1.50],
        'Talud (m)': [1.0, 1.0],
        'Slope (S)': [0.0008, 0.001], 
        'Strickler (k)': [60, 60]
    }
    st.session_state.df_input = pd.DataFrame(data_awal)

# --- SIDEBAR (FILE MANAGEMENT) ---
with st.sidebar:
    st.header("📂 File Project")
    
    # 1. SAVE PROJECT (JSON/GEOJSON style)
    st.markdown("**Simpan Pekerjaan (Save):**")
    project_data = st.session_state.df_input.to_json(orient='records')
    st.download_button(
        label="💾 Save Project (.json)",
        data=project_data,
        file_name="Proyek_Irigasi.json",
        mime="application/json",
        use_container_width=True,
        help="Simpan data input saat ini agar bisa dibuka kembali nanti."
    )
    
    st.divider()
    
    # 2. OPEN PROJECT
    st.markdown("**Buka Pekerjaan (Open):**")
    uploaded_json = st.file_uploader("Upload File .json", type=['json'])
    if uploaded_json is not None:
        try:
            df_loaded = pd.read_json(uploaded_json)
            st.session_state.df_input = df_loaded
            st.success("✅ Project berhasil dibuka!")
            st.rerun()
        except Exception as e:
            st.error(f"Gagal membuka file: {e}")

    st.divider()
    st.header("⚙️ Parameter Global")
    start_sta = st.number_input("STA Awal (m)", value=0.0)
    start_elv = st.number_input("Elevasi Awal (+m)", value=100.00)

# --- MAIN AREA ---
st.subheader("1. Input Data Desain")
col_up1, col_up2 = st.columns([1, 2])

with col_up1:
    # Template Excel Biasa
    def generate_template():
        df_temp = pd.DataFrame(columns=['Nama Saluran', 'Panjang (m)', 'Offset (m)', 'Debit (Q)', 'Lebar (b)', 'Talud (m)', 'Slope (S)', 'Strickler (k)'])
        df_temp.loc[0] = ['Saluran Contoh', 50, 0, 2.5, 1.5, 1.0, 0.0008, 60]
        output = io.BytesIO()
        with pd.ExcelWriter(output) as writer: df_temp.to_excel(writer, index=False)
        return output.getvalue()

    st.download_button("📥 Download Template Excel", generate_template(), "Template_Irigasi.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

with col_up2:
    uploaded_excel = st.file_uploader("📂 Import dari Excel (Data Baru)", type=['xlsx'])
    if uploaded_excel:
        try:
            df_upload = pd.read_excel(uploaded_excel)
            required_cols = ['Nama Saluran', 'Panjang (m)', 'Debit (Q)']
            if all(col in df_upload.columns for col in required_cols):
                st.session_state.df_input = df_upload
                st.success("✅ Data Excel dimuat!")
            else:
                st.error("❌ Format Excel salah.")
        except Exception as e:
            st.error(f"Error: {e}")

edited_df = st.data_editor(st.session_state.df_input, num_rows="dynamic", hide_index=True, use_container_width=True)

# ==========================================
# HITUNG & OUTPUT
# ==========================================

if st.button("▶️ HITUNG & VERIFIKASI (RUN)", type="primary", use_container_width=True):
    hasil_list = []
    curr_sta = start_sta; curr_elv = start_elv
    
    for idx, row in edited_df.iterrows():
        try:
            L = float(row['Panjang (m)']); Q = float(row['Debit (Q)']); b = float(row['Lebar (b)'])
            m = float(row['Talud (m)']); S = float(row['Slope (S)']); k = float(row['Strickler (k)'])
            offset = float(row['Offset (m)']) if 'Offset (m)' in row else 0.0
            
            y_calc = solve_strickler_y(Q, b, m, k, S)
            h_calc = y_calc + get_freeboard_kp03(Q)
            V_calc, Fr_calc, status, pesan = cek_keamanan_desain(Q, b, m, y_calc, k, S)
            
            elv_awal = curr_elv; elv_akhir = elv_awal - (L * S)
            
            hasil_list.append({
                'Nama Saluran': row['Nama Saluran'], 'Status': status, 'Peringatan': pesan,
                'STA Awal': round(curr_sta, 1), 'STA Akhir': round(curr_sta + L, 1),
                'Elv Dasar Awal': round(elv_awal, 3), 'Elv Dasar Akhir': round(elv_akhir, 3),
                'Tinggi Air (y)': round(y_calc, 3), 'Tinggi Total (h)': round(h_calc, 2),
                'Kecepatan (V)': round(V_calc, 2), 'Froude (Fr)': round(Fr_calc, 2),
                'Strickler (k)': k, 'Lebar (b)': b, 'Talud (m)': m, 'Slope (S)': S, 'Debit (Q)': Q 
            })
            curr_sta += L; curr_elv = elv_akhir + offset 

        except Exception as e: st.error(f"Error baris {idx+1}: {e}")

    st.session_state.df_hasil = pd.DataFrame(hasil_list)
    st.success("✅ Perhitungan Selesai!")

if 'df_hasil' in st.session_state:
    df_res = st.session_state.df_hasil
    st.divider(); st.subheader("2. Hasil & Visualisasi")
    st.dataframe(df_res.style.apply(lambda x: ['background-color: #ffcccc' if v == 'TIDAK AMAN' else '' for v in x], subset=['Status']), use_container_width=True, hide_index=True)

    col_g1, col_g2 = st.columns([2, 1])
    with col_g1:
        if len(df_res) > 0:
            fig, ax = plt.subplots(figsize=(10, 4))
            stas = []; elvs_dasar = []; elvs_air = []; elvs_tanggul = []
            for i, row in df_res.iterrows():
                stas.extend([row['STA Awal'], row['STA Akhir']])
                elvs_dasar.extend([row['Elv Dasar Awal'], row['Elv Dasar Akhir']])
                elvs_air.extend([row['Elv Dasar Awal'] + row['Tinggi Air (y)'], row['Elv Dasar Akhir'] + row['Tinggi Air (y)']])
                elvs_tanggul.extend([row['Elv Dasar Awal'] + row['Tinggi Total (h)'], row['Elv Dasar Akhir'] + row['Tinggi Total (h)']])
            ax.plot(stas, elvs_tanggul, 'g-', label='Tanggul'); ax.plot(stas, elvs_dasar, 'k-', linewidth=2, label='Dasar')
            ax.plot(stas, elvs_air, 'b-.', label='Muka Air'); ax.fill_between(stas, elvs_dasar, elvs_air, color='#00BFFF', alpha=0.2)
            ax.set_xlabel("Stationing (m)"); ax.set_ylabel("Elevasi (+m)"); ax.legend(); st.pyplot(fig)
    with col_g2:
        pilih_sal = st.selectbox("Preview Penampang:", df_res['Nama Saluran'])
        if pilih_sal:
            row = df_res[df_res['Nama Saluran'] == pilih_sal].iloc[0]
            b, m, h, y = row['Lebar (b)'], row['Talud (m)'], row['Tinggi Total (h)'], row['Tinggi Air (y)']
            fig2, ax2 = plt.subplots(figsize=(5, 3))
            x_trap = [-b/2 - m*h, -b/2, b/2, b/2 + m*h]; y_trap = [h, 0, 0, h]
            ax2.plot(x_trap, y_trap, 'k-', linewidth=2); ax2.fill_between([-b/2 - m*y, -b/2, b/2, b/2 + m*y], [y, 0, 0, y], color='#00BFFF', alpha=0.5)
            ax2.set_aspect('equal'); st.pyplot(fig2)

    # ==========================================
    # MENU EKSPOR LENGKAP
    # ==========================================
    st.subheader("3. Ekspor Data Lengkap (Excel & CAD)")
    col_d1, col_d2, col_d3 = st.columns(3)
    
    with col_d1:
        # EXCEL MULTI-SHEET (REKAP, LONG, CROSS)
        output_excel = io.BytesIO()
        with pd.ExcelWriter(output_excel, engine='xlsxwriter') as writer:
            # Sheet 1: Rekap
            df_res.to_excel(writer, sheet_name='Rekap_Desain', index=False)
            
            # Sheet 2: Data Long Section (Untuk Plotting)
            long_cols = ['STA Awal', 'STA Akhir', 'Elv Dasar Awal', 'Elv Dasar Akhir', 'Tinggi Air (y)', 'Tinggi Total (h)']
            df_long = df_res[long_cols].copy()
            df_long['Elv Muka Air'] = df_long['Elv Dasar Awal'] + df_long['Tinggi Air (y)']
            df_long['Elv Tanggul'] = df_long['Elv Dasar Awal'] + df_long['Tinggi Total (h)']
            df_long.to_excel(writer, sheet_name='Data_Long_Section', index=False)
            
            # Sheet 3: Data Cross Section (Detail Geometri)
            cross_cols = ['Nama Saluran', 'STA Awal', 'Lebar (b)', 'Talud (m)', 'Tinggi Total (h)', 'Tinggi Air (y)', 'Debit (Q)', 'Kecepatan (V)']
            df_res[cross_cols].to_excel(writer, sheet_name='Data_Cross_Section', index=False)
            
        st.download_button(
            label="📊 Download Excel Lengkap",
            data=output_excel.getvalue(),
            file_name="Laporan_Desain_Lengkap.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Berisi 3 Sheet: Rekap, Data Long Section, dan Data Cross Section",
            use_container_width=True
        )

    with col_d2:
        if EZDXF_AVAILABLE:
            doc_long = generate_long_section_dxf(df_res); out_long = io.StringIO(); doc_long.write(out_long)
            st.download_button("📐 Long Section (.dxf)", out_long.getvalue().encode('utf-8'), "LongSection.dxf", "application/dxf", use_container_width=True)
    with col_d3:
        if EZDXF_AVAILABLE:
            doc_cross = generate_cross_section_dxf(df_res); out_cross = io.StringIO(); doc_cross.write(out_cross)
            st.download_button("📐 Cross Section (.dxf)", out_cross.getvalue().encode('utf-8'), "CrossSection.dxf", "application/dxf", use_container_width=True)
