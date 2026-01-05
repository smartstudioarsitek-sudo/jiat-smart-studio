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
    for n in nodes:
        Q_local = n.get('Q', 0.5)
        n['yc'] = get_critical_depth(Q_local, n['b'], n['m'])
        n['y_sub'] = 0.0; n['y_sup'] = 0.0; n['y_final'] = 0.0 
    
    # Subcritical
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

    # Supercritical
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

    # Selection
    for n in nodes:
        Q_local = n.get('Q', 0.5)
        if force_super:
            if n['y_sup'] > 0.011 and n['y_sup'] < 49.0: 
                n['y_final'] = n['y_sup']; n['regime'] = "Supercritical"
            else: 
                n['y_final'] = n['yc']; n['regime'] = "Critical"
        else:
            if n['y_sub'] <= 0.011 or n['y_sub'] > 49.0: M_sub = -1.0
            else: _, _, _, _, M_sub = get_geom_props(n['y_sub'], n['b'], n['m'], Q_local)
            if n['y_sup'] <= 0.011 or n['y_sup'] > 49.0: M_sup = -1.0
            else: _, _, _, _, M_sup = get_geom_props(n['y_sup'], n['b'], n['m'], Q_local)
            
            if M_sub == -1 and M_sup == -1: 
                n['y_final'] = n['yc']; n['regime'] = "Critical"
            elif M_sub >= M_sup: 
                n['y_final'] = n['y_sub']; n['regime'] = "Subcritical"
            else: 
                n['y_final'] = n['y_sup']; n['regime'] = "Supercritical"
            
        n['ws'] = n['z'] + n['y_final']
        n['crit_ws'] = n['z'] + n['yc']
        H_ch = n.get('h_ch', 1.5)
        n['bank_elev'] = n['z'] + H_ch
        n['freeboard'] = n['bank_elev'] - n['ws']
        
        A, P, R, T, _ = get_geom_props(n['y_final'], n['b'], n['m'], Q_local)
        V = Q_local/A if A > 0 else 0
        n['v'] = V; n['eg'] = n['ws'] + (V**2)/(2*9.81)
        D_hyd = A/T if T > 0 else 0
        n['fr'] = V / np.sqrt(9.81 * D_hyd) if D_hyd > 0 else 0
    return nodes

def generate_long_section_scr(nodes, dataset_name="Eksisting"):
    s = "; --- LONG SECTION SCRIPT ---\nOSMODE 0\n" 
    s += f"-LAYER M {dataset_name}_DASAR C 30 {dataset_name}_DASAR \n_PLINE\n"
    for n in nodes: s += f"{n['x']:.4f},{n['z']:.4f}\n"
    s += "\n"
    s += f"-LAYER M {dataset_name}_AIR C 150 {dataset_name}_AIR \n_PLINE\n"
    for n in nodes: s += f"{n['x']:.4f},{n['ws']:.4f}\n"
    s += "\n"
    s += f"-LAYER M {dataset_name}_BANK C 10 {dataset_name}_BANK \n_PLINE\n"
    for n in nodes: s += f"{n['x']:.4f},{(n['z']+n['h_ch']):.4f}\n"
    s += "\nZOOM E\n"
    return s

