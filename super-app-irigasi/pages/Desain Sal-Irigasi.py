import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io

# ==========================================
# 1. KONFIGURASI HALAMAN (WAJIB DI ATAS)
# ==========================================
st.set_page_config(page_title="Desain Irigasi KP-03 & KP-07", layout="wide", page_icon="🌊")

# Coba import library ezdxf
try:
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    from ezdxf.tools.standards import setup_linetypes
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False

# ==========================================
# 2. FUNGSI PERHITUNGAN HIDROLIS (JANGAN DIUBAH)
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
        if P == 0: break
        R = A / P
        Q_calc = A * k * (R**(2/3)) * (S**0.5)
        if abs(Q_calc - Q) < 0.0001: break
        if Q_calc == 0: y += 0.1
        else: y = y * (Q / Q_calc) ** 0.6
    return y

def cek_keamanan_desain(Q, b, m, y, k, S):
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
# 3. FUNGSI GENERATE DXF (FONT DISESUAIKAN DISINI)
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

    SCALE_H = 1.0   
    SCALE_V = 10.0 

    min_elev_dasar = min(df_hasil['Elv Dasar Awal'].min(), df_hasil['Elv Dasar Akhir'].min())
    datum_reference = np.floor((min_elev_dasar - 2.0) / 5.0) * 5.0
    
    H_ROW = 20 # Diperbesar row height-nya biar muat font besar
    bands = {
        'JARAK':        {'y': -1 * H_ROW, 'label': 'JARAK (m)'},
        'ELV_TANAH':    {'y': -2 * H_ROW, 'label': 'ELV. TANAH (+m)'},
        'ELV_DESAIN':   {'y': -3 * H_ROW, 'label': 'ELV. DESAIN (+m)'},
        'ELV_AIR':      {'y': -4 * H_ROW, 'label': 'MUKA AIR (+m)'},
        'DIMENSI':      {'y': -5 * H_ROW, 'label': 'DIMENSI'}
    }
    
    min_y_band = bands['DIMENSI']['y']
    max_sta = df_hasil['STA Akhir'].max() * SCALE_H
    
    # --- [UPDATE 1: LONG SECTION HEADER JADI BESAR] ---
    for key, info in bands.items():
        y_pos = info['y']
        msp.add_line((-50, y_pos), (max_sta, y_pos), dxfattribs={'layer': 'KOP_GRID'})
        # Height jadi 6.0 (Sangat Besar)
        msp.add_text(info['label'], dxfattribs={'height': 6.0, 'style': 'KP_TEXT_STYLE', 'layer': 'KOP_TEXT'}).set_placement((-2, y_pos + H_ROW/2), align=TextEntityAlignment.MIDDLE_RIGHT)

    msp.add_line((-50, 0), (max_sta, 0), dxfattribs={'layer': 'KOP_GRID', 'lineweight': 30})
    msp.add_text(f"DATUM: +{datum_reference:.2f}", dxfattribs={'height': 6.0, 'layer': 'KOP_TEXT'}).set_placement((-2, 2), align=TextEntityAlignment.MIDDLE_RIGHT)

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

        # --- [UPDATE 2: LONG SECTION ISI DATA JADI BESAR] ---
        def add_band_text(txt, x_pos, y_bottom):
            # Height jadi 4.0 (Besar)
            msp.add_text(txt, dxfattribs={'height': 4.0, 'rotation': 90, 'style': 'KP_TEXT_STYLE', 'layer': 'KOP_TEXT'}).set_placement((x_pos, y_bottom + H_ROW/2), align=TextEntityAlignment.MIDDLE_CENTER)

        msp.add_line((x_awal, min_y_band), (x_awal, max(y_tanah_awal, y_tanggul_awal) + 5), dxfattribs={'layer': 'KOP_GRID', 'linetype': 'DOT'})

        add_band_text(f"{row['STA Awal']:.0f}", x_awal, bands['JARAK']['y'])
        add_band_text(f"{z_tanah_awal:.2f}", x_awal, bands['ELV_TANAH']['y'])
        add_band_text(f"{row['Elv Dasar Awal']:.2f}", x_awal, bands['ELV_DESAIN']['y'])
        add_band_text(f"{(row['Elv Dasar Awal'] + row['Tinggi Air (y)']):.2f}", x_awal, bands['ELV_AIR']['y'])
        
        x_mid = (x_awal + x_akhir) / 2
        # Dimensi Tengah juga besar (4.0)
        msp.add_text(f"b={row['Lebar (b)']}\nh={row['Tinggi Total (h)']}", dxfattribs={'height': 4.0, 'layer': 'KOP_TEXT'}).set_placement((x
