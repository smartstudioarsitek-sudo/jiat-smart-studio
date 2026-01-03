import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import io
import json

# --- CONFIG ---
st.set_page_config(page_title="Smart HEC-RAS Pro", layout="wide", page_icon="🌊")

st.markdown("""
<style>
    .header-box { padding: 20px; background: linear-gradient(90deg, #000428, #004e92); color: white; border-radius: 8px; text-align: center; margin-bottom: 20px; }
    .metric-card { background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #004e92; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .metric-label { font-size: 12px; color: #666; margin-bottom: 0; }
    .metric-value { font-size: 18px; font-weight: bold; color: #333; margin: 0; }
    @media print { .stSidebar, header, footer { display: none !important; } }
</style>
""", unsafe_allow_html=True)

# --- 1. ENGINE HIDROLIKA (MATH CORRECT & ROBUST) ---

def get_critical_depth(Q, b, m):
    """Menghitung Critical Depth (Yc) Trapesium secara Iteratif."""
    g = 9.81
    y_min, y_max = 0.01, 20.0
    for _ in range(30):
        y = (y_min + y_max) / 2
        A = (b + m * y) * y
        T = b + 2 * m * y
        if A <= 0: A = 0.001
        f_val = 9.81 * (A**3) - (Q**2) * T # Froude check
        if abs(f_val) < 0.01: return y
        if f_val < 0: y_min = y
        else: y_max = y
    return (y_min + y_max) / 2

def get_geom_props(y, b, m, Q):
    """Menghitung Properti Geometri + Momentum Trapesium yang BENAR."""
    if y <= 0.001: y = 0.001
    A = (b + m * y) * y
    P = b + 2 * y * np.sqrt(1 + m**2)
    R = A / P if P > 0 else 0
    T = b + 2 * m * y
    
    # --- MOMENTUM TRAPESIUM ---
    hydrostatic_term = ((y**2)/2) * b + ((y**3)/3) * m
    g = 9.81
    if A > 0.0001:
        M = (Q**2)/(g*A) + hydrostatic_term 
    else: 
        M = 0
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
        if mode == 'sub': # Mencari Y > Yc
            if err > 0: y_max = y_mid 
            else: y_min = y_mid
        else: # Mencari Y < Yc
            if err > 0: y_min = y_mid
            else: y_max = y_mid
    return (y_min + y_max)/2

# --- 2. LOGIC ALGORITMA MIXED FLOW ---
def calculate_profiles(nodes, Q, boundary_down, boundary_up, force_super=False):
    
    # Pre-calc Yc & Init
    for n in nodes:
        n['yc'] = get_critical_depth(Q, n['b'], n['m'])
        n['y_sub'] = 0.0; n['y_sup'] = 0.0; n['y_final'] = 0.0 
    
    # PASS 1: SUBCRITICAL
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

    # PASS 2: SUPERCRITICAL
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

    # PASS 3: REGIME SELECTION
    for n in nodes:
        if force_super:
            if n['y_sup'] > 0.011 and n['y_sup'] < 49.0:
                n['y_final'] = n['y_sup']; n['regime'] = "Supercritical (Forced)"
            else:
                n['y_final'] = n['yc']; n['regime'] = "Critical (Fallback)"
        else:
            if n['y_sub'] <= 0.011 or n['y_sub'] > 49.0: M_sub = -1.0
            else: _, _, _, _, M_sub = get_geom_props(n['y_sub'], n['b'], n['m'], Q)

            if n['y_sup'] <= 0.011 or n['y_sup'] > 49.0: M_sup = -1.0
            else: _, _, _, _, M_sup = get_geom_props(n['y_sup'], n['b'], n['m'], Q)
            
            if M_sub == -1 and M_sup == -1: n['y_final'] = n['yc']; n['regime'] = "Critical (Fallback)"
            elif M_sub >= M_sup: n['y_final'] = n['y_sub']; n['regime'] = "Subcritical"
            else: n['y_final'] = n['y_sup']; n['regime'] = "Supercritical"
            
        # Final calculations
        n['ws'] = n['z'] + n['y_final']
        n['ws_sub'] = n['z'] + n['y_sub']
        n['ws_sup'] = n['z'] + n['y_sup']
        n['crit_ws'] = n['z'] + n['yc']
        
        A, P, R, T, _ = get_geom_props(n['y_final'], n['b'], n['m'], Q)
        V = Q/A if A > 0 else 0
        n['v'] = V # Store Velocity
        
        n['eg'] = n['ws'] + (V**2)/(2*9.81)
        D_hyd = A/T if T > 0 else 0
        n['fr'] = V / np.sqrt(9.81 * D_hyd) if D_hyd > 0 else 0
        
        # Save Geometry Details for View
        n['area'] = A; n['perim'] = P; n['radius'] = R; n['top_width'] = T

    return nodes

