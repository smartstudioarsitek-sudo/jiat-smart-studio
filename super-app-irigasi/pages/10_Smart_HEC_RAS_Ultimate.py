import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import json

# --- 1. KONFIGURASI HALAMAN & CSS ---
st.set_page_config(page_title="Smart HEC-RAS Ultimate V3.2", layout="wide", page_icon="🏗️")

st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; font-weight: bold; }
    .run-btn { background-color: #28a745 !important; color: white !important; }
    .header-box { padding: 15px; background: linear-gradient(90deg, #134E5E, #71B280); color: white; border-radius: 10px; text-align: center; margin-bottom: 20px; }
    .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# --- 2. ENGINE HIDROLIKA (FUNGSI HITUNGAN) ---
def get_critical_depth(Q, b, m):
    y_min, y_max = 0.01, 20.0
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

def calculate_profiles(nodes, boundary_down, boundary_up, force_super=False):
    # 1. Hitung Critical Depth
    for n in nodes:
        Q_local = n.get('Q', 0.5)
        n['yc'] = get_critical_depth(Q_local, n['b'], n['m'])
        n['y_sub'] = 0.0; n['y_sup'] = 0.0; n['y_final'] = 0.0 
    
    # Subcritical Calculation (Hilir ke Hulu)
    nodes[-1]['y_sub'] = boundary_down
    for i in range(len(nodes)-2, -1, -1):
        dx = nodes[i+1]['x'] - nodes[i]['x']
        known, target = nodes[i+1], nodes[i]
        Q_calc = target.get('Q', 0.5) 
        yc = target['yc']
        try:
            y_calc = solve_energy_step(known['y_sub'], Q_calc, target['n'], known['z'], target['z'], target['b'], target['m'], dx, 'sub')
            if y_calc < yc: y_calc = yc + 0.01 
        except: y_calc = yc + 0.01
        target['y_sub'] = y_calc

    # Supercritical Calculation (Hulu ke Hilir)
    nodes[0]['y_sup'] = boundary_up
    for i in range(1, len(nodes)):
        dx = nodes[i]['x'] - nodes[i-1]['x']
        known, target = nodes[i-1], nodes[i]
        Q_calc = target.get('Q', 0.5)
        yc = target['yc']
        try:
            y_calc = solve_energy_step(known['y_sup'], Q_calc, target['n'], known['z'], target['z'], target['b'], target['m'], dx, 'sup')
            if y_calc > yc: y_calc = yc - 0.01 
        except: y_calc = yc - 0.01
        target['y_sup'] = y_calc

    # Selection Logic
    for n in nodes:
        Q_local = n.get('Q', 0.5)
        if force_super:
            n['y_final'] = n['y_sup'] if (0.011 < n['y_sup'] < 49.0) else n['yc']
            n['regime'] = "Supercritical"
        else:
            n['y_final'] = n['y_sub']
            n['regime'] = "Subcritical"
        
        n['ws'] = n['z'] + n['y_final']
        n['crit_ws'] = n['z'] + n['yc']
        H_ch = n.get('h_ch', 1.5)
        n['bank_elev'] = n['z'] + H_ch
        n['freeboard'] = n['bank_elev'] - n['ws']
        
        A, P, R, T, _ = get_geom_props(n['y_final'], n['b'], n['m'], Q_local)
        V = Q_local/A if A > 0 else 0
        n['v'] = V 
        D_hyd = A/T if T > 0 else 0
        n['fr'] = V / np.sqrt(9.81 * D_hyd) if D_hyd > 0 else 0

    return nodes

# --- 3. FUNGSI EXPORT BBWS (CAD) ---
def generate_bbws_scr(nodes, dataset_name="DESAIN", distorsi_v=10):
    s = f"; --- SCRIPT BBWS STANDAR ({dataset_name}) ---\n"
    s += "OSMODE 0\nZOOM E\n"
    def fmt(x, y): return f"{x:.4f},{y * distorsi_v:.4f}"

    # Layering Standar BBWS
    layers = [
        (f"{dataset_name}_TANAH", 34, 'z'),
        (f"{dataset_name}_AIR", 150, 'ws'),
        (f"{dataset_name}_STRUKTUR", 7, 'bank_elev') 
    ]

    for lay_name, color, key in layers:
        s += f"-LAYER M {lay_name} C {color} {lay_name} \n_PLINE\n"
        for n in nodes: 
            val = n[key] if key != 'bank_elev' else (n['z'] + n['h_ch'])
            s += f"{fmt(n['x'], val)}\n"
        s += "\n"

    # Layer Teks
    s += f"-LAYER M {dataset_name}_TEKS C 2 {dataset_name}_TEKS \n"
    step = 5 if len(nodes) > 100 else 1
    for i, n in enumerate(nodes):
        if i % step == 0:
            s += f"-TEXT {fmt(n['x'], n['z'] - 2)} 0.5 90 STA {n['x']:.0f}\n"
    
    s += "ZOOM E\n"
    return s

# --- 4. STATE MANAGEMENT & DATA DEFAULT ---
if 'results_ex' not in st.session_state: st.session_state['results_ex'] = None

REQUIRED_COLS = [
    "Nama Segmen", "STA Awal (m)", "STA Akhir (m)", 
    "Elev Awal (m)", "Elev Akhir (m)", 
    "Debit Q (m3/s)", "Lebar b (m)", "Talud m", "Kekasaran n", "Tinggi Saluran H (m)",
    "Desain S", "Desain B (m)", "Desain m", "Max Drop (m)"
]

def reset_data():
    return pd.DataFrame([
        ["S1", 0, 50, 100, 99.5, 0.24, 2.0, 1.0, 0.017, 1.5, 0.001, 0.6, 1.0, 1.5]
    ], columns=REQUIRED_COLS)

if 'df_pro' not in st.session_state: st.session_state['df_pro'] = reset_data()
if 'ws_down' not in st.session_state: st.session_state['ws_down'] = 0.5
if 'ws_up' not in st.session_state: st.session_state['ws_up'] = 0.2

# --- 5. UI: SIDEBAR (IMPORT) ---
with st.sidebar:
    st.header("📂 Import Data")
    
    # --- BAGIAN IMPORT ---
    tab_ex, tab_gis, tab_csv = st.tabs(["📄 Excel", "🌍 GeoJSON", "🔢 CSV"])
    
    with tab_ex:
        st.info("Upload file .xlsx")
        
        buffer_template = io.BytesIO()
        with pd.ExcelWriter(buffer_template, engine='xlsxwriter') as writer:
            reset_data().to_excel(writer, index=False)
        st.download_button("📥 Download Template Excel", buffer_template.getvalue(), "Template_Saluran.xlsx")

        up_excel = st.file_uploader("Upload Excel", type=['xlsx'], key="xls_up")
        
        if up_excel:
            try:
                df = pd.read_excel(up_excel)
                df.columns = [c.strip() for c in df.columns]
                
                # Auto-Add Columns (Anti Error)
                defaults = {"Desain S": 0.001, "Desain B (m)": 0.6, "Desain m": 1.0, "Max Drop (m)": 1.5, "Debit Q (m3/s)": 0.5, "Tinggi Saluran H (m)": 1.5}
                for d_col, d_val in defaults.items():
                    if d_col not in df.columns: df[d_col] = d_val
                
                if "Elev Awal (m)" in df.columns:
                    st.session_state['df_pro'] = df
                    st.success("✅ Excel Berhasil Dimuat!")
                else:
                    st.error("❌ Kolom 'Elev Awal (m)' tidak ditemukan!")
            except Exception as e: st.error(f"Error: {e}")

    with tab_gis:
        st.caption("Upload GeoJSON LineString")
        up_geo = st.file_uploader("Upload GeoJSON", type=['geojson', 'json'])
        if up_geo and st.button("Load GIS"):
            try:
                data = json.load(up_geo)
                features = data.get('features', [])
                new_rows = []
                coords = features[0]['geometry']['coordinates']
                dist_acum = 0
                for i in range(len(coords)-1):
                    p1, p2 = coords[i], coords[i+1]
                    dist = np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
                    new_rows.append({
                        "Nama Segmen": f"S{i}", "STA Awal (m)": dist_acum, "STA Akhir (m)": dist_acum+dist,
                        "Elev Awal (m)": p1[2], "Elev Akhir (m)": p2[2],
                        "Debit Q (m3/s)": 0.5, "Lebar b (m)": 2.0, "Talud m": 1.0, "Kekasaran n": 0.025, "Tinggi Saluran H (m)": 1.5,
                        "Desain S": 0.001, "Desain B (m)": 0.6, "Desain m": 1.0, "Max Drop (m)": 1.5
                    })
                    dist_acum += dist
                st.session_state['df_pro'] = pd.DataFrame(new_rows)
                st.success(f"✅ GIS Loaded: {len(new_rows)} segments")
            except Exception as e: st.error("Gagal load GIS")

    st.divider()
    st.subheader("⚙️ Parameter")
    force_super = st.checkbox("Force Supercritical", False)
    
    if st.button("Reset Semua Data"):
        st.session_state['df_pro'] = reset_data()
        st.rerun()

# --- 6. UI: MAIN AREA ---
st.markdown('<div class="header-box"><h1>🏗️ Smart HEC-RAS Ultimate V3.2</h1><p>Input Excel • Run Analysis • Export BBWS CAD</p></div>', unsafe_allow_html=True)

# TOOLBAR
col1, col2, col3, col4 = st.columns([2, 2, 2, 3])

with col1:
    up_proj = st.file_uploader("📂 Buka Project (.json)", type=['json'], label_visibility='collapsed')
    if up_proj:
        st.session_state['df_pro'] = pd.DataFrame(json.load(up_proj))

with col2:
    proj_json = st.session_state['df_pro'].to_json(orient='records')
    st.download_button("💾 Simpan Project", proj_json, "Project.json", "application/json", use_container_width=True)

with col3:
    run_calc = st.button("🚀 RUN ANALISIS", type="primary", use_container_width=True)

with col4:
    st.caption("Klik RUN setelah update Excel/Tabel.")

# --- 7. LOGIKA RUNNING ---
if run_calc:
    with st.spinner("Sedang Menghitung..."):
        try:
            df = st.session_state['df_pro'].sort_values("STA Awal (m)")
            segments = df.to_dict('records')
            nodes_ex = []
            
            for idx, seg in enumerate(segments):
                L = seg.get('STA Akhir (m)', 0) - seg.get('STA Awal (m)', 0)
                if L <= 0: continue
                n_steps = max(1, int(L / 2.0))
                dx = L / n_steps
                z1 = seg.get('Elev Awal (m)', 0)
                z2 = seg.get('Elev Akhir (m)', 0)
                slope = (z1 - z2) / L
                
                # Parameter dengan Default (Anti Error)
                q_seg = seg.get('Debit Q (m3/s)', 0.5)
                if pd.isna(q_seg) or q_seg == '': q_seg = 0.5
                b_seg = seg.get('Lebar b (m)', 1.0)
                m_seg = seg.get('Talud m', 1.0)
                n_seg = seg.get('Kekasaran n', 0.025)
                h_seg = seg.get('Tinggi Saluran H (m)', 1.5)
                
                for i in range(n_steps + 1):
                    nodes_ex.append({
                        "x": seg['STA Awal (m)'] + i*dx,
                        "z": z1 - i*dx*slope,
                        "b": b_seg, "m": m_seg,
                        "n": n_seg, "h_ch": h_seg,
                        "Q": q_seg
                    })
            
            if nodes_ex:
                res = calculate_profiles(nodes_ex, st.session_state['ws_down'], st.session_state['ws_up'], force_super)
                st.session_state['results_ex'] = res
                st.success("✅ Analisis Selesai!")
            else:
                st.warning("Data Kosong!")
        except Exception as e:
            st.error(f"Error Running: {e}")

# --- 8. HASIL ---
tab_input, tab_viz, tab_export, tab_report = st.tabs(["📝 Input Data", "📊 Grafik Profil", "📑 Export BBWS", "📋 Laporan"])

with tab_input:
    st.session_state['df_pro'] = st.data_editor(st.session_state['df_pro'], num_rows="dynamic", use_container_width=True)

with tab_viz:
    if st.session_state['results_ex']:
        res = st.session_state['results_ex']
        x = [n['x'] for n in res]; z = [n['z'] for n in res]; ws = [n['ws'] for n in res]
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(x, z, 'k-', label='Dasar Saluran')
        ax.plot(x, ws, 'b-', label='Muka Air')
        ax.fill_between(x, z, ws, color='#00eaff', alpha=0.3)
        ax.set_title("Longitudinal Profile")
        ax.legend(); ax.grid(True, linestyle='--', alpha=0.5)
        st.pyplot(fig)
    else:
        st.info("Klik tombol 'RUN ANALISIS' di atas untuk melihat grafik.")

with tab_export:
    st.subheader("📦 Export ke AutoCAD (Standar BBWS)")
    c1, c2 = st.columns(2)
    with c1:
        distorsi = st.slider("Distorsi Vertikal (V)", 1, 20, 10)
    with c2:
        if st.session_state['results_ex']:
            scr = generate_bbws_scr(st.session_state['results_ex'], "EKSISTING", distorsi)
            st.download_button("📥 Download Script (.SCR)", scr, "LongSection_BBWS.scr")

with tab_report:
    if st.session_state['results_ex']:
        res_df = pd.DataFrame(st.session_state['results_ex'])[['x','z','ws','y_final','v','fr','regime']]
        
        # FIX ERROR: Hanya format kolom angka, jangan kolom text (regime)
        numeric_cols = ['x','z','ws','y_final','v','fr']
        st.dataframe(res_df.style.format("{:.2f}", subset=numeric_cols))
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer) as writer:
            res_df.to_excel(writer, index=False)
        st.download_button("📥 Download Laporan Excel", buffer.getvalue(), "Laporan_Hidrolika.xlsx")
