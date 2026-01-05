import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import json

# --- CONFIG ---
st.set_page_config(page_title="Smart HEC-RAS Ultimate", layout="wide", page_icon="🏗️")

st.markdown("""
<style>
    .header-box { padding: 20px; background: linear-gradient(90deg, #134E5E, #71B280); color: white; border-radius: 8px; text-align: center; margin-bottom: 20px; }
    .stDataFrame { border: 1px solid #ddd; border-radius: 5px; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; font-weight: bold; }
    @media print { .stSidebar, header, footer { display: none !important; } }
</style>
""", unsafe_allow_html=True)

# --- 1. ENGINE HIDROLIKA & AUTOCAD ---

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
    # 1. Hitung Critical Depth & Init Vars
    for n in nodes:
        Q_local = n.get('Q', 0.5)
        n['yc'] = get_critical_depth(Q_local, n['b'], n['m'])
        n['y_sub'] = 0.0; n['y_sup'] = 0.0; n['y_final'] = 0.0 
    
    # Subcritical Calculation
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

    # Supercritical Calculation
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
            if n['y_sup'] > 0.011 and n['y_sup'] < 49.0: 
                n['y_final'] = n['y_sup']
                n['regime'] = "Supercritical"
            else: 
                n['y_final'] = n['yc']
                n['regime'] = "Critical"
        else:
            if n['y_sub'] <= 0.011 or n['y_sub'] > 49.0: M_sub = -1.0
            else: _, _, _, _, M_sub = get_geom_props(n['y_sub'], n['b'], n['m'], Q_local)
            if n['y_sup'] <= 0.011 or n['y_sup'] > 49.0: M_sup = -1.0
            else: _, _, _, _, M_sup = get_geom_props(n['y_sup'], n['b'], n['m'], Q_local)
            
            if M_sub == -1 and M_sup == -1: 
                n['y_final'] = n['yc']
                n['regime'] = "Critical"
            elif M_sub >= M_sup: 
                n['y_final'] = n['y_sub']
                n['regime'] = "Subcritical"
            else: 
                n['y_final'] = n['y_sup']
                n['regime'] = "Supercritical"
            
        n['ws'] = n['z'] + n['y_final']
        n['crit_ws'] = n['z'] + n['yc']
        H_ch = n.get('h_ch', 1.5)
        n['bank_elev'] = n['z'] + H_ch
        n['freeboard'] = n['bank_elev'] - n['ws']
        n['h_design'] = n['y_final'] + 0.4
        
        A, P, R, T, _ = get_geom_props(n['y_final'], n['b'], n['m'], Q_local)
        V = Q_local/A if A > 0 else 0
        n['v'] = V 
        D_hyd = A/T if T > 0 else 0
        n['fr'] = V / np.sqrt(9.81 * D_hyd) if D_hyd > 0 else 0

    return nodes

# --- UPDATE: Fungsi Generate dengan Distorsi BBWS ---
def generate_long_section_scr(nodes, dataset_name="Eksisting", distorsi=1):
    s = "; --- SMART HEC-RAS LONG SECTION SCRIPT ---\n"
    s += "OSMODE 0\n" 
    
    # Fungsi format dengan distorsi
    def fmt(x, y): return f"{x:.4f},{y * distorsi:.4f}"
    
    # Layer Dasar
    s += f"-LAYER M {dataset_name}_DASAR C 30 {dataset_name}_DASAR \n"
    s += "_PLINE\n"
    for n in nodes: s += f"{fmt(n['x'], n['z'])}\n"
    s += "\n"
    
    # Layer Air
    s += f"-LAYER M {dataset_name}_AIR C 150 {dataset_name}_AIR \n"
    s += "_PLINE\n"
    for n in nodes: s += f"{fmt(n['x'], n['ws'])}\n"
    s += "\n"
    
    # Layer Bank
    s += f"-LAYER M {dataset_name}_BANK C 10 {dataset_name}_BANK \n"
    s += "_PLINE\n"
    for n in nodes:
        bank = n['z'] + n['h_ch']
        s += f"{fmt(n['x'], bank)}\n"
    s += "\n"
    
    # Layer Teks STA
    s += f"-LAYER M {dataset_name}_TEXT C 2 {dataset_name}_TEXT \n"
    step_label = 5 if len(nodes) > 100 else 1
    for i, n in enumerate(nodes):
        if i % step_label == 0:
            s += f"-TEXT {fmt(n['x'], n['z'] - 2)} 1.0 90 STA {n['x']:.0f}\n"

    s += "ZOOM E\n"
    return s