# --- 3. UI SETUP ---
REQUIRED_COLS = ["Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"]

def reset_data():
    return pd.DataFrame([["S1", 0, 50, 100, 99.5, 2.0, 1.0, 0.017]], columns=REQUIRED_COLS)

if 'df_pro' not in st.session_state: st.session_state['df_pro'] = reset_data()
if 'q_pro' not in st.session_state: st.session_state['q_pro'] = 0.24
if 'ws_down' not in st.session_state: st.session_state['ws_down'] = 0.5
if 'ws_up' not in st.session_state: st.session_state['ws_up'] = 0.2 

st.markdown("""<div class="header-box"><h1>🚀 Smart HEC-RAS Ultimate</h1><p>Comprehensive Open Channel Flow Analysis</p></div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Parameter Hidrolis")
    st.session_state['q_pro'] = st.number_input("Debit (Q) m³/s", 0.01, 1000.0, st.session_state['q_pro'])
    st.info("💡 **Tips:** Gunakan 'Auto' untuk umum. Gunakan 'Force Supercritical' jika ingin cek potensi gerusan.")
    force_super = st.checkbox("🔥 Force Supercritical", value=False)
    
    st.divider()
    st.subheader("🌊 Boundary Conditions")
    st.session_state['ws_up'] = st.number_input("Hulu (Super): Kedalaman (m)", 0.01, 20.0, st.session_state['ws_up'])
    st.session_state['ws_down'] = st.number_input("Hilir (Sub): Kedalaman (m)", 0.01, 20.0, st.session_state['ws_down'])
    
    st.divider()
    up_file = st.file_uploader("Upload Excel", type=['xlsx'], key="xls_rekap_v5")
    if up_file:
        try:
            df = pd.read_excel(up_file)
            def clean(t): return str(t).lower().replace(" ", "").replace("(m)", "").replace(".", "")
            df.columns = [clean(c) for c in df.columns]
            mapping = {
                "Nama Segmen": ["nama", "reach", "segmen"], "STA Awal (m)": ["staawal", "start", "hulu"],
                "STA Akhir (m)": ["staakhir", "end", "hilir"], "Elev Awal (m)": ["elevawal", "z1", "startelv"],
                "Elev Akhir (m)": ["elevakhir", "z2", "endelv"], "Lebar b (m)": ["lebar", "width", "b"],
                "Talud m": ["talud", "slope", "m", "z"], "Kekasaran n": ["kekasaran", "manning", "n"]
            }
            new_df = pd.DataFrame()
            found=0
            for k,v in mapping.items():
                for x in v:
                    match = next((c for c in df.columns if x in c), None)
                    if match: new_df[k]=df[match]; found+=1; break
            if found>=5: 
                for r in REQUIRED_COLS: 
                    if r not in new_df.columns: new_df[r] = 0
                st.session_state['df_pro'] = new_df
        except: pass
    if st.button("Reset Data"): st.session_state['df_pro'] = reset_data(); st.rerun()

# --- 4. MAIN PROCESS ---
df = st.session_state['df_pro']
profile = {'x': [], 'z': [], 'ws': [], 'eg': [], 'crit': []}
final_data = []
all_nodes = [] 

if not df.empty:
    try:
        df = df.sort_values(by="STA Awal (m)")
        segments = df.to_dict('records')
        dx_step = 2.0 
        nodes = []
        
        # --- GENERATE NODES ---
        for idx, seg in enumerate(segments):
            L = seg["STA Akhir (m)"] - seg["STA Awal (m)"]
            if L <= 0: continue
            n_steps = int(L / dx_step); 
            if n_steps < 1: n_steps = 1
            real_dx = L / n_steps
            z_s, z_e = seg["Elev Awal (m)"], seg["Elev Akhir (m)"]
            slope = (z_s - z_e) / L
            
            start_i = 1 if idx > 0 else 0
            for i in range(start_i, n_steps + 1):
                nodes.append({
                    "x": seg["STA Awal (m)"] + i * real_dx,
                    "z": z_s - (i * real_dx * slope),
                    "b": seg["Lebar b (m)"], "m": seg["Talud m"], "n": seg["Kekasaran n"], "seg": seg["Nama Segmen"],
                    "slope_local": slope
                })
        
        # --- RUN SOLVER ---
        if len(nodes) > 0:
            nodes = calculate_profiles(nodes, st.session_state['q_pro'], st.session_state['ws_down'], st.session_state['ws_up'], force_super)
            all_nodes = nodes 
            
            for n in nodes:
                profile['x'].append(n['x']); profile['z'].append(n['z']); profile['ws'].append(n['ws'])
                profile['eg'].append(n['eg']); profile['crit'].append(n['crit_ws'])
                final_data.append(n)

    except Exception as e: st.error(f"Error Calculation: {e}")

# --- 5. TABS VISUALISASI ---
t1, t2, t3, t4, t5 = st.tabs(["📝 Input Geometri", "📈 Profil Memanjang", "❌ Cross Section", "📑 Rekap per Segmen (AutoCAD)", "📋 Laporan Detail"])

with t1:
    st.data_editor(st.session_state['df_pro'], num_rows="dynamic", use_container_width=True)

with t2:
    if len(profile['x']) > 0:
        # PENGATURAN PLOT PROFESIONAL
        fig, ax = plt.subplots(figsize=(14, 8)) # Ukuran lebih besar/lebar
        
        # 1. Plot Utama
        ax.plot(profile['x'], profile['z'], 'k-', lw=2.5, label='Dasar Saluran (Ground)')
        ax.plot(profile['x'], profile['ws'], 'b-', lw=2, label='Muka Air (W.S.)')
        ax.fill_between(profile['x'], profile['z'], profile['ws'], color='#00eaff', alpha=0.4)
        ax.plot(profile['x'], profile['crit'], 'r--', lw=1.5, alpha=0.7, label='Kedalaman Kritis (Critical)')
        ax.plot(profile['x'], profile['eg'], 'g-.', lw=1, alpha=0.8, label='Garis Energi (E.G.)')
        
        # 2. Grid Rinci (Informatif)
        ax.minorticks_on()
        ax.grid(which='major', linestyle='-', linewidth='0.5', color='gray', alpha=0.7)
        ax.grid(which='minor', linestyle=':', linewidth='0.5', color='gray', alpha=0.3)
        
        # 3. Label Segmen (Batas S1, S2, dst)
        res_df = pd.DataFrame(final_data)
        seg_starts = res_df.groupby('seg')['x'].min().sort_values()
        
        # Cari batas Y untuk menaruh label text (di bagian atas grafik)
        y_max_plot = max(max(profile['ws']), max(profile['eg'])) + 1.0
        y_min_plot = min(profile['z']) - 1.0
        
        for seg_name, x_start in seg_starts.items():
            ax.axvline(x=x_start, color='black', linestyle='--', linewidth=0.5, alpha=0.5)
            # Taruh text label segmen sedikit di kanan garis
            ax.text(x_start + 1, y_max_plot - 0.5, seg_name, rotation=90, fontsize=9, fontweight='bold', color='#333')

        # 4. Limit Skala (Auto-Zoom ke area sungai)
        ax.set_ylim(y_min_plot, y_max_plot)
        ax.set_xlim(min(profile['x']), max(profile['x']))
        
        # 5. Labeling
        ax.set_title(f"Profil Memanjang Hidrolis - Q = {st.session_state['q_pro']} m³/s", fontsize=14, fontweight='bold')
        ax.set_xlabel("Station / Jarak (m)", fontsize=11)
        ax.set_ylabel("Elevasi (m)", fontsize=11)
        ax.legend(loc='upper right', frameon=True, shadow=True)
        
        st.pyplot(fig)
        st.caption("✅ **Grafik Skala Teknik:** Menampilkan garis grid minor/mayor dan batas segmen untuk kemudahan pembacaan.")
    else: st.info("Data kosong.")

with t3:
    if len(all_nodes) > 0:
        st.subheader("Visualisasi Penampang (Cross Section)")
        sta_list = [n['x'] for n in all_nodes]
        sel_sta = st.select_slider("Pilih Station (m):", options=sta_list, value=sta_list[0])
        node = next((n for n in all_nodes if n['x'] == sel_sta), None)
        
        if node:
            c1, c2 = st.columns([2, 1])
            with c1:
                fig_cs, ax_cs = plt.subplots(figsize=(8, 5))
                b, m, z, y, ws = node['b'], node['m'], node['z'], node['y_final'], node['ws']
                depth_draw = max(y, node['yc']) * 1.5 if y > 0 else 1.0
                top_w_draw = b + 2 * m * depth_draw
                x_ground = [-top_w_draw/2, -b/2, b/2, top_w_draw/2]
                y_ground = [z + depth_draw, z, z, z + depth_draw]
                ax_cs.plot(x_ground, y_ground, 'k-', lw=3, label="Tanah")
                ax_cs.fill_between(x_ground, y_ground, min(y_ground), color='gray', alpha=0.3)
                if y > 0.001:
                    T = b + 2*m*y
                    x_water = [-T/2, T/2]; y_water = [ws, ws]
                    ax_cs.plot(x_water, y_water, 'b-', lw=2, label="Muka Air")
                    ax_cs.fill([-T/2, T/2, b/2, -b/2], [ws, ws, z, z], color='#00eaff', alpha=0.6)
                    ax_cs.hlines(node['eg'], -top_w_draw/2, top_w_draw/2, colors='green', linestyles='--', label="Energy")
                    ax_cs.hlines(node['crit_ws'], -top_w_draw/2, top_w_draw/2, colors='red', linestyles=':', label="Critical")
                ax_cs.set_title(f"Cross Section STA {sel_sta:.2f}"); ax_cs.legend(); ax_cs.grid(True, ls=':')
                st.pyplot(fig_cs)
            with c2:
                st.metric("Kedalaman Air (y)", f"{node['y_final']:.3f} m")
                st.metric("Kecepatan (V)", f"{node['v']:.3f} m/s")
                st.metric("Froude", f"{node['fr']:.2f}")
                st.divider()
                st.caption("Detail Dimensi:")
                st.text(f"Lebar Bawah (b) : {node['b']:.2f} m")
                st.text(f"Lebar Atas (T)  : {node['top_width']:.2f} m")
                st.text(f"Luas Basah (A)  : {node['area']:.2f} m²")

with t4:
    if final_data:
        st.subheader("📋 Rekapitulasi Data Per Segmen (Untuk AutoCAD)")
        st.caption("Ringkasan data Hulu & Hilir per segmen, lengkap dengan dimensi lebar.")
        
        res_df = pd.DataFrame(final_data)
        summary_list = []
        
        unique_segs = res_df['seg'].unique()
        for seg_name in unique_segs:
            seg_data = res_df[res_df['seg'] == seg_name]
            hulu = seg_data.iloc[0]
            hilir = seg_data.iloc[-1]
            
            summary_list.append({
                "Segmen": seg_name,
                "STA Awal": f"{hulu['x']:.2f}",
                "STA Akhir": f"{hilir['x']:.2f}",
                "Lebar Bawah (b)": f"{hulu['b']:.2f}",  
                "Lebar Atas Hulu (T)": f"{hulu['top_width']:.2f}",
                "Lebar Atas Hilir (T)": f"{hilir['top_width']:.2f}",
                "Elv Dasar Hulu": f"{hulu['z']:.3f}",
                "Elv Dasar Hilir": f"{hilir['z']:.3f}",
                "M.A. Hulu": f"{hulu['ws']:.3f}",
                "M.A. Hilir": f"{hilir['ws']:.3f}",
                "V Hulu": f"{hulu['v']:.3f}",
                "V Hilir": f"{hilir['v']:.3f}"
            })
            
        sum_df = pd.DataFrame(summary_list)
        st.dataframe(sum_df, width='stretch')
        st.download_button("Download Rekap AutoCAD (CSV)", sum_df.to_csv(index=False).encode('utf-8'), "Rekap_Segmen_AutoCAD.csv")

with t5:
    if final_data:
        res = pd.DataFrame(final_data)[["x", "seg", "z", "ws", "y_final", "fr", "regime", "v", "eg"]]
        res.columns = ["Sta", "Segmen", "Elev Dasar", "W.S.", "Depth", "Froude", "Regime", "Velocity", "E.G."]
        st.dataframe(res, width='stretch')
        st.download_button("Download Laporan Detail (CSV)", res.to_csv(index=False).encode('utf-8'), "Laporan_Smart_HEC_RAS_Final.csv")
