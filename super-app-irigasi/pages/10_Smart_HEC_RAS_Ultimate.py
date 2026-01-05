import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import json

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Smart HEC-RAS V4.0 (BBWS Standard)", layout="wide", page_icon="🏗️")
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; font-weight: bold; }
    .run-btn { background-color: #28a745 !important; color: white !important; }
    .header-box { padding: 15px; background: linear-gradient(90deg, #134E5E, #71B280); color: white; border-radius: 10px; text-align: center; margin-bottom: 20px; }
    .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# --- 2. ENGINE HIDROLIKA ---
def get_geom_props(y, b, m, Q):
    if y <= 0.001: y = 0.001
    A = (b + m * y) * y
    P = b + 2 * y * np.sqrt(1 + m**2)
    R = A / P if P > 0 else 0
    T = b + 2 * m * y
    # Momentum Equation simplified terms
    hydrostatic_term = ((y**2)/2) * b + ((y**3)/3) * m
    g = 9.81
    if A > 0.0001: M = (Q**2)/(g*A) + hydrostatic_term 
    else: M = 0
    return A, P, R, T, M

def get_critical_depth(Q, b, m):
    y_min, y_max = 0.01, 20.0
    for _ in range(30):
        y = (y_min + y_max) / 2
        A, _, _, T, _ = get_geom_props(y, b, m, Q)
        f_val = 9.81 * (A**3) - (Q**2) * T
        if abs(f_val) < 0.01: return y
        if f_val < 0: y_min = y
        else: y_max = y
    return (y_min + y_max) / 2

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
        loss = ((Sf1 + Sf2)/2) * dx
        if mode == 'sub': return H2 - (H1 + loss)
        else: return H1 - (H2 + loss)

    y_min, y_max = 0.01, 50.0
    for _ in range(30):
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

def calculate_profiles(nodes, boundary_down, boundary_up, force_subcritical=True):
    # 1. Critical Depth
    for n in nodes:
        Q_local = n.get('Q', 0.5)
        n['yc'] = get_critical_depth(Q_local, n['b'], n['m'])
        n['y_sub'] = 0.0; n['y_sup'] = 0.0; n['y_final'] = 0.0 
    
    # 2. Subcritical (Hilir -> Hulu) - PREFERRED FOR IRRIGATION
    nodes[-1]['y_sub'] = boundary_down
    for i in range(len(nodes)-2, -1, -1):
        dx = nodes[i+1]['x'] - nodes[i]['x']
        known, target = nodes[i+1], nodes[i]
        yc = target['yc']
        try:
            y_calc = solve_energy_step(known['y_sub'], target['Q'], target['n'], known['z'], target['z'], target['b'], target['m'], dx, 'sub')
            target['y_sub'] = max(y_calc, yc + 0.01) # Force stay above critical
        except: target['y_sub'] = yc + 0.05

    # 3. Supercritical (Only if needed or forced)
    if not force_subcritical:
        nodes[0]['y_sup'] = boundary_up
        for i in range(1, len(nodes)):
            dx = nodes[i]['x'] - nodes[i-1]['x']
            known, target = nodes[i-1], nodes[i]
            yc = target['yc']
            try:
                y_calc = solve_energy_step(known['y_sup'], target['Q'], target['n'], known['z'], target['z'], target['b'], target['m'], dx, 'sup')
                target['y_sup'] = min(y_calc, yc - 0.01)
            except: target['y_sup'] = yc - 0.05

    # 4. Selection (Default to Subcritical for Irrigation)
    for n in nodes:
        if force_subcritical:
            n['y_final'] = n['y_sub']
            n['regime'] = "Subcritical"
        else:
            # Simple momentum logic or force super
            n['y_final'] = n['y_sub'] 
            n['regime'] = "Subcritical"
        
        n['ws'] = n['z'] + n['y_final']
        n['bank_elev'] = n['z'] + n.get('h_ch', 1.5)
        n['freeboard'] = n['bank_elev'] - n['ws']
        
        A, P, R, T, _ = get_geom_props(n['y_final'], n['b'], n['m'], n['Q'])
        n['v'] = n['Q']/A if A > 0 else 0
        n['fr'] = n['v'] / np.sqrt(9.81 * (A/T)) if T > 0 else 0

    return nodes

# --- 3. EXPORT SCRIPTS (BBWS STANDAR) ---
def generate_long_scr(nodes_ex, nodes_des=None, distorsi=10):
    s = "; --- LONG SECTION BBWS STANDAR ---\nOSMODE 0\nZOOM E\n"
    def fmt(x, y): return f"{x:.4f},{y * distorsi:.4f}"

    # EKSISTING
    if nodes_ex:
        s += f"-LAYER M EKS_TANAH C 250 EKS_TANAH \n_PLINE\n"
        for n in nodes_ex: s += f"{fmt(n['x'], n['z'])}\n"
        s += "\n"
        
        # TEKS STA (interval 50m)
        s += f"-LAYER M TEXT_STA C 7 TEXT_STA \n"
        for i, n in enumerate(nodes_ex):
            if i % 25 == 0: s += f"-TEXT {fmt(n['x'], n['z'] - 2)} 1.0 90 STA {n['x']:.0f}\n"

    # DESAIN (Jika ada)
    if nodes_des:
        s += f"-LAYER M DES_SALURAN C 10 DES_SALURAN \n_PLINE\n" # Merah/Coklat
        for n in nodes_des: s += f"{fmt(n['x'], n['z'])}\n"
        s += "\n"
        s += f"-LAYER M DES_AIR C 150 DES_AIR \n_PLINE\n" # Biru
        for n in nodes_des: s += f"{fmt(n['x'], n['ws'])}\n"
        s += "\n"
        s += f"-LAYER M DES_BANK C 30 DES_BANK \n_PLINE\n" # Jingga/Bank
        for n in nodes_des: s += f"{fmt(n['x'], n['bank_elev'])}\n"
        s += "\n"

        # Gambar Drop Structures (Vertikal)
        s += f"-LAYER M DES_BANGUNAN C 2 DES_BANGUNAN \n"
        for i in range(1, len(nodes_des)):
            curr = nodes_des[i]; prev = nodes_des[i-1]
            # Deteksi lonjakan Z tiba-tiba (Drop)
            if (prev['z'] - curr['z']) > 0.5: # Jika ada drop > 0.5m
                s += "_PLINE\n"
                s += f"{fmt(curr['x'], prev['z'])}\n" # Atas terjun
                s += f"{fmt(curr['x'], curr['z'])}\n" # Bawah terjun
                s += "\n"

    s += "ZOOM E\n"
    return s

def generate_cs_scr(nodes, dataset="DESAIN", sp_x=30, sp_y=20):
    s = f"; --- CROSS SECTION {dataset} BBWS ---\nOSMODE 0\n"
    r, c = 0, 0
    max_c = 5
    
    for n in nodes:
        bx, by = c * sp_x, r * -sp_y
        b, m, z, h = n['b'], n['m'], n['z'], n['h_ch']
        ws = n['ws']
        
        # 1. LAYER SALURAN (PUTIH/7)
        top_w = b + 2*m*h
        pts = [(-top_w/2, h), (-b/2, 0), (b/2, 0), (top_w/2, h)]
        s += f"-LAYER M {dataset}_SALURAN C 7 {dataset}_SALURAN \n_PLINE\n"
        for px, py in pts: s += f"{bx + px:.4f},{by + py:.4f}\n"
        s += "\n"

        # 2. LAYER AIR (BIRU/150)
        if n['y_final'] > 0:
            top_w_air = b + 2*m*n['y_final']
            pts_air = [(-top_w_air/2, n['y_final']), (top_w_air/2, n['y_final'])]
            s += f"-LAYER M {dataset}_AIR C 150 {dataset}_AIR \n_PLINE\n"
            for px, py in pts_air: s += f"{bx + px:.4f},{by + py:.4f}\n"
            s += "\n"

        # 3. TEXT LABEL
        s += f"-LAYER M {dataset}_TEXT C 2 {dataset}_TEXT \n"
        s += f"-TEXT {bx:.4f},{by - 3:.4f} 0.5 0 STA {n['x']:.2f}\n"
        
        c += 1
        if c >= max_c:
            c = 0; r += 1
            
    s += "ZOOM E\n"
    return s

# --- 4. STATE & DATA ---
if 'res_ex' not in st.session_state: st.session_state['res_ex'] = None
if 'res_des' not in st.session_state: st.session_state['res_des'] = None
if 'drop_list' not in st.session_state: st.session_state['drop_list'] = []

REQUIRED_COLS = [
    "Nama Segmen", "STA Awal (m)", "STA Akhir (m)", 
    "Elev Awal (m)", "Elev Akhir (m)", 
    "Debit Q (m3/s)", "Lebar b (m)", "Talud m", "Kekasaran n", "Tinggi Saluran H (m)",
    "Desain S", "Desain B (m)", "Desain m", "Max Drop (m)"
]

def reset_data():
    return pd.DataFrame([["S1", 0, 100, 100, 95.0, 0.5, 2.0, 1.0, 0.025, 1.5, 0.001, 1.0, 1.0, 1.5]], columns=REQUIRED_COLS)

if 'df_pro' not in st.session_state: st.session_state['df_pro'] = reset_data()

# --- 5. UI SIDEBAR ---
with st.sidebar:
    st.header("📂 Data & Config")
    up_excel = st.file_uploader("Upload Excel (.xlsx)", type=['xlsx'])
    if up_excel:
        try:
            df = pd.read_excel(up_excel)
            df.columns = [c.strip() for c in df.columns]
            defaults = {"Desain S":0.001, "Desain B (m)":0.6, "Desain m":1.0, "Max Drop (m)":1.5, "Debit Q (m3/s)":0.5, "Tinggi Saluran H (m)":1.5}
            for k,v in defaults.items(): 
                if k not in df.columns: df[k] = v
            st.session_state['df_pro'] = df
            st.success("✅ Excel Loaded!")
        except: st.error("Gagal Load Excel")
        
    st.divider()
    if st.button("Reset Data"): st.session_state['df_pro'] = reset_data()

# --- 6. MAIN UI ---
st.markdown('<div class="header-box"><h1>🏗️ Smart HEC-RAS V4.0 (BBWS Standard)</h1></div>', unsafe_allow_html=True)

# TOMBOL RUN (UTAMA)
if st.button("🚀 RUN ANALISIS HIDROLIKA", type="primary"):
    with st.spinner("Menghitung..."):
        try:
            df = st.session_state['df_pro'].sort_values("STA Awal (m)")
            segs = df.to_dict('records')
            nodes_ex, nodes_des = [], []
            drop_structs = [] # List untuk menyimpan data terjunan
            
            # 1. GENERATE EKSISTING NODES
            for seg in segs:
                L = seg.get('STA Akhir (m)', 0) - seg.get('STA Awal (m)', 0)
                if L <= 0: continue
                dx = 2.0; n_steps = int(L/dx)
                if n_steps < 1: n_steps = 1; dx = L
                slope = (seg['Elev Awal (m)'] - seg['Elev Akhir (m)']) / L
                
                for i in range(n_steps+1):
                    nodes_ex.append({
                        "x": seg['STA Awal (m)'] + i*dx,
                        "z": seg['Elev Awal (m)'] - i*dx*slope,
                        "b": seg.get('Lebar b (m)', 1.0), "m": seg.get('Talud m', 1.0),
                        "n": seg.get('Kekasaran n', 0.025), "h_ch": seg.get('Tinggi Saluran H (m)', 1.5),
                        "Q": seg.get('Debit Q (m3/s)', 0.5)
                    })
            st.session_state['res_ex'] = calculate_profiles(nodes_ex, 0.5, 0.5, force_subcritical=True)

            # 2. GENERATE DESAIN NODES (REDESIGN)
            if nodes_ex:
                z_curr = nodes_ex[0]['z'] # Start at existing ground
                
                for seg in segs:
                    L = seg['STA Akhir (m)'] - seg['STA Awal (m)']
                    if L <= 0: continue
                    dx = 2.0; n_steps = int(L/dx)
                    if n_steps < 1: n_steps = 1; dx = L
                    
                    des_S = seg.get('Desain S', 0.001)
                    des_B = seg.get('Desain B (m)', 0.6)
                    des_m = seg.get('Desain m', 1.0)
                    
                    # FIX PENTING: Gunakan ABS agar input -1.5 tetap dianggap 1.5
                    max_drop = abs(seg.get('Max Drop (m)', 1.5))
                    
                    for i in range(n_steps+1):
                        x_curr = seg['STA Awal (m)'] + i*dx
                        
                        # Ambil elevasi tanah di titik ini untuk cek
                        z_ex_node = next((n['z'] for n in nodes_ex if abs(n['x'] - x_curr) < 0.1), z_curr)
                        
                        # LOGIKA DROP STRUCTURE:
                        # Jika elevasi desain (z_curr) lebih tinggi dari tanah (z_ex_node) melebihi batas (max_drop)
                        # Maka kita harus "Terjun" ke bawah mengikuti tanah
                        diff = z_curr - z_ex_node
                        
                        if diff > max_drop:
                            # Catat Bangunan Terjun
                            drop_height = diff - 0.2 # Sisakan sedikit freeboard
                            drop_structs.append({
                                "STA": x_curr,
                                "Elev Hulu": z_curr,
                                "Elev Hilir": z_ex_node - 0.5, # Tanam sedikit dari muka tanah
                                "Tinggi Terjun (m)": round(z_curr - (z_ex_node - 0.5), 2)
                            })
                            # Reset Elevasi Dasar Desain
                            z_curr = z_ex_node - 0.5 
                        
                        nodes_des.append({
                            "x": x_curr, "z": z_curr,
                            "b": des_B, "m": des_m,
                            "n": 0.017, # Lining Beton
                            "h_ch": seg.get('Tinggi Saluran H (m)', 1.5),
                            "Q": seg.get('Debit Q (m3/s)', 0.5)
                        })
                        z_curr -= dx * des_S # Turun sesuai slope desain
                        
                st.session_state['res_des'] = calculate_profiles(nodes_des, 0.5, 0.5, force_subcritical=True)
                st.session_state['drop_list'] = drop_structs
                st.success("Analisis Selesai! Cek Tab Rekap Terjun.")
            
        except Exception as e: st.error(f"Error: {e}")

# --- 7. TABS HASIL ---
t1, t2, t3, t4, t5 = st.tabs(["📝 Input", "📈 Long Section", "🚧 Rekap Terjun", "❌ Cross Section", "📦 Export"])

with t1:
    st.info("💡 Tips: Masukkan 'Max Drop' angka positif (misal 1.5). Jika minus, sistem otomatis memperbaikinya.")
    st.session_state['df_pro'] = st.data_editor(st.session_state['df_pro'], num_rows="dynamic", use_container_width=True)

with t2:
    if st.session_state['res_ex']:
        rex = st.session_state['res_ex']
        rdes = st.session_state['res_des']
        
        fig, ax = plt.subplots(figsize=(12, 6))
        # Plot Eksisting (Putus-putus Abu)
        ax.plot([n['x'] for n in rex], [n['z'] for n in rex], 'k--', alpha=0.4, label='Tanah Asli')
        
        # Plot Desain
        if rdes:
            # Dasar Saluran (Coklat Tebal)
            ax.plot([n['x'] for n in rdes], [n['z'] for n in rdes], 'brown', linewidth=2, label='Dasar Desain')
            # Muka Air (Biru)
            ax.plot([n['x'] for n in rdes], [n['ws'] for n in rdes], 'b-', linewidth=1.5, label='Muka Air')
            # Arsir Air
            ax.fill_between([n['x'] for n in rdes], [n['z'] for n in rdes], [n['ws'] for n in rdes], color='cyan', alpha=0.3)
            
            # Gambar Drop Structures (Garis Vertikal Merah)
            drops = st.session_state['drop_list']
            for d in drops:
                ax.vlines(x=d['STA'], ymin=d['Elev Hilir'], ymax=d['Elev Hulu'], colors='red', linestyles='solid', linewidth=2)
        
        ax.set_title("Longitudinal Profile")
        ax.set_xlabel("Station (m)"); ax.set_ylabel("Elevasi (m)")
        ax.legend(); ax.grid(True, linestyle=':')
        st.pyplot(fig)
    else: st.info("Klik RUN dulu.")

with t3:
    st.subheader("📋 Rekapitulasi Bangunan Terjun")
    if st.session_state['drop_list']:
        df_drop = pd.DataFrame(st.session_state['drop_list'])
        st.dataframe(df_drop.style.format("{:.2f}"), use_container_width=True)
        st.caption("Bangunan terjun ditambahkan otomatis saat elevasi desain > tanah asli melebihi batas 'Max Drop'.")
    else:
        st.info("Tidak ada bangunan terjun yang diperlukan (Slope tanah landai).")

with t4:
    if st.session_state['res_des']:
        st.subheader("Visualisasi Potongan Melintang (Desain)")
        nodes = st.session_state['res_des']
        stas = [n['x'] for n in nodes]
        sel_sta = st.select_slider("Pilih Station (STA)", options=stas)
        
        node = next((n for n in nodes if n['x'] == sel_sta), None)
        if node:
            fig_cs, ax_cs = plt.subplots(figsize=(8, 4))
            b, m, h, z = node['b'], node['m'], node['h_ch'], node['z']
            ws = node['ws']
            
            # Gambar Trapezium
            top_w = b + 2*m*h
            x_pts = [-top_w/2, -b/2, b/2, top_w/2]
            y_pts = [z+h, z, z, z+h]
            ax_cs.plot(x_pts, y_pts, 'k-', lw=2, label='Saluran')
            
            # Gambar Air
            if ws > z:
                y_depth = ws - z
                top_w_air = b + 2*m*y_depth
                ax_cs.fill([-top_w_air/2, top_w_air/2, b/2, -b/2], [ws, ws, z, z], 'cyan', alpha=0.6, label='Air')
            
            ax_cs.set_title(f"Cross Section STA {sel_sta:.2f}")
            ax_cs.set_aspect('equal')
            ax_cs.legend(); ax_cs.grid(True)
            st.pyplot(fig_cs)

with t5:
    c1, c2 = st.columns(2)
    with c1:
        st.info("Export Long Section (Distorsi)")
        dist = st.slider("Faktor Distorsi Vertikal (V)", 1, 20, 10)
        if st.session_state['res_ex']:
            scr_long = generate_long_scr(st.session_state['res_ex'], st.session_state['res_des'], dist)
            st.download_button("📥 Download Long Section (.SCR)", scr_long, "LongSection.scr")
    with c2:
        st.info("Export Cross Section (BBWS)")
        if st.session_state['res_des']:
            scr_cs = generate_cs_scr(st.session_state['res_des'], "DESAIN")
            st.download_button("📥 Download Cross Section (.SCR)", scr_cs, "CrossSection.scr")