def generate_cross_section_scr(nodes, dataset_name="Desain", spacing_x=20, spacing_y=20):
    s = "; --- CROSS SECTION SCRIPT ---\nOSMODE 0\n"
    row = 0; col = 0; max_cols = 5 
    for i, n in enumerate(nodes):
        bx = col * spacing_x; by = row * spacing_y * -1 
        b = n['b']; m = n['m']; z = n['z']; h = n['h_ch']; ws = n['ws']; y = n['y_final']
        top_w = (b + 2*m*h) / 2
        
        s += f"-LAYER M {dataset_name}_CS_SALURAN C 7 {dataset_name}_CS_SALURAN \n_PLINE\n"
        s += f"{bx-top_w:.4f},{by+h:.4f}\n{bx-b/2:.4f},{by:.4f}\n{bx+b/2:.4f},{by:.4f}\n{bx+top_w:.4f},{by+h:.4f}\n\n"
        
        if y > 0.01:
            tw_wat = (b + 2*m*y) / 2
            s += f"-LAYER M {dataset_name}_CS_AIR C 150 {dataset_name}_CS_AIR \n_PLINE\n"
            s += f"{bx-tw_wat:.4f},{by+y:.4f}\n{bx+tw_wat:.4f},{by+y:.4f}\n\n"
        
        s += f"-LAYER M {dataset_name}_TEXT C 2 {dataset_name}_TEXT \n"
        s += f"-TEXT {bx:.4f},{by-2:.4f} 0.5 0 STA {n['x']:.2f}\n"
        col += 1
        if col >= max_cols: col = 0; row += 1
    s += "ZOOM E\n"
    return s

# --- 2. SETUP & STATE ---
REQUIRED_COLS = [
    "Nama Segmen", "STA Awal (m)", "STA Akhir (m)", "Elev Awal (m)", "Elev Akhir (m)", 
    "Debit Q (m3/s)", "Lebar b (m)", "Talud m", "Kekasaran n", "Tinggi Saluran H (m)",
    "Desain S", "Desain B (m)", "Desain m", "Max Drop (m)"
]

def reset_data():
    return pd.DataFrame([["S1", 0, 50, 100, 99.5, 0.24, 2.0, 1.0, 0.017, 1.5, 0.001, 0.6, 1.0, 1.5]], columns=REQUIRED_COLS)

if 'df_pro' not in st.session_state: st.session_state['df_pro'] = reset_data()
if 'q_pro' not in st.session_state: st.session_state['q_pro'] = 0.24
if 'ws_down' not in st.session_state: st.session_state['ws_down'] = 0.5
if 'ws_up' not in st.session_state: st.session_state['ws_up'] = 0.2
if 'force_super' not in st.session_state: st.session_state['force_super'] = False

# Auto-fix columns
try:
    df_curr = st.session_state['df_pro'].copy()
    defaults = {"Desain S": 0.001, "Desain B (m)": 0.6, "Desain m": 1.0, "Max Drop (m)": 1.5, "Debit Q (m3/s)": st.session_state['q_pro']}
    changed = False
    for c, v in defaults.items():
        if c not in df_curr.columns: df_curr[c] = v; changed = True
    if changed: st.session_state['df_pro'] = df_curr
except: st.session_state['df_pro'] = reset_data()

# --- UI SIDEBAR (MODIFIKASI UTAMA) ---
st.markdown("""<div class="header-box"><h1>🏗️ Smart HEC-RAS Ultimate</h1><p>Open • Save • Calculate</p></div>""", unsafe_allow_html=True)