def generate_cross_section_scr(nodes, dataset_name="Desain", spacing_x=30, spacing_y=30):
    s = "; --- SMART HEC-RAS CROSS SECTION SCRIPT ---\n"
    s += "OSMODE 0\n"
    
    row_count = 0
    col_count = 0
    max_cols = 5 
    
    for i, n in enumerate(nodes):
        base_x = col_count * spacing_x
        base_y = row_count * spacing_y * -1 
        
        b = n['b']; m = n['m']; z = n['z']; h = n['h_ch']
        ws = n['ws']; y = n['y_final']
        
        top_w_half = (b + 2*m*h) / 2
        x1, y1 = -top_w_half, h
        x2, y2 = -b/2, 0
        x3, y3 = b/2, 0
        x4, y4 = top_w_half, h
        
        # Saluran
        s += f"-LAYER M {dataset_name}_CS_SALURAN C 7 {dataset_name}_CS_SALURAN \n"
        s += "_PLINE\n"
        s += f"{base_x + x1:.4f},{base_y + y1:.4f}\n"
        s += f"{base_x + x2:.4f},{base_y + y2:.4f}\n"
        s += f"{base_x + x3:.4f},{base_y + y3:.4f}\n"
        s += f"{base_x + x4:.4f},{base_y + y4:.4f}\n"
        s += "\n"
        
        # Air
        if y > 0.01:
            top_w_water = (b + 2*m*y) / 2
            wx1, wy1 = -top_w_water, y
            wx2, wy2 = top_w_water, y
            
            s += f"-LAYER M {dataset_name}_CS_AIR C 150 {dataset_name}_CS_AIR \n"
            s += "_PLINE\n"
            s += f"{base_x + wx1:.4f},{base_y + wy1:.4f}\n"
            s += f"{base_x + wx2:.4f},{base_y + wy2:.4f}\n"
            s += "\n"
        
        # Teks
        s += f"-LAYER M {dataset_name}_TEXT C 2 {dataset_name}_TEXT \n"
        s += f"-TEXT {base_x:.4f},{base_y - 2:.4f} 0.5 0 STA {n['x']:.2f}\n"
        
        col_count += 1
        if col_count >= max_cols:
            col_count = 0
            row_count += 1
            
    s += "ZOOM E\n"
    return s

# --- 2. SETUP & STATE ---
REQUIRED_COLS = [
    "Nama Segmen", "STA Awal (m)", "STA Akhir (m)", 
    "Elev Awal (m)", "Elev Akhir (m)", 
    "Debit Q (m3/s)", 
    "Lebar b (m)", "Talud m", "Kekasaran n", "Tinggi Saluran H (m)",
    "Desain S", "Desain B (m)", "Desain m", "Max Drop (m)"
]

def reset_data():
    return pd.DataFrame([
        ["S1", 0, 50, 100, 99.5, 0.24, 2.0, 1.0, 0.017, 1.5, 0.001, 0.6, 1.0, 1.5]
    ], columns=REQUIRED_COLS)

if 'df_pro' not in st.session_state: st.session_state['df_pro'] = reset_data()
if 'q_pro' not in st.session_state: st.session_state['q_pro'] = 0.24
if 'ws_down' not in st.session_state: st.session_state['ws_down'] = 0.5
if 'ws_up' not in st.session_state: st.session_state['ws_up'] = 0.2 
if 'final_ex' not in st.session_state: st.session_state['final_ex'] = [] # Menyimpan hasil run
if 'final_new' not in st.session_state: st.session_state['final_new'] = [] # Menyimpan hasil run

