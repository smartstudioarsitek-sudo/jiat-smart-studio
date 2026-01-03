import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import io

# --- CONFIG ---
st.set_page_config(page_title="Smart HEC-RAS Ultimate", layout="wide", page_icon="🏗️")

st.markdown("""
<style>
    .header-box { padding: 20px; background: linear-gradient(90deg, #134E5E, #71B280); color: white; border-radius: 8px; text-align: center; margin-bottom: 20px; }
    .metric-card { background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #28a745; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .metric-label { font-size: 12px; color: #666; margin-bottom: 0; }
    .metric-value { font-size: 18px; font-weight: bold; color: #333; margin: 0; }
    @media print { .stSidebar, header, footer { display: none !important; } }
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
        
        H_ch = n.get('h_ch', 1.5) # Default H=1.5
        n['bank_elev'] = n['z'] + H_ch
        n['freeboard'] = n['bank_elev'] - n['ws']
        n['h_design'] = n['y_final'] + 0.4
        
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

if 'df_pro' not in st.session_state: st.session_state['df_pro'] = reset_data()
if 'q_pro' not in st.session_state: st.session_state['q_pro'] = 0.24
if 'ws_down' not in st.session_state: st.session_state['ws_down'] = 0.5
if 'ws_up' not in st.session_state: st.session_state['ws_up'] = 0.2 

# --- UI SIDEBAR ---
st.markdown("""<div class="header-box"><h1>🏗️ Smart HEC-RAS Ultimate</h1><p>GIS Import • Auto-Redesign • Freeboard Check</p></div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Parameter Hidrolis")
    st.session_state['q_pro'] = st.number_input("Debit (Q) m³/s", 0.01, 1000.0, st.session_state['q_pro'])
    force_super = st.checkbox("🔥 Force Supercritical (Cek Gerusan)", value=False)
    
    st.divider()
    st.subheader("🛠️ Auto-Redesign (Opsional)")
    use_redesign = st.checkbox("Aktifkan Fitur Redesain", value=False)
    if use_redesign:
        target_slope = st.number_input("Target Kemiringan (S)", 0.0001, 0.05, 0.001, format="%.4f")
        design_b = st.number_input("Lebar Desain (m)", 0.1, 50.0, 1.5)
        max_drop = st.number_input("Max Drop (m)", 0.5, 5.0, 1.5)
    
    st.divider()
    st.subheader("📂 Input Data")
    
    tab_file1, tab_file2 = st.tabs(["🌍 GIS/CSV", "📄 Excel"])
    
    with tab_file1:
        up_gis = st.file_uploader("Upload CSV Global Mapper", type=['csv', 'txt'], key="gis_up")
        if up_gis and st.button("🚀 Konversi GIS"):
            try:
                df_gis = pd.read_csv(up_gis)
                df_gis.columns = [c.lower() for c in df_gis.columns]
                col_dist = next((c for c in df_gis.columns if any(x in c for x in ['dist', 'len', 'x', 'sta'])), None)
                col_elev = next((c for c in df_gis.columns if any(x in c for x in ['elev', 'z', 'height'])), None)
                
                if col_dist and col_elev:
                    new_rows = []
                    for i in range(len(df_gis) - 1):
                        d1 = df_gis.iloc[i][col_dist]; d2 = df_gis.iloc[i+1][col_dist]
                        z1 = df_gis.iloc[i][col_elev]; z2 = df_gis.iloc[i+1][col_elev]
                        if abs(d2 - d1) < 0.01: continue
                        new_rows.append({
                            "Nama Segmen": f"S{i+1}", "STA Awal (m)": d1, "STA Akhir (m)": d2,
                            "Elev Awal (m)": z1, "Elev Akhir (m)": z2,
                            "Lebar b (m)": 2.0, "Talud m": 1.0, "Kekasaran n": 0.025, "Tinggi Saluran H (m)": 1.5
                        })
                    st.session_state['df_pro'] = pd.DataFrame(new_rows)
                    st.success(f"Import {len(new_rows)} segmen sukses!")
                    st.rerun()
            except Exception as e: st.error(f"Error: {e}")

    with tab_file2:
        up_excel = st.file_uploader("Upload Excel", type=['xlsx'], key="xls_up")
        if up_excel:
            try:
                df = pd.read_excel(up_excel)
                st.session_state['df_pro'] = df
                st.rerun()
            except: pass

    if st.button("Reset Data"): st.session_state['df_pro'] = reset_data(); st.rerun()

# --- MAIN LOGIC ---
df = st.session_state['df_pro']
profile_ex = {'x': [], 'z': [], 'ws': [], 'crit': [], 'bank': []} # Existing
profile_new = {'x': [], 'z': [], 'ws': [], 'drops': []} # Redesign

final_data_ex = []
final_data_new = []
all_nodes_ex = []

if not df.empty:
    try:
        if "STA Awal (m)" in df.columns: df = df.sort_values(by="STA Awal (m)")
        segments = df.to_dict('records')
        dx_step = 2.0 
        
        # 1. GENERATE NODES EKSISTING
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
            h_ch = seg.get("Tinggi Saluran H (m)", 1.5)
            
            for i in range(n_steps + 1):
                nodes_ex.append({
                    "x": sta1 + i * real_dx,
                    "z": z1 - (i * real_dx * slope),
                    "b": seg.get("Lebar b (m)", 1.0), "m": seg.get("Talud m", 1.0), 
                    "n": seg.get("Kekasaran n", 0.025), "seg": seg.get("Nama Segmen", f"S{idx}"),
                    "h_ch": h_ch
                })
        
        # 2. RUN EKSISTING
        if len(nodes_ex) > 0:
            nodes_ex = calculate_profiles(nodes_ex, st.session_state['q_pro'], st.session_state['ws_down'], st.session_state['ws_up'], force_super)
            all_nodes_ex = nodes_ex
            for n in nodes_ex:
                profile_ex['x'].append(n['x']); profile_ex['z'].append(n['z'])
                profile_ex['ws'].append(n['ws']); profile_ex['crit'].append(n['crit_ws'])
                profile_ex['bank'].append(n['bank_elev'])
                final_data_ex.append(n)

        # 3. RUN REDESAIN (JIKA AKTIF)
        if use_redesign and len(nodes_ex) > 0:
            nodes_new = []
            current_z = nodes_ex[0]['z']
            
            for i, n in enumerate(nodes_ex):
                if i > 0:
                    dx = n['x'] - nodes_ex[i-1]['x']
                    current_z -= dx * target_slope
                
                # Cek Terjunan
                if (current_z - n['z']) > max_drop:
                    current_z = n['z']
                    profile_new['drops'].append(n['x'])
                
                nodes_new.append({
                    "x": n['x'], "z": current_z,
                    "b": design_b, "m": 1.0, "n": 0.025,
                    "seg": n['seg'], "h_ch": n['h_ch']
                })
            
            res_new = calculate_profiles(nodes_new, st.session_state['q_pro'], 1.0, 1.0, False) # Force Subcritical
            for n in res_new:
                profile_new['x'].append(n['x']); profile_new['z'].append(n['z']); profile_new['ws'].append(n['ws'])
                final_data_new.append(n)

    except Exception as e: st.error(f"Error: {e}")

# --- TABS ---
if use_redesign:
    tabs = ["🛠️ Hasil Redesain", "📈 Profil Eksisting", "❌ Cross Section", "📑 Rekap AutoCAD", "📝 Input"]
else:
    tabs = ["📈 Profil Eksisting", "❌ Cross Section", "📑 Rekap AutoCAD", "📋 Laporan", "📝 Input"]

active_tabs = st.tabs(tabs)

# LOGIC UNTUK TAB REDESAIN (JIKA AKTIF)
if use_redesign:
    with active_tabs[0]:
        if len(profile_new['x']) > 0:
            fig, ax = plt.subplots(figsize=(14, 8))
            ax.plot(profile_ex['x'], profile_ex['z'], 'k-', lw=1, alpha=0.3, label='Tanah Asli')
            ax.plot(profile_new['x'], profile_new['z'], 'brown', lw=2.5, label='Saluran Baru (Cascading)')
            ax.plot(profile_new['x'], profile_new['ws'], 'g-', lw=2, label='Muka Air (Subkritis)')
            ax.fill_between(profile_new['x'], profile_new['z'], profile_new['ws'], color='#ccffcc', alpha=0.6)
            
            for d in profile_new['drops']:
                ax.axvline(x=d, color='red', ls='--'); ax.text(d, max(profile_ex['z']), "DROP", color='red', rotation=90)
            
            ax.set_title("Redesain Saluran Berjenjang"); ax.legend(); ax.grid(True, alpha=0.5)
            st.pyplot(fig)
            
            st.success(f"Jumlah Terjunan: {len(profile_new['drops'])} | Kecepatan Rata2 Baru: {np.mean([n['v'] for n in final_data_new]):.2f} m/s")

# LOGIC UNTUK TAB EKSISTING (Standard)
target_tab_idx = 1 if use_redesign else 0
with active_tabs[target_tab_idx]:
    if len(profile_ex['x']) > 0:
        fig, ax = plt.subplots(figsize=(14, 8))
        ax.plot(profile_ex['x'], profile_ex['z'], 'k-', lw=2.5, label='Dasar Saluran')
        ax.plot(profile_ex['x'], profile_ex['ws'], 'b-', lw=2, label='Muka Air')
        ax.plot(profile_ex['x'], profile_ex['bank'], 'brown', ls='--', lw=2, label='Bibir Tanggul')
        ax.fill_between(profile_ex['x'], profile_ex['z'], profile_ex['ws'], color='#00eaff', alpha=0.4)
        ax.plot(profile_ex['x'], profile_ex['eg'], 'g-.', lw=1, label='Energy Grade')
        
        ax.minorticks_on(); ax.grid(which='major', alpha=0.7); ax.grid(which='minor', alpha=0.3)
        ax.set_title(f"Profil Memanjang Eksisting - Q={st.session_state['q_pro']}"); ax.legend()
        st.pyplot(fig)

# LOGIC CROSS SECTION
target_tab_idx += 1
with active_tabs[target_tab_idx]:
    if len(all_nodes_ex) > 0:
        st.subheader("Visualisasi Penampang")
        sta_list = [n['x'] for n in all_nodes_ex]
        sel_sta = st.select_slider("Station (m)", options=sta_list, value=sta_list[0])
        node = next((n for n in all_nodes_ex if n['x'] == sel_sta), None)
        if node:
            c1, c2 = st.columns([2,1])
            with c1:
                fig_cs, ax_cs = plt.subplots(figsize=(8,5))
                b, m, z, y, ws = node['b'], node['m'], node['z'], node['y_final'], node['ws']
                H = node['h_ch']; T = b + 2*m*y; TopW = b + 2*m*H
                x_g = [-TopW/2, -b/2, b/2, TopW/2]; y_g = [z+H, z, z, z+H]
                ax_cs.plot(x_g, y_g, 'k-', lw=3); ax_cs.fill_between(x_g, y_g, min(y_g), color='gray', alpha=0.3)
                if y > 0.001:
                    ax_cs.plot([-T/2, T/2], [ws, ws], 'b-', lw=2)
                    ax_cs.fill([-T/2, T/2, b/2, -b/2], [ws, ws, z, z], color='#00eaff', alpha=0.6)
                ax_cs.set_title(f"CS STA {sel_sta:.2f}"); ax_cs.grid(True)
                st.pyplot(fig_cs)
            with c2:
                fb = node['freeboard']
                clr = "red" if fb < 0.3 else "green"
                st.markdown(f"**Freeboard:** <span style='color:{clr}; font-size:18px'>{fb:.3f} m</span>", unsafe_allow_html=True)
                st.metric("Kecepatan", f"{node['v']:.2f} m/s")

# LOGIC REKAP
target_tab_idx += 1
with active_tabs[target_tab_idx]:
    if final_data_ex:
        res_df = pd.DataFrame(final_data_ex)
        summ = []
        for s in res_df['seg'].unique():
            d = res_df[res_df['seg'] == s]
            hulu, hilir = d.iloc[0], d.iloc[-1]
            summ.append({
                "Segmen": s, "STA Awal": f"{hulu['x']:.2f}", "STA Akhir": f"{hilir['x']:.2f}",
                "Elev Hulu": f"{hulu['z']:.2f}", "Elev Hilir": f"{hilir['z']:.2f}",
                "MA Hulu": f"{hulu['ws']:.2f}", "Jagaan Hulu": f"{hulu['freeboard']:.2f}",
                "Saran Tinggi Desain": f"{hulu['h_design']:.2f}"
            })
        st.dataframe(pd.DataFrame(summ), width='stretch')

# LOGIC INPUT
with active_tabs[-1]:
    st.data_editor(st.session_state['df_pro'], num_rows="dynamic", width='stretch')
