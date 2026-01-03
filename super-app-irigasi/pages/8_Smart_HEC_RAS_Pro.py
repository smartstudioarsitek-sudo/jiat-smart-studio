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

# --- 1. ENGINE HIDROLIKA (MATH UPGRADE: TRAPEZOIDAL SUPPORT) ---

def get_critical_depth(Q, b, m):
    """
    Menghitung Critical Depth (Yc) untuk penampang Trapesium/Persegi.
    Menggunakan Metode Bisection karena persamaan Yc Trapesium tidak bisa diselesaikan analitik langsung.
    Target: Froude Number = 1 -> (Q^2 * T) / (g * A^3) = 1
    """
    g = 9.81
    y_min, y_max = 0.01, 20.0
    
    for _ in range(30): # 30 Iterasi cukup presisi
        y = (y_min + y_max) / 2
        A = (b + m * y) * y
        T = b + 2 * m * y
        
        if A <= 0: A = 0.001
        
        # Froude Check: g*A^3 - Q^2*T = 0
        f_val = 9.81 * (A**3) - (Q**2) * T
        
        if abs(f_val) < 0.01: return y
        
        if f_val < 0: # Aliran Superkritis (A terlalu kecil)
            y_min = y
        else:
            y_max = y
            
    return (y_min + y_max) / 2

def get_geom_props(y, b, m, Q):
    """
    Menghitung Properti Geometri + Momentum (Specific Force) yang BENAR untuk Trapesium.
    """
    if y <= 0.001: y = 0.001
    A = (b + m * y) * y
    P = b + 2 * y * np.sqrt(1 + m**2)
    R = A / P if P > 0 else 0
    T = b + 2 * m * y
    
    # --- KOREKSI MOMENTUM (Trapezoidal Exact Formula) ---
    # Momentum (M) = Q^2/(gA) + A * y_centroid
    # Suku Hidrostatis (A * y_centroid) untuk trapesium:
    # Integral (y*dA) -> (y^2/2)*b + (y^3/3)*m
    
    hydrostatic_term = ((y**2)/2) * b + ((y**3)/3) * m
    
    g = 9.81
    if A > 0:
        M = (Q**2)/(g*A) + hydrostatic_term 
    else: 
        M = 0
        
    return A, P, R, T, M

def solve_energy_step(y_known, Q, n, Z1, Z2, b, m, dx, mode):
    g = 9.81
    # 1 = Known, 2 = Target
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
        
        if mode == 'sub': return H2 - (H1 + loss) # Mundur (Hulu = Hilir + Loss)
        else: return H1 - (H2 + loss) # Maju (Hilir = Hulu - Loss)

    # Bisection Solver
    y_min, y_max = 0.01, 50.0
    for _ in range(50):
        y_mid = (y_min + y_max)/2
        err = func(y_mid)
        if abs(err) < 0.001: return y_mid
        
        if mode == 'sub': # Mencari Y > Yc (Subkritis)
            if err > 0: y_max = y_mid
            else: y_min = y_mid
        else: # Mencari Y < Yc (Superkritis)
            if err > 0: y_min = y_mid
            else: y_max = y_mid
            
    return (y_min + y_max)/2

# --- 2. LOGIC ALGORITMA MIXED FLOW ---
def calculate_profiles(nodes, Q, boundary_down, boundary_up):
    
    # --- PRE-CALCULATION (YC CORRECT) ---
    for n in nodes:
        # Panggil fungsi Yc Iteratif yang baru (Trapezoid Correct)
        n['yc'] = get_critical_depth(Q, n['b'], n['m'])
        
        # Init placeholder
        n['y_sub'] = 0.0
        n['y_sup'] = 0.0
        n['y_final'] = 0.0
    
    # --- PASS 1: SUBCRITICAL (MUNDUR) ---
    nodes[-1]['y_sub'] = boundary_down
    for i in range(len(nodes)-2, -1, -1):
        dx = nodes[i+1]['x'] - nodes[i]['x']
        known = nodes[i+1]
        target = nodes[i]
        yc = target['yc']
        
        try:
            y_calc = solve_energy_step(known['y_sub'], Q, target['n'], known['z'], target['z'], target['b'], target['m'], dx, 'sub')
            # Filter: Subkritis tidak boleh nembus Super (Y < Yc)
            if y_calc < yc: y_calc = yc + 0.05
        except: y_calc = yc + 0.05
        target['y_sub'] = y_calc

    # --- PASS 2: SUPERCRITICAL (MAJU) ---
    nodes[0]['y_sup'] = boundary_up
    for i in range(1, len(nodes)):
        dx = nodes[i]['x'] - nodes[i-1]['x']
        known = nodes[i-1]
        target = nodes[i]
        yc = target['yc']
        
        try:
            y_calc = solve_energy_step(known['y_sup'], Q, target['n'], known['z'], target['z'], target['b'], target['m'], dx, 'sup')
            # Filter: Superkritis tidak boleh nembus Sub (Y > Yc)
            if y_calc > yc: y_calc = yc - 0.01
        except: y_calc = yc - 0.01
        target['y_sup'] = y_calc

    # --- PASS 3: MOMENTUM CHECK (MIXED) ---
    for n in nodes:
        # Hitung Momentum (Dengan Rumus Baru Trapesium)
        _, _, _, _, M_sub = get_geom_props(n['y_sub'], n['b'], n['m'], Q)
        _, _, _, _, M_sup = get_geom_props(n['y_sup'], n['b'], n['m'], Q)
        
        if M_sub >= M_sup:
            n['y_final'] = n['y_sub']
            n['regime'] = "Subcritical"
        else:
            n['y_final'] = n['y_sup']
            n['regime'] = "Supercritical"
            
        n['ws'] = n['z'] + n['y_final']
        n['ws_sub'] = n['z'] + n['y_sub']
        n['ws_sup'] = n['z'] + n['y_sup']
        n['crit_ws'] = n['z'] + n['yc']
        
        A, _, _, _, _ = get_geom_props(n['y_final'], n['b'], n['m'], Q)
        V = Q/A if A > 0 else 0
        n['eg'] = n['ws'] + (V**2)/(2*9.81)
        # Froude Trapesium: V / sqrt(g * A/T)
        T_top = n['b'] + 2*n['m']*n['y_final']
        D_hydraulic = A/T_top if T_top > 0 else 0
        n['fr'] = V / np.sqrt(9.81 * D_hydraulic) if D_hydraulic > 0 else 0

    return nodes