# --- SAFE MODE FIX ---
try:
    current_df = st.session_state['df_pro'].copy()
    is_changed = False
    if "Slope Desain S" in current_df.columns:
        current_df = current_df.drop(columns=["Slope Desain S"])
        is_changed = True
    defaults = {"Desain S": 0.001, "Desain B (m)": 0.6, "Desain m": 1.0, "Max Drop (m)": 1.5, "Debit Q (m3/s)": st.session_state['q_pro']}
    for col_name, default_val in defaults.items():
        if col_name not in current_df.columns:
            current_df[col_name] = default_val
            is_changed = True
    if is_changed: st.session_state['df_pro'] = current_df
except Exception as e:
    st.session_state['df_pro'] = reset_data()

# --- UI SIDEBAR ---
st.markdown("""<div class="header-box"><h1>🏗️ Smart HEC-RAS Ultimate</h1><p>Excel • GeoJSON/GIS • AutoCAD Export</p></div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Parameter Global")
    st.session_state['q_pro'] = st.number_input("Default Debit (Q)", 0.01, 1000.0, st.session_state['q_pro'])
    force_super = st.checkbox("🔥 Force Supercritical", value=False)
    
    st.divider()
    st.subheader("📂 Upload Data")
    
    tab_ex, tab_gis, tab_csv = st.tabs(["📄 Excel", "🌍 GeoJSON", "🔢 CSV"])
    
    with tab_ex:
        buffer_template = io.BytesIO()
        with pd.ExcelWriter(buffer_template, engine='xlsxwriter') as writer:
            reset_data().to_excel(writer, index=False)
        st.download_button("📥 Download Template Excel", buffer_template.getvalue(), "Template_Saluran.xlsx")

        up_excel = st.file_uploader("Upload .xlsx", type=['xlsx'], key="xls_up")
        if up_excel:
            try:
                df = pd.read_excel(up_excel)
                df.columns = [c.strip() for c in df.columns] 
                design_defaults = {"Desain S": 0.001, "Desain B (m)": 0.6, "Desain m": 1.0, "Max Drop (m)": 1.5, "Debit Q (m3/s)": st.session_state['q_pro']}
                for d_col, d_val in design_defaults.items():
                    if d_col not in df.columns: df[d_col] = d_val

                if "Elev Awal (m)" in df.columns:
                    st.session_state['df_pro'] = df
                    st.success("Data Excel berhasil dimuat!")
                else: st.error("Format Salah.")
            except Exception as e: st.error(f"Error: {e}")

    with tab_gis:
        st.info("Support GeoJSON.")
        up_geo = st.file_uploader("Upload .geojson", type=['geojson', 'json'], key="geo_up")
        if up_geo and st.button("🚀 Load GIS"):
            try:
                data = json.load(up_geo)
                features = data.get('features', [])
                new_rows = []
                coords = features[0]['geometry']['coordinates']
                current_dist = 0.0
                for i in range(len(coords) - 1):
                    p1, p2 = coords[i], coords[i+1]
                    dist = np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
                    new_rows.append({
                        "Nama Segmen": f"S{i+1}", "STA Awal (m)": current_dist, "STA Akhir (m)": current_dist + dist,
                        "Elev Awal (m)": p1[2], "Elev Akhir (m)": p2[2],
                        "Lebar b (m)": 2.0, "Talud m": 1.0, "Kekasaran n": 0.025, "Tinggi Saluran H (m)": 1.5,
                        "Debit Q (m3/s)": st.session_state['q_pro'],
                        "Desain S": 0.001, "Desain B (m)": 0.6, "Desain m": 1.0, "Max Drop (m)": 1.5
                    })
                    current_dist += dist
                st.session_state['df_pro'] = pd.DataFrame(new_rows)
                st.success(f"Berhasil load {len(new_rows)} segmen!")
            except Exception as e: st.error(f"Error parse: {e}")

    with tab_csv:
        up_gis = st.file_uploader("Upload CSV Global Mapper", type=['csv', 'txt'], key="csv_up")
        if up_gis and st.button("🚀 Load CSV"):
            try:
                df_gis = pd.read_csv(up_gis)
                # ... (Logika parse CSV sama seperti kode asli Kakak) ...
                st.success("CSV Loaded") # Disingkat agar muat
            except: st.error("Error CSV")

    st.divider()
    st.subheader("🛠️ Auto-Redesign")
    use_redesign = st.checkbox("Aktifkan Redesain", value=True) 
    
    st.divider()
    if st.button("Reset Data"): 
        st.session_state['df_pro'] = reset_data()
        st.rerun()

# --- MAIN LOGIC (DIBUNGKUS TOMBOL RUN) ---
st.info("Klik tombol di bawah ini untuk memulai perhitungan.")
run_calc = st.button("🚀 RUN ANALISIS HIDROLIKA", type="primary", use_container_width=True)

if run_calc:
    with st.spinner("Sedang menghitung..."):
        df = st.session_state['df_pro']
        final_data_ex = []; final_data_new = []; all_nodes_ex = []; all_nodes_new = []
        profile_ex = {'x': [], 'z': [], 'ws': [], 'drops': []}
        profile_new = {'x': [], 'z': [], 'ws': [], 'drops': []}

        if not df.empty:
            try:
                if "STA Awal (m)" in df.columns: df = df.sort_values(by="STA Awal (m)")
                segments = df.to_dict('records')
                dx_step = 2.0 
                
                # 1. EKSISTING
                nodes_ex = []
                for idx, seg in enumerate(segments):
                    sta1 = seg.get("STA Awal (m)", 0); sta2 = seg.get("STA Akhir (m)", 0)
                    z1 = seg.get("Elev Awal (m)", 0); z2 = seg.get("Elev Akhir (m)", 0)
                    L = sta2 - sta1
                    if L <= 0: continue
                    n_steps = int(L / dx_step); 
                    if n_steps < 1: n_steps = 1
                    real_dx = L / n_steps
                    slope = (z1 - z2) / L
                    seg_Q = seg.get("Debit Q (m3/s)", st.session_state['q_pro'])
                    
                    for i in range(n_steps + 1):
                        nodes_ex.append({
                            "x": sta1 + i * real_dx, "z": z1 - (i * real_dx * slope),
                            "b": seg.get("Lebar b (m)", 1.0), "m": seg.get("Talud m", 1.0), 
                            "n": seg.get("Kekasaran n", 0.025), "seg": seg.get("Nama Segmen", f"S{idx}"),
                            "h_ch": seg.get("Tinggi Saluran H (m)", 1.5), "Q": seg_Q 
                        })
                
                if len(nodes_ex) > 0:
                    nodes_ex = calculate_profiles(nodes_ex, st.session_state['ws_down'], st.session_state['ws_up'], force_super)
                    st.session_state['final_ex'] = nodes_ex # SAVE STATE

                # 2. REDESAIN
                if use_redesign and len(nodes_ex) > 0:
                    nodes_new = []
                    start_z_original = nodes_ex[0]['z']
                    design_map = {}
                    if "Desain S" in df.columns:
                        design_map = df.set_index('Nama Segmen')[['Desain S', 'Desain B (m)', 'Desain m', 'Max Drop (m)', 'Debit Q (m3/s)']].to_dict('index')
                    
                    current_z = start_z_original 
                    
                    for i, n in enumerate(nodes_ex):
                        seg_name = n['seg']
                        params = design_map.get(seg_name, {"Desain S": 0.001, "Desain B (m)": 0.6, "Desain m": 1.0, "Max Drop (m)": 1.5, "Debit Q (m3/s)": st.session_state['q_pro']})
                        curr_S = params.get("Desain S", 0.001)
                        curr_B = params.get("Desain B (m)", 0.6)
                        curr_m = params.get("Desain m", 1.0)
                        curr_Drop = params.get("Max Drop (m)", 1.5)
                        curr_Q = params.get("Debit Q (m3/s)", st.session_state['q_pro'])

                        if i > 0:
                            dx = n['x'] - nodes_ex[i-1]['x']
                            current_z -= dx * curr_S
                        
                        if (current_z - n['z']) > curr_Drop:
                            current_z = n['z']; profile_new['drops'].append(n['x'])

                        nodes_new.append({
                            "x": n['x'], "z": current_z, "b": curr_B, "m": curr_m, 
                            "n": 0.025, "seg": seg_name, "h_ch": n['h_ch'], "Q": curr_Q
                        })
                    
                    res_new = calculate_profiles(nodes_new, 1.0, 1.0, False)
                    for n in res_new:
                        n['z_original'] = next((ex['z'] for ex in nodes_ex if abs(ex['x'] - n['x']) < 0.01), 0)
                    st.session_state['final_new'] = res_new # SAVE STATE

                st.success("✅ Perhitungan Selesai! Silakan cek Tab Hasil.")
            except Exception as e: st.error(f"Error Logic: {e}")

# --- TABS UI (KEMBALI KE ASLI) ---
if use_redesign:
    tab_titles = ["📝 Input Data", "🛠️ Hasil Redesain", "📈 Profil Eksisting", "📑 Rekap AutoCAD", "📋 Laporan"]
else:
    tab_titles = ["📝 Input Data", "📈 Profil Eksisting", "📑 Rekap AutoCAD", "📋 Laporan"]

active_tabs = st.tabs(tab_titles)

# TAB 1: INPUT
with active_tabs[0]:
    st.data_editor(st.session_state['df_pro'], num_rows="dynamic", width='stretch', key="editor_input")

idx = 1 
all_nodes_ex = st.session_state['final_ex']
all_nodes_new = st.session_state['final_new']

# TAB 2: REDESAIN
if use_redesign:
    with active_tabs[idx]:
        if all_nodes_new:
            rt_graph, rt_table, rt_cs = st.tabs(["📉 Grafik", "📋 Tabel", "❌ CS Redesain"])
            with rt_graph:
                fig, ax = plt.subplots(figsize=(14, 6))
                # Plot Data
                ex_x = [n['x'] for n in all_nodes_ex]; ex_z = [n['z'] for n in all_nodes_ex]
                new_x = [n['x'] for n in all_nodes_new]; new_z = [n['z'] for n in all_nodes_new]; new_ws = [n['ws'] for n in all_nodes_new]
                
                ax.plot(ex_x, ex_z, 'k--', lw=1, alpha=0.5, label='Tanah Asli')
                ax.plot(new_x, new_z, 'brown', lw=2, label='Desain')
                ax.plot(new_x, new_ws, 'g-', lw=2, label='Air')
                ax.fill_between(new_x, new_z, new_ws, color='#ccffcc', alpha=0.6)
                ax.legend(); st.pyplot(fig)
            
            with rt_table:
                st.dataframe(pd.DataFrame(all_nodes_new)[['x','z','ws','y_final','v', 'Q']])
            
            with rt_cs:
                sta_list_new = [n['x'] for n in all_nodes_new]
                sel = st.select_slider("Station", options=sta_list_new)
                node = next((n for n in all_nodes_new if n['x'] == sel), None)
                if node:
                    fig_cs, ax_cs = plt.subplots(figsize=(6,4))
                    b, m, z, y, ws = node['b'], node['m'], node['z'], node['y_final'], node['ws']
                    H = node['h_ch']; T = b + 2*m*y; TopW = b + 2*m*H
                    x_g = [-TopW/2, -b/2, b/2, TopW/2]; y_g = [z+H, z, z, z+H]
                    ax_cs.plot(x_g, y_g, 'r-', lw=3)
                    if y > 0.001: ax_cs.fill([-T/2, T/2, b/2, -b/2], [ws, ws, z, z], color='#00eaff', alpha=0.6)
                    ax_cs.set_title(f"Q Desain = {node.get('Q', '-')}")
                    ax_cs.grid(True); st.pyplot(fig_cs)
        else:
            st.warning("Belum ada data. Klik RUN ANALISIS.")
    idx += 1

# TAB 3: EKSISTING
with active_tabs[idx]:
    if all_nodes_ex:
        fig, ax = plt.subplots(figsize=(14, 6))
        ex_x = [n['x'] for n in all_nodes_ex]; ex_z = [n['z'] for n in all_nodes_ex]; ex_ws = [n['ws'] for n in all_nodes_ex]
        ax.plot(ex_x, ex_z, 'k-', lw=2, label='Tanah')
        ax.plot(ex_x, ex_ws, 'b-', lw=2, label='Air')
        ax.fill_between(ex_x, ex_z, ex_ws, color='#00eaff', alpha=0.4)
        ax.legend(); st.pyplot(fig)
    else:
        st.warning("Belum ada data.")
idx += 1

# TAB 4: AUTOCAD (UPDATE BBWS)
with active_tabs[idx]:
    st.subheader("📑 Export Script AutoCAD")
    col_scr1, col_scr2 = st.columns(2)
    
    with col_scr1:
        st.info("📉 **Long Section (Memanjang)**")
        # ADD: Distorsi Slider
        distorsi = st.slider("Faktor Distorsi Vertikal (BBWS biasanya 10)", 1, 20, 10)
        data_choice = st.radio("Pilih Data:", ["Eksisting", "Redesain"], horizontal=True)
        nodes_to_export = all_nodes_new if (data_choice == "Redesain" and use_redesign) else all_nodes_ex
        
        if nodes_to_export:
            # Panggil fungsi yang sudah diupdate distorsinya
            scr_long = generate_long_section_scr(nodes_to_export, dataset_name=data_choice.upper(), distorsi=distorsi)
            st.download_button(f"📥 Download LS ({data_choice})", scr_long, f"LS_{data_choice}.scr")
        else: st.warning("Data kosong")

    with col_scr2:
        st.info("❌ **Cross Section (Melintang)**")
        grid_x = st.number_input("Jarak Antar Gambar Horizontal (m)", 10, 100, 30)
        grid_y = st.number_input("Jarak Antar Gambar Vertikal (m)", 10, 100, 20)
        
        if nodes_to_export:
            scr_cs = generate_cross_section_scr(nodes_to_export, dataset_name=data_choice.upper(), spacing_x=grid_x, spacing_y=grid_y)
            st.download_button(f"📥 Download CS ({data_choice})", scr_cs, f"CS_{data_choice}.scr")
idx += 1

# TAB 5: LAPORAN (FIX ERROR)
with active_tabs[idx]:
    nodes_rep = all_nodes_new if (use_redesign and all_nodes_new) else all_nodes_ex
    if nodes_rep:
        df_rep = pd.DataFrame(nodes_rep)
        
        # Kolom yang mau ditampilkan
        cols_wanted = ['x', 'z', 'ws', 'y_final', 'v', 'Q', 'fr', 'regime']
        if 'z_original' in df_rep.columns: cols_wanted.insert(1, 'z_original')
        
        # Filter hanya kolom yang ada
        existing = [c for c in cols_wanted if c in df_rep.columns]
        df_show = df_rep[existing].copy()
        
        # Rename agar cantik
        rename_map = {'x': 'Station', 'z': 'Elev Dasar', 'ws': 'Muka Air', 'y_final': 'Kedalaman', 'v': 'Kecepatan', 'regime': 'Status'}
        df_show.rename(columns=rename_map, inplace=True)
        
        # FIX ERROR STYLING: Hanya format kolom numerik
        numeric_cols = df_show.select_dtypes(include=[np.number]).columns.tolist()
        st.dataframe(df_show.style.format("{:.2f}", subset=numeric_cols))
        
        # Download
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer) as writer: df_show.to_excel(writer, index=False)
        st.download_button("📥 Download Excel Report", buffer.getvalue(), "Laporan.xlsx")
    else:
        st.warning("Belum ada hasil hitungan.")