with st.sidebar:
    # --- MENU OPEN & SAVE (BARU) ---
    st.expander("📁 MENU PROJECT (OPEN / SAVE)", expanded=True).markdown("Simpan pekerjaanmu agar tidak hilang!")
    
    col_save, col_open = st.sidebar.columns(2)
    
    # 1. SAVE PROJECT
    with col_save:
        # Fungsi Save ke Excel dengan 2 Sheet (Data & Parameter)
        buffer_save = io.BytesIO()
        with pd.ExcelWriter(buffer_save, engine='xlsxwriter') as writer:
            st.session_state['df_pro'].to_excel(writer, sheet_name='Data Saluran', index=False)
            # Simpan Parameter Global juga
            params_df = pd.DataFrame([{
                'q_pro': st.session_state['q_pro'],
                'ws_down': st.session_state['ws_down'],
                'ws_up': st.session_state['ws_up'],
                'force_super': st.session_state['force_super']
            }])
            params_df.to_excel(writer, sheet_name='Parameter Global', index=False)
            
        st.download_button(
            label="💾 Simpan Project",
            data=buffer_save.getvalue(),
            file_name="Project_Saluran.xlsx",
            mime="application/vnd.ms-excel",
            help="Download file .xlsx berisi data tabel dan setting parameter."
        )

    # 2. OPEN PROJECT
    uploaded_project = st.sidebar.file_uploader("📂 Buka Project (.xlsx)", type=['xlsx'], key="open_proj")
    if uploaded_project:
        try:
            xls = pd.ExcelFile(uploaded_project)
            # Load Data Saluran
            if 'Data Saluran' in xls.sheet_names:
                st.session_state['df_pro'] = pd.read_excel(xls, sheet_name='Data Saluran')
            else:
                st.session_state['df_pro'] = pd.read_excel(uploaded_project) # Fallback kalau sheet 1 doang
            
            # Load Parameter Global (jika ada)
            if 'Parameter Global' in xls.sheet_names:
                p_df = pd.read_excel(xls, sheet_name='Parameter Global')
                if not p_df.empty:
                    st.session_state['q_pro'] = float(p_df.iloc[0]['q_pro'])
                    st.session_state['ws_down'] = float(p_df.iloc[0]['ws_down'])
                    st.session_state['ws_up'] = float(p_df.iloc[0]['ws_up'])
                    st.session_state['force_super'] = bool(p_df.iloc[0]['force_super'])
            
            if 'editor_input' in st.session_state: del st.session_state['editor_input']
            st.success("Project Berhasil Dibuka!")
            st.rerun()
        except Exception as e:
            st.error(f"Gagal membuka file: {e}")

    st.divider()
    st.header("⚙️ Parameter Global")
    st.session_state['q_pro'] = st.number_input("Default Debit (Q)", 0.01, 1000.0, st.session_state['q_pro'])
    st.session_state['ws_down'] = st.number_input("Tinggi Air Hilir (m)", 0.0, 50.0, st.session_state['ws_down'])
    st.session_state['ws_up'] = st.number_input("Tinggi Air Hulu (m)", 0.0, 50.0, st.session_state['ws_up'])
    st.session_state['force_super'] = st.checkbox("🔥 Force Supercritical", value=st.session_state['force_super'])

    st.divider()
    with st.expander("🛠️ Tools Import Lainnya"):
        tab_gis, tab_csv = st.tabs(["🌍 GeoJSON", "🔢 CSV GM"])
        with tab_gis:
            up_geo = st.file_uploader("Upload .geojson", type=['geojson', 'json'], key="geo_up")
            if up_geo and st.button("Load GIS"):
                # (Logika GeoJSON disederhanakan agar fit, sama seperti sebelumnya)
                try:
                    data = json.load(up_geo)
                    coords = data['features'][0]['geometry']['coordinates']
                    new_rows = []
                    curr_dist = 0.0
                    for i in range(len(coords)-1):
                        p1=coords[i]; p2=coords[i+1]
                        dist=np.sqrt((p2[0]-p1[0])**2+(p2[1]-p1[1])**2)
                        new_rows.append(["S"+str(i+1), curr_dist, curr_dist+dist, p1[2], p2[2], st.session_state['q_pro'], 2.0, 1.0, 0.025, 1.5, 0.001, 0.6, 1.0, 1.5])
                        curr_dist+=dist
                    st.session_state['df_pro'] = pd.DataFrame(new_rows, columns=REQUIRED_COLS)
                    if 'editor_input' in st.session_state: del st.session_state['editor_input']
                    st.rerun()
                except: st.error("Format GeoJSON Error")
        
        with tab_csv:
            up_csv = st.file_uploader("Upload CSV", type=['csv'], key="csv_up")
            if up_csv and st.button("Load CSV"):
                # (Logika CSV Global Mapper)
                try:
                    df_gis = pd.read_csv(up_csv); df_gis.columns = [c.lower() for c in df_gis.columns]
                    # Simple parser logic
                    col_d = [c for c in df_gis.columns if 'dist' in c][0]
                    col_z = [c for c in df_gis.columns if 'elev' in c][0]
                    new_rows = []
                    for i in range(len(df_gis)-1):
                        d1=df_gis.iloc[i][col_d]; d2=df_gis.iloc[i+1][col_d]
                        if abs(d2-d1)<0.01: continue
                        new_rows.append(["S"+str(i+1), d1, d2, df_gis.iloc[i][col_z], df_gis.iloc[i+1][col_z], st.session_state['q_pro'], 2.0, 1.0, 0.025, 1.5, 0.001, 0.6, 1.0, 1.5])
                    st.session_state['df_pro'] = pd.DataFrame(new_rows, columns=REQUIRED_COLS)
                    if 'editor_input' in st.session_state: del st.session_state['editor_input']
                    st.rerun()
                except: st.error("Format CSV Error")

    if st.button("⚠️ Reset Semua Data"): 
        st.session_state['df_pro'] = reset_data()
        if 'editor_input' in st.session_state: del st.session_state['editor_input']
        st.rerun()

