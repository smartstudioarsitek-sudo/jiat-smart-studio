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
    .header-box {
        padding: 20px; background: linear-gradient(90deg, #000428, #004e92); 
        color: white; border-radius: 8px; text-align: center; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .metric-card { background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #004e92; margin-bottom: 10px; }
    @media print {
        .stSidebar, header, footer, .stFileUploader, .stButton, .stTabs nav { display: none !important; }
        .block-container { padding-top: 0 !important; }
    }
</style>
""", unsafe_allow_html=True)

# --- 1. ENGINE HIDROLIKA (SMART DROP DETECTION) ---
def get_geom_props(y, b, m):
    if y <= 0: return 0.001, 0.001, 0.001, 0.001
    A = (b + m * y) * y
    P = b + 2 * y * np.sqrt(1 + m**2)
    R = A / P if P > 0 else 0
    T = b + 2 * m * y
    return A, P, R, T

def solve_manning_y(Q, n, b, S, m):
    if S <= 0: S = 0.0001
    y_low, y_high = 0.001, 50.0
    for _ in range(50):
        y_mid = (y_low + y_high) / 2
        A, P, R, T = get_geom_props(y_mid, b, m)
        Q_calc = (1/n) * A * (R**(2/3)) * (S**0.5)
        if abs(Q_calc - Q) < 0.001: return y_mid
        if Q_calc < Q: y_low = y_mid
        else: y_high = y_mid
    return (y_low + y_high) / 2

def solve_energy_equation(y_guess, Q, n, Z1, Z2, y1, b, m, L, dx, mode='subcritical'):
    g = 9.81
    # 1 = Titik Referensi (Known), 2 = Titik Target (Unknown)
    A1, P1, R1, T1 = get_geom_props(y1, b, m)
    V1 = Q / A1
    H1 = Z1 + y1 + (V1**2) / (2*g) # Total Head di Titik Known
    
    # --- DETEKSI TERJUNAN (CHOKING CHECK) ---
    # Hitung Energi Minimum yang dibutuhkan di Titik Target (Critical Energy)
    yc_target = ( (Q**2) / (g * b**2) )**(1/3) # Approx rectangular
    Ec_target = Z2 + yc_target + (Q/(b*yc_target))**2 / (2*g)
    
    # Jika kita hitung mundur (Subkritis) dan Energi Hilir (H1) lebih rendah dari 
    # Energi Minimum yang dibutuhkan Hulu (Ec_target) karena beda tinggi dasar (Z2 > Z1),
    # Maka terjadi Choking -> Reset ke Critical Depth
    if mode == 'subcritical' and H1 < Ec_target:
        return yc_target

    # Fungsi Solver Normal
    def energy_func(y2):
        A2, P2, R2, T2 = get_geom_props(y2, b, m)
        if A2 <= 0: return 1000.0
        V2 = Q / A2
        H2 = Z2 + y2 + (V2**2) / (2*g)
        
        Sf1 = (n * V1)**2 / (R1**(4/3)) if R1 > 0 else 0
        Sf2 = (n * V2)**2 / (R2**(4/3)) if R2 > 0 else 0
        Sf_avg = (Sf1 + Sf2) / 2
        h_f = Sf_avg * dx
        
        if mode == 'subcritical': return H2 - (H1 + h_f) # Hulu = Hilir + Loss
        else: return H1 - (H2 + h_f) # Hilir = Hulu - Loss

    y_min, y_max = 0.01, 50.0
    for _ in range(50):
        y_mid = (y_min + y_max) / 2
        err = energy_func(y_mid)
        if abs(err) < 0.001: return y_mid
        
        if mode == 'subcritical':
            if err > 0: y_max = y_mid 
            else: y_min = y_mid
        else:
            if err > 0: y_min = y_mid
            else: y_max = y_mid
            
    return (y_min + y_max) / 2

# --- 2. INISIALISASI & SIDEBAR ---
REQUIRED_COLS = ["Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", "Lebar b (m)", "Talud m", "Kekasaran n"]

def reset_data():
    return pd.DataFrame([["S1", 0, 50, 100, 99.5, 2.0, 1.0, 0.017]], columns=REQUIRED_COLS)

if 'df_pro' not in st.session_state: st.session_state['df_pro'] = reset_data()
if 'q_pro' not in st.session_state: st.session_state['q_pro'] = 0.24
if 'ws_known' not in st.session_state: st.session_state['ws_known'] = 0.5

# --- UI ---
st.markdown("""
<div class="header-box">
    <h1 style="margin:0; font-size: 32px;">🚀 Smart HEC-RAS Pro</h1>
    <p style="margin-top:5px; font-size: 14px; opacity: 0.9;">Standard Step Method Solver (Drop Structure Support)</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Boundary Condition")
    st.session_state['q_pro'] = st.number_input("Debit (Q) m³/s", 0.01, 1000.0, st.session_state['q_pro'])
    calc_mode = st.radio("Mode Analisa", ["Subkritis (Hilir -> Hulu)", "Superkritis (Hulu -> Hilir)"], index=0)
    mode_key = 'subcritical' if "Sub" in calc_mode else 'supercritical'
    
    st.divider()
    
    if mode_key == 'subcritical':
        st.subheader("🌊 Batas Hilir")
        df_curr = st.session_state['df_pro']
        if not df_curr.empty:
            last_seg = df_curr.iloc[-1]
            S0 = (last_seg['Elev Awal (m)'] - last_seg['Elev Akhir (m)']) / (last_seg['STA Akhir (m)'] - last_seg['STA Awal (m)'])
            yn = solve_manning_y(st.session_state['q_pro'], last_seg['Kekasaran n'], last_seg['Lebar b (m)'], S0, last_seg['Talud m'])
            st.caption(f"Normal Depth Hilir: {yn:.2f} m")
            if st.button("Pakai Normal Depth"): st.session_state['ws_known'] = float(yn); st.rerun()
        boundary_y = st.number_input("Kedalaman Air Hilir (m)", 0.01, 50.0, st.session_state['ws_known'])
    else:
        st.subheader("🌊 Batas Hulu")
        boundary_y = st.number_input("Kedalaman Air Hulu (m)", 0.01, 50.0, st.session_state['ws_known'])
    
    st.divider()
    
    st.subheader("📥 Excel & Project")
    df_temp = pd.DataFrame([["S1", 0, 50, 100, 99.5, 0.6, 1.0, 0.017]], columns=REQUIRED_COLS)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer: df_temp.to_excel(writer, index=False)
    st.download_button("Template Excel", buf.getvalue(), "Template_Pro.xlsx")
    
    up_file = st.file_uploader("Upload Excel", type=['xlsx'])
    if up_file:
        try:
            df_up = pd.read_excel(up_file)
            def clean(t): return str(t).lower().replace(" ", "").replace("(m)", "").replace(".", "")
            df_up.columns = [clean(c) for c in df_up.columns]
            mapping = {
                "Nama Segmen": ["nama", "reach", "segmen"], "STA Awal (m)": ["staawal", "start", "hulu"],
                "STA Akhir (m)": ["staakhir", "end", "hilir"], "Elev Awal (m)": ["elevawal", "z1", "startelv"],
                "Elev Akhir (m)": ["elevakhir", "z2", "endelv"], "Lebar b (m)": ["lebar", "width", "b"],
                "Talud m": ["talud", "slope", "m", "z"], "Kekasaran n": ["kekasaran", "manning", "n"]
            }
            new_data = pd.DataFrame()
            found_count = 0
            for sys_col, keywords in mapping.items():
                for kw in keywords:
                    match = next((c for c in df_up.columns if kw in c), None)
                    if match:
                        new_data[sys_col] = df_up[match]; found_count += 1; break
            if found_count >= 6: st.session_state['df_pro'] = new_data; st.success("Loaded!"); st.rerun()
        except: st.error("Gagal load Excel.")

    proj = {'q': st.session_state['q_pro'], 'segments': st.session_state['df_pro'].to_dict('records')}
    st.download_button("Simpan Project (.json)", json.dumps(proj), "pro.json", "application/json")
    up_json = st.file_uploader("Buka Project (.json)", type=['json'])
    if up_json:
        try:
            L = json.load(up_json); st.session_state['q_pro'] = float(L['q']); st.session_state['df_pro'] = pd.DataFrame(L['segments']); st.rerun()
        except: pass
    if st.button("Reset"): st.session_state['df_pro'] = reset_data(); st.rerun()

# --- 3. MAIN LOGIC ---
df = st.session_state['df_pro']
profile = {'x': [], 'z': [], 'ws': [], 'eg': [], 'crit': []}
final_data = []

if not df.empty:
    try:
        df = df.sort_values(by="STA Awal (m)")
        segments = df.to_dict('records')
        dx_step = 5.0
        nodes = []
        
        for seg in segments:
            L = seg["STA Akhir (m)"] - seg["STA Awal (m)"]
            if L <= 0: continue
            n_steps = int(L / dx_step); 
            if n_steps < 1: n_steps = 1
            real_dx = L / n_steps
            z_s, z_e = seg["Elev Awal (m)"], seg["Elev Akhir (m)"]
            slope = (z_s - z_e) / L
            
            for i in range(n_steps + 1):
                nodes.append({
                    "x": seg["STA Awal (m)"] + i * real_dx,
                    "z": z_s - (i * real_dx * slope),
                    "b": seg["Lebar b (m)"], "m": seg["Talud m"], "n": seg["Kekasaran n"], "seg": seg["Nama Segmen"]
                })
        
        Q = st.session_state['q_pro']
        
        if mode_key == 'subcritical':
            nodes[-1]['y'] = boundary_y
            nodes[-1]['ws'] = nodes[-1]['z'] + boundary_y
            
            for i in range(len(nodes)-2, -1, -1):
                dx = nodes[i+1]['x'] - nodes[i]['x']
                # Cek Diskontinuitas Geometri (Junction Segmen)
                if dx == 0: 
                    # Jika dx=0 (titik sambung), paksa energi kontinuitas, tapi jika drop, reset ke critical
                    pass 
                
                y_res = solve_energy_equation(
                    y_guess=nodes[i+1]['y'], Q=Q, n=nodes[i]['n'],
                    Z1=nodes[i+1]['z'], Z2=nodes[i]['z'], y1=nodes[i+1]['y'],
                    b=nodes[i]['b'], m=nodes[i]['m'], L=dx, dx=dx, mode='subcritical'
                )
                nodes[i]['y'] = y_res
                nodes[i]['ws'] = nodes[i]['z'] + y_res
        else:
            nodes[0]['y'] = boundary_y
            nodes[0]['ws'] = nodes[0]['z'] + boundary_y
            for i in range(1, len(nodes)):
                dx = nodes[i]['x'] - nodes[i-1]['x']
                y_res = solve_energy_equation(
                    y_guess=nodes[i-1]['y'], Q=Q, n=nodes[i]['n'],
                    Z1=nodes[i-1]['z'], Z2=nodes[i]['z'], y1=nodes[i-1]['y'],
                    b=nodes[i]['b'], m=nodes[i]['m'], L=dx, dx=dx, mode='supercritical'
                )
                nodes[i]['y'] = y_res
                nodes[i]['ws'] = nodes[i]['z'] + y_res

        for n in nodes:
            y, b, m = n['y'], n['b'], n['m']
            A, P, R, T = get_geom_props(y, b, m)
            V = Q/A if A>0 else 0
            n['eg'] = n['ws'] + (V**2)/(19.62)
            yc = ((Q**2)/(9.81 * b**2))**(1/3)
            n['crit_ws'] = n['z'] + yc
            final_data.append(n)
            profile['x'].append(n['x']); profile['z'].append(n['z'])
            profile['ws'].append(n['ws']); profile['eg'].append(n['eg']); profile['crit'].append(n['crit_ws'])

    except Exception as e: st.error(f"Error: {e}")

# --- 4. TABS ---
t1, t2, t3 = st.tabs(["📝 Input", "📈 Grafik Profil", "📋 Laporan"])

with t1:
    new_df = st.data_editor(st.session_state['df_pro'], num_rows="dynamic", use_container_width=True)
    if not new_df.equals(st.session_state['df_pro']): st.session_state['df_pro'] = new_df; st.rerun()

with t2:
    if len(profile['x']) > 0:
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(profile['x'], profile['z'], 'k-', lw=2, label='Dasar')
        ax.plot(profile['x'], profile['ws'], 'b-', lw=2, label='Muka Air')
        ax.fill_between(profile['x'], profile['z'], profile['ws'], color='#00eaff', alpha=0.6)
        ax.plot(profile['x'], profile['crit'], 'r:', label='Kritis')
        ax.plot(profile['x'], profile['eg'], 'g--', label='Energi')
        ax.set_title(f"Profil Muka Air ({calc_mode})"); ax.legend(); ax.grid(True, ls=':')
        st.pyplot(fig)
    else: st.info("No Data")

with t3:
    if final_data:
        res = pd.DataFrame(final_data)
        res = res[["x", "seg", "z", "ws", "y", "eg", "crit_ws"]]
        res.columns = ["Sta", "Segmen", "Elev Dasar", "W.S.", "Depth", "E.G.", "Crit W.S."]
        st.dataframe(res, use_container_width=True)
        csv = res.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, "laporan.csv", "text/csv")
