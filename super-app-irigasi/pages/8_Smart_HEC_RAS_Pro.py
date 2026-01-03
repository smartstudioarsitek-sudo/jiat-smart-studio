import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import json

# --- CONFIG ---
st.set_page_config(page_title="Smart HEC-RAS Pro", layout="wide", page_icon="🌊")

st.markdown("""
<style>
    .header-box { padding: 20px; background: linear-gradient(90deg, #000428, #004e92); color: white; border-radius: 8px; text-align: center; margin-bottom: 20px; }
    .success-box { padding: 10px; background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; border-radius: 5px; }
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

# --- 2. LOGIC ALGORITMA MIXED FLOW (WITH FORCE SUPERCRITICAL) ---
def calculate_profiles(nodes, Q, boundary_down, boundary_up, force_super=False):
    
    # Pre-calc Yc
    for n in nodes:
        n['yc'] = get_critical_depth(Q, n['b'], n['m'])
        n['y_sub'] = 0.0; n['y_sup'] = 0.0; n['y_final'] = 0.0 # Init
    
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

    # PASS 3: REGIME SELECTION (Auto vs Forced)
    for n in nodes:
        # 1. Jika User Memaksa Superkritis (Untuk Cek Gerusan/Erosi)
        if force_super:
            if n['y_sup'] > 0.011 and n['y_sup'] < 49.0:
                n['y_final'] = n['y_sup']
                n['regime'] = "Supercritical (Forced)"
            else:
                n['y_final'] = n['yc'] # Fallback
                n['regime'] = "Critical (Fallback)"
        
        # 2. Mode Otomatis (Smart Momentum Check)
        else:
            if n['y_sub'] <= 0.011 or n['y_sub'] > 49.0: M_sub = -1.0
            else: _, _, _, _, M_sub = get_geom_props(n['y_sub'], n['b'], n['m'], Q)

            if n['y_sup'] <= 0.011 or n['y_sup'] > 49.0: M_sup = -1.0
            else: _, _, _, _, M_sup = get_geom_props(n['y_sup'], n['b'], n['m'], Q)
            
            if M_sub == -1 and M_sup == -1:
                n['y_final'] = n['yc']
                n['regime'] = "Critical (Fallback)"
            elif M_sub >= M_sup: 
                n['y_final'] = n['y_sub']
                n['regime'] = "Subcritical"
            else: 
                n['y_final'] = n['y_sup']
                n['regime'] = "Supercritical"
            
        # Final calculations
        n['ws'] = n['z'] + n['y_final']
        n['ws_sub'] = n['z'] + n['y_sub']
        n['ws_sup'] = n['z'] + n['y_sup']
        n['crit_ws'] = n['z'] + n['yc']
        
        A, _, _, _, _ = get_geom_props(n['y_final'], n['b'], n['m'], Q)
        V = Q/A if A > 0 else 0
        n['eg'] = n['ws'] + (V**2)/(2*9.81)
        T_top = n['b'] + 2*n['m']*n['y_final']
        D_hyd = A/T_top if T_top > 0 else 0
        n['fr'] = V / np.sqrt(9.81 * D_hyd) if D_hyd > 0 else 0

    return nodes

# --- 3. UI SETUP ---
REQUIRED_COLS = ["Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"]

def reset_data():
    return pd.DataFrame([["S1", 0, 50, 100, 99.5, 2.0, 1.0, 0.017]], columns=REQUIRED_COLS)

if 'df_pro' not in st.session_state: st.session_state['df_pro'] = reset_data()
if 'q_pro' not in st.session_state: st.session_state['q_pro'] = 0.24
if 'ws_down' not in st.session_state: st.session_state['ws_down'] = 0.5
if 'ws_up' not in st.session_state: st.session_state['ws_up'] = 0.2 

st.markdown("""<div class="header-box"><h1>🚀 Smart HEC-RAS Ultimate</h1><p>Mixed Flow • Trapezoidal Correct • Infinite Fix</p></div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Parameter Hidrolis")
    st.session_state['q_pro'] = st.number_input("Debit (Q) m³/s", 0.01, 1000.0, st.session_state['q_pro'])
    
    # --- FITUR BARU: FORCE SUPERCRITICAL ---
    st.info("💡 **Tips:** Gunakan 'Auto' untuk umum. Gunakan 'Force Supercritical' jika ingin mendesain peredam energi di saluran curam.")
    force_super = st.checkbox("🔥 Force Supercritical (Paksa Aliran Deras)", value=False)
    
    st.divider()
    st.subheader("🌊 Boundary Conditions")
    st.session_state['ws_up'] = st.number_input("Hulu (Super): Kedalaman (m)", 0.01, 20.0, st.session_state['ws_up'])
    st.session_state['ws_down'] = st.number_input("Hilir (Sub): Kedalaman (m)", 0.01, 20.0, st.session_state['ws_down'])
    
    st.divider()
    up_file = st.file_uploader("Upload Excel", type=['xlsx'], key="xls_gold")
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
profile = {'x': [], 'z': [], 'ws': [], 'ws_sub': [], 'ws_sup': [], 'eg': [], 'crit': []}
final_data = []

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
                    "b": seg["Lebar b (m)"], "m": seg["Talud m"], "n": seg["Kekasaran n"], "seg": seg["Nama Segmen"]
                })
        
        # --- RUN SOLVER ---
        if len(nodes) > 0:
            nodes = calculate_profiles(nodes, st.session_state['q_pro'], st.session_state['ws_down'], st.session_state['ws_up'], force_super)
            
            # --- PLOT DATA ---
            for n in nodes:
                profile['x'].append(n['x']); profile['z'].append(n['z']); profile['ws'].append(n['ws'])
                profile['ws_sub'].append(n['ws_sub']); profile['ws_sup'].append(n['ws_sup'])
                profile['eg'].append(n['eg']); profile['crit'].append(n['crit_ws'])
                final_data.append(n)

    except Exception as e: st.error(f"Error Calculation: {e}")