# --- 3. UI SETUP ---
REQUIRED_COLS = ["Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"]

def reset_data():
    return pd.DataFrame([["S1", 0, 50, 100, 99.5, 2.0, 1.0, 0.017]], columns=REQUIRED_COLS)

if 'df_pro' not in st.session_state: st.session_state['df_pro'] = reset_data()
if 'q_pro' not in st.session_state: st.session_state['q_pro'] = 0.24
if 'ws_down' not in st.session_state: st.session_state['ws_down'] = 0.5
if 'ws_up' not in st.session_state: st.session_state['ws_up'] = 0.2 

st.markdown("""<div class="header-box"><h1>🚀 Smart HEC-RAS Ultimate</h1><p>Mixed Flow (Trapezoidal Corrected Momentum)</p></div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Parameter")
    st.session_state['q_pro'] = st.number_input("Debit (Q) m³/s", 0.01, 1000.0, st.session_state['q_pro'])
    
    st.divider()
    st.subheader("🌊 Boundary Conditions")
    st.session_state['ws_up'] = st.number_input("Hulu: Kedalaman Awal (m)", 0.01, 20.0, st.session_state['ws_up'])
    st.session_state['ws_down'] = st.number_input("Hilir: Kedalaman Awal (m)", 0.01, 20.0, st.session_state['ws_down'])
    
    st.divider()
    # Excel Upload (Auto)
    up_file = st.file_uploader("Upload Excel", type=['xlsx'], key="xls_math_fix")
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
        
        # --- RUN MIXED FLOW SOLVER ---
        if len(nodes) > 0:
            nodes = calculate_profiles(nodes, st.session_state['q_pro'], st.session_state['ws_down'], st.session_state['ws_up'])
            
            # --- PREPARE PLOT DATA ---
            for n in nodes:
                profile['x'].append(n['x'])
                profile['z'].append(n['z'])
                profile['ws'].append(n['ws'])
                profile['ws_sub'].append(n['ws_sub'])
                profile['ws_sup'].append(n['ws_sup'])
                profile['eg'].append(n['eg'])
                profile['crit'].append(n['crit_ws'])
                final_data.append(n)

    except Exception as e: st.error(f"Error Calculation: {e}")

# --- 5. TABS ---
t1, t2, t3 = st.tabs(["📝 Input", "📈 Mixed Flow Profile", "📋 Laporan"])

with t1:
    st.data_editor(st.session_state['df_pro'], num_rows="dynamic", use_container_width=True)

with t2:
    if len(profile['x']) > 0:
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(profile['x'], profile['z'], 'k-', lw=2, label='Ground')
        ax.plot(profile['x'], profile['crit'], 'r--', lw=1, alpha=0.5, label='Critical Depth (Trapezoidal)')
        ax.plot(profile['x'], profile['ws_sub'], 'g:', lw=0.5, alpha=0.3, label='Subcritical Trial')
        ax.plot(profile['x'], profile['ws_sup'], 'm:', lw=0.5, alpha=0.3, label='Supercritical Trial')
        ax.plot(profile['x'], profile['ws'], 'b-', lw=2.5, label='Final W.S. (Mixed)')
        ax.fill_between(profile['x'], profile['z'], profile['ws'], color='#00eaff', alpha=0.4)
        ax.set_title(f"Mixed Flow Analysis (Trapezoidal Corrected) - Q = {st.session_state['q_pro']}")
        ax.set_xlabel("Station (m)"); ax.set_ylabel("Elevation (m)")
        ax.legend(loc='best'); ax.grid(True, ls=':', alpha=0.5)
        st.pyplot(fig)
    else: st.info("Data kosong.")

with t3:
    if final_data:
        res = pd.DataFrame(final_data)[["x", "seg", "z", "ws", "y_final", "fr", "regime"]]
        res.columns = ["Sta", "Segmen", "Elev Dasar", "W.S.", "Depth", "Froude", "Regime"]
        st.dataframe(res, use_container_width=True)
        st.download_button("Download CSV", res.to_csv(index=False).encode('utf-8'), "laporan_final_trapezoid.csv")
