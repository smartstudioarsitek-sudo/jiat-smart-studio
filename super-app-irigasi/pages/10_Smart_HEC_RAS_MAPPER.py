import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import io

# --- CONFIG ---
st.set_page_config(page_title="HEC-RAS Mapper GIS", layout="wide", page_icon="🗺️")

st.markdown("""
<style>
    .header-box { padding: 20px; background: linear-gradient(90deg, #1e3c72, #2a5298); color: white; border-radius: 8px; text-align: center; margin-bottom: 20px; }
    .stAlert { padding: 10px; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# --- 1. ENGINE HIDROLIKA (CORE) ---
def get_critical_depth(Q, b, m):
    g = 9.81; y_min, y_max = 0.01, 20.0
    for _ in range(30):
        y = (y_min + y_max) / 2
        A = (b + m * y) * y; T = b + 2 * m * y
        if A <= 0: A = 0.001
        f_val = 9.81 * (A**3) - (Q**2) * T
        if abs(f_val) < 0.01: return y
        if f_val < 0: y_min = y
        else: y_max = y
    return (y_min + y_max) / 2

def get_geom_props(y, b, m, Q):
    if y <= 0.001: y = 0.001
    A = (b + m * y) * y
    P = b + 2 * y * np.sqrt(1 + m**2)
    R = A / P if P > 0 else 0
    T = b + 2 * m * y
    hydrostatic_term = ((y**2)/2) * b + ((y**3)/3) * m
    g = 9.81
    if A > 0.0001: M = (Q**2)/(g*A) + hydrostatic_term 
    else: M = 0
    return A, P, R, T, M

def solve_energy_step(y_known, Q, n, Z1, Z2, b, m, dx, mode):
    g = 9.81
    A1, P1, R1, T1, M1 = get_geom_props(y_known, b, m, Q)
    V1 = Q/A1
    H1 = Z1 + y_known + (V1**2)/(2*g)
    
    def func(y2):
        A2, P2, R2, T2, M2 = get_geom_props(y2, b, m, Q)
        V2 = Q/A2
        H2 = Z2 + y2 + (V2**2)/(2*g)
        Sf1 = (n*V1)**2 / (R1**(4/3))
        Sf2 = (n*V2)**2 / (R2**(4/3))
        Sf_avg = (Sf1 + Sf2)/2
        loss = Sf_avg * dx
        if mode == 'sub': return H2 - (H1 + loss)
        else: return H1 - (H2 + loss)

    y_min, y_max = 0.01, 50.0
    for _ in range(50):
        y_mid = (y_min + y_max)/2
        err = func(y_mid)
        if abs(err) < 0.001: return y_mid
        if mode == 'sub': 
            if err > 0: y_max = y_mid 
            else: y_min = y_mid
        else:
            if err > 0: y_min = y_mid
            else: y_max = y_mid
    return (y_min + y_max)/2

def calculate_profiles(nodes, Q, boundary_down, boundary_up, force_super=False):
    for n in nodes:
        n['yc'] = get_critical_depth(Q, n['b'], n['m'])
        n['y_sub'] = 0.0; n['y_sup'] = 0.0; n['y_final'] = 0.0 
    
    # SUBCRITICAL (Mundur)
    nodes[-1]['y_sub'] = boundary_down
    for i in range(len(nodes)-2, -1, -1):
        dx = nodes[i+1]['x'] - nodes[i]['x']
        known, target = nodes[i+1], nodes[i]
        yc = target['yc']
        try:
            y_calc = solve_energy_step(known['y_sub'], Q, target['n'], known['z'], target['z'], target['b'], target['m'], dx, 'sub')
            if y_calc < yc: y_calc = yc + 0.01 
        except: y_calc = yc + 0.01
        target['y_sub'] = y_calc

    # SUPERCRITICAL (Maju)
    nodes[0]['y_sup'] = boundary_up
    for i in range(1, len(nodes)):
        dx = nodes[i]['x'] - nodes[i-1]['x']
        known, target = nodes[i-1], nodes[i]
        yc = target['yc']
        try:
            y_calc = solve_energy_step(known['y_sup'], Q, target['n'], known['z'], target['z'], target['b'], target['m'], dx, 'sup')
            if y_calc > yc: y_calc = yc - 0.01 
        except: y_calc = yc - 0.01
        target['y_sup'] = y_calc

    # SELECTION & FREEBOARD
    for n in nodes:
        if force_super:
            if n['y_sup'] > 0.011 and n['y_sup'] < 49.0: n['y_final'] = n['y_sup']; n['regime'] = "Supercritical (Forced)"
            else: n['y_final'] = n['yc']; n['regime'] = "Critical (Fallback)"
        else:
            if n['y_sub'] <= 0.011 or n['y_sub'] > 49.0: M_sub = -1.0
            else: _, _, _, _, M_sub = get_geom_props(n['y_sub'], n['b'], n['m'], Q)
            if n['y_sup'] <= 0.011 or n['y_sup'] > 49.0: M_sup = -1.0
            else: _, _, _, _, M_sup = get_geom_props(n['y_sup'], n['b'], n['m'], Q)
            
            if M_sub == -1 and M_sup == -1: n['y_final'] = n['yc']; n['regime'] = "Critical (Fallback)"
            elif M_sub >= M_sup: n['y_final'] = n['y_sub']; n['regime'] = "Subcritical"
            else: n['y_final'] = n['y_sup']; n['regime'] = "Supercritical"
            
        n['ws'] = n['z'] + n['y_final']
        n['crit_ws'] = n['z'] + n['yc']
        
        # Freeboard
        H_ch = n.get('h_ch', 1.5) 
        n['bank_elev'] = n['z'] + H_ch
        n['freeboard'] = n['bank_elev'] - n['ws']
        
        A, P, R, T, _ = get_geom_props(n['y_final'], n['b'], n['m'], Q)
        V = Q/A if A > 0 else 0
        n['v'] = V 
        n['eg'] = n['ws'] + (V**2)/(2*9.81)
        D_hyd = A/T if T > 0 else 0
        n['fr'] = V / np.sqrt(9.81 * D_hyd) if D_hyd > 0 else 0
        n['top_width'] = T

    return nodes

# --- 2. SETUP & STATE ---
REQUIRED_COLS = ["Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n", "Tinggi Saluran H (m)"]

def reset_data():
    return pd.DataFrame([["S1", 0, 50, 100, 99.5, 2.0, 1.0, 0.017, 1.5]], columns=REQUIRED_COLS)

if 'df_mapper' not in st.session_state: st.session_state['df_mapper'] = reset_data()
if 'q_mapper' not in st.session_state: st.session_state['q_mapper'] = 0.24
if 'ws_down_m' not in st.session_state: st.session_state['ws_down_m'] = 0.5
if 'ws_up_m' not in st.session_state: st.session_state['ws_up_m'] = 0.2 

# --- UI ---
st.markdown("""<div class="header-box"><h1>🗺️ HEC-RAS Mapper (GIS Bridge)</h1><p>Import Point Data from Global Mapper/QGIS & Auto-Simulate</p></div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Konfigurasi")
    st.session_state['q_mapper'] = st.number_input("Debit (Q) m³/s", 0.01, 1000.0, st.session_state['q_mapper'])
    force_super = st.checkbox("🔥 Force Supercritical", value=False)
    
    st.divider()
    st.subheader("🌊 Boundary Conditions")
    st.session_state['ws_up_m'] = st.number_input("Hulu Depth (m)", 0.01, 20.0, st.session_state['ws_up_m'])
    st.session_state['ws_down_m'] = st.number_input("Hilir Depth (m)", 0.01, 20.0, st.session_state['ws_down_m'])
    
    st.divider()
    st.subheader("📂 Input Data")
    
    # TAB KHUSUS GIS
    tab_gis, tab_xls = st.tabs(["🌍 GIS (CSV)", "📄 Excel Template"])
    
    with tab_gis:
        st.info("Format CSV: Harus ada kolom Jarak (Dist) & Elevasi (Z).")
        up_gis = st.file_uploader("Upload CSV dari Global Mapper/QGIS", type=['csv', 'txt'], key="gis_uploader")
        
        if up_gis:
            st.markdown("---")
            st.caption("Default Parameter Saluran:")
            c1, c2 = st.columns(2)
            def_b = c1.number_input("Lebar (b)", 0.1, 50.0, 1.0)
            def_m = c2.number_input("Talud (m)", 0.0, 10.0, 1.0)
            def_n = c1.number_input("Manning (n)", 0.001, 0.1, 0.025)
            def_h = c2.number_input("Tinggi (H)", 0.1, 10.0, 1.5)
            
            if st.button("🚀 Konversi GIS ke Model"):
                try:
                    df_gis = pd.read_csv(up_gis)
                    df_gis.columns = [c.lower() for c in df_gis.columns]
                    
                    # Smart Column Detection
                    col_dist = next((c for c in df_gis.columns if any(x in c for x in ['dist', 'len', 'x', 'sta'])), None)
                    col_elev = next((c for c in df_gis.columns if any(x in c for x in ['elev', 'z', 'height'])), None)
                    
                    if col_dist and col_elev:
                        new_rows = []
                        for i in range(len(df_gis) - 1):
                            d1 = df_gis.iloc[i][col_dist]; d2 = df_gis.iloc[i+1][col_dist]
                            z1 = df_gis.iloc[i][col_elev]; z2 = df_gis.iloc[i+1][col_elev]
                            
                            if abs(d2 - d1) < 0.01: continue # Skip duplicate points
                            
                            new_rows.append({
                                "Nama Segmen": f"S{i+1}",
                                "STA Awal (m)": d1, "STA Akhir (m)": d2,
                                "Elev Awal (m)": z1, "Elev Akhir (m)": z2,
                                "Lebar b (m)": def_b, "Talud m": def_m,
                                "Kekasaran n": def_n, "Tinggi Saluran H (m)": def_h
                            })
                        
                        st.session_state['df_mapper'] = pd.DataFrame(new_rows)
                        st.success(f"✅ Berhasil import {len(new_rows)} segmen!")
                        st.rerun()
                    else:
                        st.error("Gagal deteksi kolom. Pastikan ada 'Distance' dan 'Elevation'.")
                except Exception as e:
                    st.error(f"Error: {e}")

    with tab_xls:
        up_excel = st.file_uploader("Upload Excel", type=['xlsx'], key="xls_mapper")
        if up_excel:
            try:
                df = pd.read_excel(up_excel)
                # Simple Cleaning
                st.session_state['df_mapper'] = df
                st.rerun()
            except: pass
            
    if st.button("🔄 Reset Data"): st.session_state['df_mapper'] = reset_data(); st.rerun()

# --- MAIN LOGIC ---
df = st.session_state['df_mapper']
final_data = []
profile = {'x': [], 'z': [], 'ws': [], 'bank': [], 'eg': []}

if not df.empty:
    try:
        if "STA Awal (m)" in df.columns: df = df.sort_values(by="STA Awal (m)")
        
        segments = df.to_dict('records')
        dx_step = 2.0 
        nodes = []
        
        for idx, seg in enumerate(segments):
            sta1 = seg.get("STA Awal (m)", 0); sta2 = seg.get("STA Akhir (m)", 0