# --- MAIN LOGIC ---
df = st.session_state['df_pro']
profile_ex = {'x': [], 'z': [], 'ws': [], 'crit': [], 'bank': []} 
profile_new = {'x': [], 'z': [], 'ws': [], 'drops': []} 
final_data_new = []; all_nodes_new = []; all_nodes_ex = []

if not df.empty:
    try:
        if "STA Awal (m)" in df.columns: df = df.sort_values(by="STA Awal (m)")
        segments = df.to_dict('records')
        
        # 1. EKSISTING
        nodes_ex = []
        for idx, seg in enumerate(segments):
            sta1 = seg.get("STA Awal (m)", 0); sta2 = seg.get("STA Akhir (m)", 0)
            z1 = seg.get("Elev Awal (m)", 0); z2 = seg.get("Elev Akhir (m)", 0)
            L = sta2 - sta1; dx_step = 2.0
            if L <= 0: continue
            n_steps = max(1, int(L / dx_step))
            real_dx = L / n_steps; slope = (z1 - z2) / L
            seg_Q = seg.get("Debit Q (m3/s)", st.session_state['q_pro'])
            
            for i in range(n_steps + 1):
                nodes_ex.append({
                    "x": sta1 + i * real_dx, "z": z1 - (i * real_dx * slope),
                    "b": seg.get("Lebar b (m)", 1.0), "m": seg.get("Talud m", 1.0), 
                    "n": seg.get("Kekasaran n", 0.025), "seg": seg.get("Nama Segmen", f"S{idx}"),
                    "h_ch": seg.get("Tinggi Saluran H (m)", 1.5), "Q": seg_Q
                })
        
        if nodes_ex:
            nodes_ex = calculate_profiles(nodes_ex, st.session_state['ws_down'], st.session_state['ws_up'], st.session_state['force_super'])
            all_nodes_ex = nodes_ex
            for n in nodes_ex:
                profile_ex['x'].append(n['x']); profile_ex['z'].append(n['z'])
                profile_ex['ws'].append(n['ws']); profile_ex['crit'].append(n['crit_ws'])
                profile_ex['bank'].append(n['bank_elev'])

        # 2. REDESAIN
        use_redesign = True 
        if use_redesign and nodes_ex:
            nodes_new = []
            design_map = df.set_index('Nama Segmen').to_dict('index') if "Desain S" in df.columns else {}
            current_z = nodes_ex[0]['z']
            
            for i, n in enumerate(nodes_ex):
                params = design_map.get(n['seg'], {"Desain S": 0.001, "Desain B (m)": 0.6, "Desain m": 1.0, "Max Drop (m)": 1.5, "Debit Q (m3/s)": st.session_state['q_pro']})
                if i > 0: current_z -= (n['x'] - nodes_ex[i-1]['x']) * params.get("Desain S", 0.001)
                if (current_z - n['z']) > params.get("Max Drop (m)", 1.5):
                      current_z = n['z']; profile_new['drops'].append(n['x'])
                
                nodes_new.append({
                    "x": n['x'], "z": current_z, "b": params.get("Desain B (m)", 0.6), "m": params.get("Desain m", 1.0), 
                    "n": 0.025, "seg": n['seg'], "h_ch": n['h_ch'], "Q": params.get("Debit Q (m3/s)", st.session_state['q_pro'])
                })
            
            res_new = calculate_profiles(nodes_new, 1.0, 1.0, False)
            all_nodes_new = res_new
            for n in res_new:
                profile_new['x'].append(n['x']); profile_new['z'].append(n['z']); profile_new['ws'].append(n['ws'])
                n['z_original'] = next((ex['z'] for ex in nodes_ex if abs(ex['x'] - n['x']) < 0.01), 0)
                final_data_new.append(n)
    except Exception as e: st.error(f"Error Calc: {e}")