# --- 5. TABS ---
t1, t2, t3 = st.tabs(["📝 Input", "📈 Profil Hidrolis", "📋 Laporan & Download"])

with t1:
    st.data_editor(st.session_state['df_pro'], num_rows="dynamic", use_container_width=True)

with t2:
    if len(profile['x']) > 0:
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(profile['x'], profile['z'], 'k-', lw=2, label='Dasar Saluran')
        ax.plot(profile['x'], profile['crit'], 'r--', lw=1, alpha=0.5, label='Critical Depth')
        
        # Grafik Utama
        ax.plot(profile['x'], profile['ws'], 'b-', lw=2.5, label='Muka Air (W.S.)')
        ax.fill_between(profile['x'], profile['z'], profile['ws'], color='#00eaff', alpha=0.4)
        ax.plot(profile['x'], profile['eg'], 'g--', lw=1, label='Energy Grade Line')
        
        ax.set_title(f"Profil Hidrolis - Q = {st.session_state['q_pro']} m³/s")
        ax.set_xlabel("Station (m)"); ax.set_ylabel("Elevation (m)")
        ax.legend(loc='best'); ax.grid(True, ls=':', alpha=0.5)
        st.pyplot(fig)
        
        if force_super:
            st.warning("⚠️ **Mode Force Supercritical Aktif!** Grafik ini menunjukkan kemungkinan kecepatan maksimum. Gunakan untuk desain proteksi gerusan.")
        else:
            st.success("✅ **Mode Auto (Momentum Balance).** Grafik menunjukkan profil aliran yang paling stabil secara fisika.")
    else: st.info("Data kosong.")

with t3:
    if final_data:
        res = pd.DataFrame(final_data)[["x", "seg", "z", "ws", "y_final", "fr", "regime"]]
        res.columns = ["Sta", "Segmen", "Elev Dasar", "W.S.", "Depth", "Froude", "Regime"]
        st.dataframe(res, use_container_width=True)
        st.download_button("Download Laporan Lengkap (CSV)", res.to_csv(index=False).encode('utf-8'), "Laporan_Smart_HEC_RAS_Final.csv")