# --- TABS OUTPUT ---
tabs = st.tabs(["📝 Input Data", "🛠️ Hasil Redesain", "📈 Profil Eksisting", "📑 AutoCAD", "📋 Laporan"])

with tabs[0]:
    st.info("💡 Edit data di sini. Jangan lupa SIMPAN PROJECT di Sidebar setelah selesai!")
    st.data_editor(st.session_state['df_pro'], num_rows="dynamic", width='stretch', key="editor_input")

with tabs[1]:
    if profile_new['x']:
        fig, ax = plt.subplots(figsize=(14, 6))
        ax.plot(profile_ex['x'], profile_ex['z'], 'k--', alpha=0.5, label='Tanah Asli')
        ax.plot(profile_new['x'], profile_new['z'], 'brown', lw=2, label='Desain')
        ax.plot(profile_new['x'], profile_new['ws'], 'g-', lw=2, label='Air')
        ax.fill_between(profile_new['x'], profile_new['z'], profile_new['ws'], color='#ccffcc', alpha=0.6)
        for d in profile_new['drops']: ax.axvline(x=d, color='red', ls='--')
        ax.legend(); st.pyplot(fig)
        st.dataframe(pd.DataFrame(final_data_new)[['x','z','ws','y_final','v', 'Q']])

with tabs[2]:
    if profile_ex['x']:
        fig, ax = plt.subplots(figsize=(14, 6))
        ax.plot(profile_ex['x'], profile_ex['z'], 'k-', label='Tanah')
        ax.plot(profile_ex['x'], profile_ex['ws'], 'b-', label='Air')
        ax.fill_between(profile_ex['x'], profile_ex['z'], profile_ex['ws'], color='#00eaff', alpha=0.4)
        ax.legend(); st.pyplot(fig)

with tabs[3]:
    st.info("Generate Script AutoCAD (.scr)")
    c1, c2 = st.columns(2)
    nodes_out = all_nodes_new if all_nodes_new else all_nodes_ex
    d_name = "DESAIN" if all_nodes_new else "EKSISTING"
    with c1:
        st.download_button("📥 Long Section (.scr)", generate_long_section_scr(nodes_out, d_name), f"LS_{d_name}.scr")
    with c2:
        st.download_button("📥 Cross Section (.scr)", generate_cross_section_scr(nodes_out, d_name), f"CS_{d_name}.scr")

with tabs[4]:
    if final_data_new:
        df_rep = pd.DataFrame(final_data_new)[['x','z_original','z','ws','y_final','v','Q','fr','regime']]
        st.dataframe(df_rep.style.format("{:.2f}", subset=['x','z_original','z','ws','y_final','v','Q','fr']))
        b_rep = io.BytesIO()
        with pd.ExcelWriter(b_rep, engine='xlsxwriter') as w: df_rep.to_excel(w, index=False)
        st.download_button("📥 Download Excel Laporan", b_rep.getvalue(), "Laporan.xlsx")
